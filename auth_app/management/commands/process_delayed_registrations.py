from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
import logging
import requests
import json
import os
import time
from datetime import timedelta

# Configure logger
logger = logging.getLogger(__name__)
User = get_user_model()

class Command(BaseCommand):
    help = 'Process delayed registrations that encountered rate limits'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max-attempts',
            type=int,
            default=5,
            help='Maximum attempts to register a user in Supabase'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Only show what would be done without making changes'
        )
        parser.add_argument(
            '--delay',
            type=int,
            default=5,
            help='Delay between registration attempts in seconds'
        )

    def handle(self, *args, **options):
        max_attempts = options['max_attempts']
        dry_run = options['dry_run']
        delay = options['delay']
        
        self.stdout.write(f"Processing delayed registrations (dry-run: {dry_run})")
        
        # Get unverified users that need to be registered in Supabase
        # Users with no supabase_id who have been created more than 5 minutes ago
        # to avoid race conditions with normal registration
        cutoff_time = timezone.now() - timedelta(minutes=5)
        pending_users = User.objects.filter(
            supabase_id__isnull=True,
            email_verified=False,
            date_joined__lt=cutoff_time
        )
        
        self.stdout.write(f"Found {pending_users.count()} users pending Supabase registration")
        
        # Process each user
        success_count = 0
        failed_count = 0
        
        # Get Supabase URL and key
        supabase_url = settings.SUPABASE_URL
        service_key = settings.SUPABASE_SERVICE_KEY
        
        if not supabase_url or not service_key:
            self.stdout.write(self.style.ERROR("Missing Supabase URL or service role key"))
            return
            
        # Set up API headers for admin operations
        headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json"
        }
        
        for user in pending_users:
            self.stdout.write(f"Processing user: {user.email}")
            
            if dry_run:
                self.stdout.write(self.style.SUCCESS(f"[DRY RUN] Would register {user.email} in Supabase"))
                continue
                
            # Generate a random password for the user
            from django.utils.crypto import get_random_string
            temp_password = get_random_string(16)
            
            # Determine if we should verify the email directly
            # Users that have been in the system for a while can be auto-verified
            auto_verify = (timezone.now() - user.date_joined) > timedelta(days=1)
            
            # Try to register the user in Supabase
            for attempt in range(1, max_attempts + 1):
                try:
                    # Create user in Supabase with admin API
                    create_url = f"{supabase_url}/auth/v1/admin/users"
                    create_data = {
                        "email": user.email,
                        "password": temp_password,
                        "email_confirm": auto_verify,  # Auto-verify if the user has been around for a while
                        "user_metadata": {
                            "username": user.username
                        }
                    }
                    
                    self.stdout.write(f"Attempt {attempt}/{max_attempts} for {user.email}")
                    response = requests.post(create_url, headers=headers, json=create_data)
                    
                    if response.status_code == 200:
                        # Success! Update the user's Supabase ID
                        supabase_data = response.json()
                        supabase_id = supabase_data.get('id')
                        
                        if supabase_id:
                            user.supabase_id = supabase_id
                            if auto_verify:
                                user.email_verified = True
                            user.save()
                            success_count += 1
                            self.stdout.write(self.style.SUCCESS(f"Successfully registered {user.email} in Supabase"))
                            break
                    else:
                        # Check response for specific errors
                        error_body = response.text
                        
                        try:
                            error_data = json.loads(error_body)
                            error_message = error_data.get('message', '')
                            
                            # If the email is already registered, update the user's Supabase ID
                            if "already registered" in error_message.lower() or "already exists" in error_message.lower():
                                # Try to find the user in Supabase by email
                                self.stdout.write(f"User {user.email} appears to already exist in Supabase")
                                
                                # Try to get the user's ID from Supabase
                                search_url = f"{supabase_url}/auth/v1/admin/users"
                                search_response = requests.get(search_url, headers=headers)
                                
                                if search_response.status_code == 200:
                                    supabase_users = search_response.json()
                                    
                                    # Handle different response formats
                                    if isinstance(supabase_users, dict) and 'users' in supabase_users:
                                        supabase_users = supabase_users['users']
                                    
                                    # Find the user by email
                                    for supabase_user in supabase_users:
                                        if supabase_user.get('email', '').lower() == user.email.lower():
                                            # Found the user, update the Supabase ID
                                            supabase_id = supabase_user.get('id')
                                            if supabase_id:
                                                user.supabase_id = supabase_id
                                                
                                                # Check if email is verified in Supabase
                                                if (supabase_user.get('email_confirmed_at') or 
                                                    supabase_user.get('confirmed_at')):
                                                    user.email_verified = True
                                                    
                                                user.save()
                                                success_count += 1
                                                self.stdout.write(self.style.SUCCESS(
                                                    f"User {user.email} already in Supabase, updated ID"
                                                ))
                                                break
                                
                                # Break the retry loop since we've handled this case
                                break
                            
                            # If we hit rate limits, wait and retry
                            if "rate limit" in error_message.lower():
                                if attempt < max_attempts:
                                    self.stdout.write(f"Rate limit hit for {user.email}, waiting {delay}s before retry...")
                                    time.sleep(delay)
                                    continue
                        except json.JSONDecodeError:
                            pass
                        
                        # If we've reached the max attempts, log the error
                        if attempt == max_attempts:
                            self.stdout.write(self.style.ERROR(
                                f"Failed to register {user.email} after {max_attempts} attempts: {response.status_code} - {error_body}"
                            ))
                            failed_count += 1
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"Error processing {user.email}: {str(e)}"))
                    if attempt == max_attempts:
                        failed_count += 1
                    else:
                        time.sleep(delay)
            
        status = "[DRY RUN] " if dry_run else ""
        self.stdout.write(self.style.SUCCESS(
            f"{status}Completed delayed registration processing: "
            f"Success: {success_count}, Failed: {failed_count}, Total: {pending_users.count()}"
        )) 
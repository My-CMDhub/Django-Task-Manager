from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import transaction
import logging
import requests
import json
from datetime import datetime

logger = logging.getLogger(__name__)
User = get_user_model()

class Command(BaseCommand):
    help = 'Synchronize users between Django and Supabase'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without actually making changes',
        )
        parser.add_argument(
            '--direction',
            type=str,
            default='both',
            choices=['to-django', 'to-supabase', 'both'],
            help='Direction of synchronization',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force synchronization even if users already exist',
        )
        parser.add_argument(
            '--email',
            type=str,
            help='Synchronize only the specified email address',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        direction = options['direction']
        force = options['force']
        email_filter = options.get('email')
        
        self.stdout.write(f"Starting user synchronization (direction: {direction}, dry_run: {dry_run})")
        
        # Get Supabase service key and URL
        supabase_url = settings.SUPABASE_URL
        service_key = settings.SUPABASE_SERVICE_KEY
        
        if not supabase_url or not service_key:
            self.stdout.write(self.style.ERROR("Missing Supabase URL or service role key."))
            return
        
        # Set up API headers
        headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json"
        }
        
        # Get Supabase users
        supabase_users = self.get_supabase_users(supabase_url, headers)
        if supabase_users is None:
            return
            
        # Filter by email if specified
        if email_filter:
            supabase_users = [user for user in supabase_users if user.get('email', '').lower() == email_filter.lower()]
            self.stdout.write(f"Filtered Supabase users by email: {email_filter} - found {len(supabase_users)} users")
            
        # Get Django users
        django_query = User.objects.all()
        if email_filter:
            django_query = django_query.filter(email__iexact=email_filter)
            self.stdout.write(f"Filtered Django users by email: {email_filter}")
        django_users = list(django_query)
        
        # Create email-to-object mappings for easy lookup
        supabase_users_by_email = {user.get('email', '').lower(): user for user in supabase_users if user.get('email')}
        django_users_by_email = {user.email.lower(): user for user in django_users if user.email}
        
        # Create ID-to-object mappings for users with IDs
        supabase_users_by_id = {user.get('id'): user for user in supabase_users if user.get('id')}
        django_users_by_id = {user.supabase_id: user for user in django_users if user.supabase_id}
        
        self.stdout.write(f"Found {len(supabase_users)} users in Supabase")
        self.stdout.write(f"Found {len(django_users)} users in Django")
        
        # Synchronize from Supabase to Django if needed
        if direction in ['to-django', 'both']:
            self.sync_to_django(
                supabase_users, 
                django_users_by_email, 
                django_users_by_id,
                dry_run,
                force
            )
            
        # Synchronize from Django to Supabase if needed
        if direction in ['to-supabase', 'both']:
            self.sync_to_supabase(
                django_users, 
                supabase_users_by_email, 
                supabase_users_by_id,
                supabase_url,
                headers,
                dry_run,
                force
            )
            
        self.stdout.write(self.style.SUCCESS("User synchronization completed"))
        
    def get_supabase_users(self, supabase_url, headers):
        """Get all users from Supabase"""
        try:
            # Construct the Auth API URL
            auth_api_url = f"{supabase_url}/auth/v1/admin/users"
            response = requests.get(auth_api_url, headers=headers)
            
            if response.status_code != 200:
                self.stdout.write(self.style.ERROR(
                    f"Failed to list Supabase users: {response.status_code} - {response.text}"
                ))
                return None
            
            # Parse the response
            users_data = response.json()
            
            # Handle different response structures
            if isinstance(users_data, dict) and 'users' in users_data:
                return users_data['users']
            elif isinstance(users_data, list):
                return users_data
            else:
                self.stdout.write(self.style.ERROR(f"Unexpected response format: {type(users_data)}"))
                return []
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error getting Supabase users: {str(e)}"))
            return None
            
    @transaction.atomic
    def sync_to_django(self, supabase_users, django_users_by_email, django_users_by_id, dry_run, force):
        """Synchronize users from Supabase to Django"""
        created_count = 0
        updated_count = 0
        error_count = 0
        
        self.stdout.write(self.style.SUCCESS("\nSynchronizing from Supabase to Django:"))
        
        for supabase_user in supabase_users:
            user_id = supabase_user.get('id')
            email = supabase_user.get('email')
            
            if not email:
                self.stdout.write(self.style.WARNING(f"  Skipping Supabase user with no email (ID: {user_id})"))
                continue
                
            email = email.lower()
            existing_django_user = django_users_by_email.get(email) or django_users_by_id.get(user_id)
            
            if existing_django_user:
                # User already exists in Django, update if needed
                needs_update = False
                changes = []
                
                # Check if Supabase ID needs updating
                if existing_django_user.supabase_id != user_id:
                    changes.append(f"Supabase ID: {existing_django_user.supabase_id} -> {user_id}")
                    if not dry_run:
                        existing_django_user.supabase_id = user_id
                    needs_update = True
                
                # Check email verification status
                email_verified = self._check_email_verified(supabase_user)
                if email_verified and not existing_django_user.email_verified:
                    changes.append(f"Email verified: False -> True")
                    if not dry_run:
                        existing_django_user.email_verified = True
                    needs_update = True
                
                # Update user info if needed
                if needs_update:
                    if dry_run:
                        self.stdout.write(f"  Would update Django user {email}: {', '.join(changes)}")
                    else:
                        try:
                            existing_django_user.save(update_fields=['supabase_id', 'email_verified'])
                            self.stdout.write(self.style.SUCCESS(f"  Updated Django user {email}: {', '.join(changes)}"))
                            updated_count += 1
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"  Error updating Django user {email}: {str(e)}"))
                            error_count += 1
                else:
                    self.stdout.write(f"  Django user {email} already in sync")
                    
            else:
                # User does not exist in Django, create a new user
                # Generate random password - user will need to reset it
                from django.utils.crypto import get_random_string
                temp_password = get_random_string(16)
                
                # Get username from metadata or use email
                username = email.split('@')[0]
                user_meta = supabase_user.get('raw_user_meta_data', {})
                if isinstance(user_meta, dict) and 'username' in user_meta:
                    username = user_meta.get('username')
                
                # Make username unique if needed
                username_base = username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{username_base}{counter}"
                    counter += 1
                
                # Check email verification status
                email_verified = self._check_email_verified(supabase_user)
                
                if dry_run:
                    self.stdout.write(f"  Would create Django user: {email} (Supabase ID: {user_id})")
                else:
                    try:
                        new_user = User.objects.create_user(
                            username=username,
                            email=email,
                            password=temp_password,
                            supabase_id=user_id,
                            email_verified=email_verified
                        )
                        self.stdout.write(self.style.SUCCESS(f"  Created Django user: {email} (Supabase ID: {user_id})"))
                        
                        # Create profile if needed
                        try:
                            profile = new_user.profile
                        except Exception:
                            # If UserProfile model exists and has a relationship to User
                            try:
                                from auth_app.models import UserProfile
                                UserProfile.objects.create(
                                    user=new_user,
                                    supabase_uid=user_id,
                                    verified=email_verified
                                )
                            except Exception:
                                pass  # Profile model not available or has different structure
                                
                        created_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"  Error creating Django user {email}: {str(e)}"))
                        error_count += 1
                        
        self.stdout.write(self.style.SUCCESS(f"\nSynchronization to Django completed: {created_count} created, {updated_count} updated, {error_count} errors"))
    
    def sync_to_supabase(self, django_users, supabase_users_by_email, supabase_users_by_id, supabase_url, headers, dry_run, force):
        """Synchronize users from Django to Supabase"""
        created_count = 0
        updated_count = 0
        error_count = 0
        
        self.stdout.write(self.style.SUCCESS("\nSynchronizing from Django to Supabase:"))
        
        for django_user in django_users:
            email = django_user.email.lower()
            supabase_id = django_user.supabase_id
            
            if not email:
                self.stdout.write(self.style.WARNING(f"  Skipping Django user with no email (ID: {django_user.id})"))
                continue
                
            existing_supabase_user = supabase_users_by_email.get(email) or (supabase_id and supabase_users_by_id.get(supabase_id))
            
            if existing_supabase_user:
                # User already exists in Supabase, update if needed
                needs_update = False
                changes = []
                
                # Check email verification status
                email_confirmed = self._check_email_verified(existing_supabase_user)
                if django_user.email_verified and not email_confirmed:
                    changes.append("Email verification status")
                    needs_update = True
                
                # Update user if needed
                if needs_update:
                    if dry_run:
                        self.stdout.write(f"  Would update Supabase user {email}: {', '.join(changes)}")
                    else:
                        try:
                            # Only update email verification status for now
                            # More complex updates would require additional API calls
                            if 'Email verification status' in changes:
                                supabase_id = existing_supabase_user.get('id')
                                if supabase_id:
                                    self._confirm_supabase_email(supabase_url, headers, supabase_id)
                                    
                            self.stdout.write(self.style.SUCCESS(f"  Updated Supabase user {email}: {', '.join(changes)}"))
                            updated_count += 1
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"  Error updating Supabase user {email}: {str(e)}"))
                            error_count += 1
                else:
                    self.stdout.write(f"  Supabase user {email} already in sync")
                    
            elif force:
                # User does not exist in Supabase, create a new user
                # Generate a random password
                from django.utils.crypto import get_random_string
                temp_password = get_random_string(16)
                
                # Prepare metadata
                user_metadata = {
                    "username": django_user.username,
                    "created_via": "django_sync"
                }
                
                if dry_run:
                    self.stdout.write(f"  Would create Supabase user: {email}")
                else:
                    try:
                        # Create user in Supabase
                        response = self._create_supabase_user(
                            supabase_url,
                            headers,
                            email,
                            temp_password,
                            user_metadata,
                            django_user.email_verified
                        )
                        
                        if response and response.get('id'):
                            supabase_id = response.get('id')
                            
                            # Update Django user with Supabase ID
                            django_user.supabase_id = supabase_id
                            django_user.save(update_fields=['supabase_id'])
                            
                            self.stdout.write(self.style.SUCCESS(f"  Created Supabase user: {email} (ID: {supabase_id})"))
                            created_count += 1
                        else:
                            self.stdout.write(self.style.ERROR(f"  Failed to create Supabase user {email}"))
                            error_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"  Error creating Supabase user {email}: {str(e)}"))
                        error_count += 1
            else:
                self.stdout.write(f"  Django user {email} not found in Supabase (use --force to create)")
                
        self.stdout.write(self.style.SUCCESS(f"\nSynchronization to Supabase completed: {created_count} created, {updated_count} updated, {error_count} errors"))
    
    def _check_email_verified(self, user_record):
        """Helper function to check if email is verified based on Supabase user record"""
        # Check confirmation timestamp
        if user_record.get('email_confirmed_at'):
            return True
            
        # Check raw user metadata
        user_meta = user_record.get('raw_user_meta_data', {})
        if isinstance(user_meta, dict) and user_meta.get('email_verified') is True:
            return True
            
        # Check confirmed_at field  
        if user_record.get('confirmed_at'):
            return True
            
        return False
        
    def _confirm_supabase_email(self, supabase_url, headers, user_id):
        """Confirm a user's email in Supabase"""
        try:
            update_url = f"{supabase_url}/auth/v1/admin/users/{user_id}"
            now = datetime.utcnow().isoformat()
            
            update_data = {
                "email_confirmed_at": now,
                "confirmed_at": now
            }
            
            response = requests.put(update_url, headers=headers, json=update_data)
            
            if response.status_code != 200:
                self.stdout.write(self.style.ERROR(
                    f"Failed to confirm email: {response.status_code} - {response.text}"
                ))
                return False
                
            return True
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error confirming email: {str(e)}"))
            return False
            
    def _create_supabase_user(self, supabase_url, headers, email, password, metadata, email_verified):
        """Create a new user in Supabase"""
        try:
            users_url = f"{supabase_url}/auth/v1/admin/users"
            
            user_data = {
                "email": email,
                "password": password,
                "email_confirm": email_verified,
                "user_metadata": metadata
            }
            
            if email_verified:
                now = datetime.utcnow().isoformat()
                user_data["email_confirmed_at"] = now
                user_data["confirmed_at"] = now
            
            response = requests.post(users_url, headers=headers, json=user_data)
            
            if response.status_code not in (200, 201):
                self.stdout.write(self.style.ERROR(
                    f"Failed to create user: {response.status_code} - {response.text}"
                ))
                return None
                
            return response.json()
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error creating Supabase user: {str(e)}"))
            return None 
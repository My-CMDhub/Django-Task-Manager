import logging
from django.core.management.base import BaseCommand
from django.conf import settings
from auth_app.models import User
from datetime import datetime
from mysite.settings import get_supabase_admin_client

class Command(BaseCommand):
    help = 'Syncs users from Supabase to Django'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update all users even if they are already synced',
        )

    def handle(self, *args, **options):
        force_update = options.get('force', False)
        supabase_admin = get_supabase_admin_client()

        if not supabase_admin:
            self.stderr.write(self.style.ERROR('Failed to initialize Supabase admin client'))
            return

        self.stdout.write(self.style.SUCCESS('Starting user sync from Supabase to Django'))
        
        try:
            # Get all users from Supabase
            response = supabase_admin.auth.admin.list_users()
            supabase_users = response.users if hasattr(response, 'users') else []
            
            if not supabase_users:
                self.stdout.write(self.style.WARNING('No users found in Supabase'))
                return

            self.stdout.write(f'Found {len(supabase_users)} users in Supabase')
            
            # Process each user
            created_count = 0
            updated_count = 0
            skipped_count = 0
            
            for supabase_user in supabase_users:
                supabase_id = supabase_user.id
                email = supabase_user.email
                
                if not email:
                    self.stdout.write(self.style.WARNING(f'Skipping user with no email: {supabase_id}'))
                    skipped_count += 1
                    continue
                    
                # Check if user already exists
                user_exists = User.objects.filter(supabase_id=supabase_id).exists()
                email_exists = User.objects.filter(email=email).exists()
                
                if user_exists and not force_update:
                    self.stdout.write(f'User already exists and is synced: {email}')
                    skipped_count += 1
                    continue
                    
                # Get or create user
                if email_exists:
                    # Update existing user
                    user = User.objects.get(email=email)
                    if not user.supabase_id:
                        user.supabase_id = supabase_id
                    
                    # Update user fields
                    user.email_verified = supabase_user.email_confirmed_at is not None
                    user.is_active = not supabase_user.banned
                    
                    # Update last login if available
                    if hasattr(supabase_user, 'last_sign_in_at') and supabase_user.last_sign_in_at:
                        user.last_login = datetime.fromisoformat(supabase_user.last_sign_in_at.replace('Z', '+00:00'))
                    
                    user.save()
                    self.stdout.write(f'Updated user: {email}')
                    updated_count += 1
                else:
                    # Create new user
                    username = email.split('@')[0]
                    base_username = username
                    counter = 1
                    
                    # Ensure username is unique
                    while User.objects.filter(username=username).exists():
                        username = f"{base_username}{counter}"
                        counter += 1
                    
                    user = User(
                        username=username,
                        email=email,
                        supabase_id=supabase_id,
                        email_verified=supabase_user.email_confirmed_at is not None,
                        is_active=not supabase_user.banned,
                    )
                    
                    # Set last login if available
                    if hasattr(supabase_user, 'last_sign_in_at') and supabase_user.last_sign_in_at:
                        user.last_login = datetime.fromisoformat(supabase_user.last_sign_in_at.replace('Z', '+00:00'))
                    
                    # Save without triggering validation
                    user.save()
                    self.stdout.write(self.style.SUCCESS(f'Created user: {email}'))
                    created_count += 1
            
            # Summary
            self.stdout.write(self.style.SUCCESS(
                f'Sync completed: {created_count} created, {updated_count} updated, {skipped_count} skipped'
            ))
            
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error syncing users: {str(e)}'))
            logging.exception('Error in sync_supabase_users command') 
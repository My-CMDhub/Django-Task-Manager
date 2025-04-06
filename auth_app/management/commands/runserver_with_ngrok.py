from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings
import os
import requests
import json
import time
import subprocess
import signal
import sys
import threading
import logging
from auth_app.models import User, UserProfile
from mysite.settings import get_supabase_admin_client

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Runs the server with ngrok integration and syncs with Supabase'

    def add_arguments(self, parser):
        parser.add_argument(
            '--auto-sync',
            action='store_true',
            help='Automatically synchronize users with Supabase',
        )
        parser.add_argument(
            '--no-browser',
            action='store_true',
            help='Do not open the browser automatically',
        )

    def handle(self, *args, **options):
        auto_sync = options.get('auto_sync', False)
        no_browser = options.get('no_browser', False)
        
        self.stdout.write(self.style.SUCCESS('Starting ngrok tunnel...'))
        
        # Start ngrok in a separate thread
        ngrok_thread = threading.Thread(target=self.start_ngrok)
        ngrok_thread.daemon = True
        ngrok_thread.start()
        
        # Wait for ngrok to start
        time.sleep(2)
        
        # Get ngrok public URL
        try:
            ngrok_url = self.get_ngrok_url()
            if ngrok_url:
                self.stdout.write(self.style.SUCCESS(f'Ngrok tunnel started: {ngrok_url}'))
                
                # Update SITE_URL in settings
                os.environ['SITE_URL'] = ngrok_url
                if hasattr(settings, 'SITE_URL'):
                    settings.SITE_URL = ngrok_url
                
                # Update Supabase site URL if auto-sync enabled
                if auto_sync:
                    os.environ['SUPABASE_SITE_URL'] = ngrok_url
                    self.stdout.write(self.style.SUCCESS(f'Setting SUPABASE_SITE_URL to {ngrok_url}'))
                    
                    # Sync users with Supabase
                    self.sync_with_supabase()
            else:
                self.stdout.write(self.style.ERROR('Failed to get ngrok URL. Continuing without tunnel.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error getting ngrok URL: {str(e)}'))
        
        # Start Django server
        self.stdout.write(self.style.SUCCESS('Starting Django server...'))
        
        # Run the server
        try:
            call_command('runserver')
        except KeyboardInterrupt:
            self.stdout.write(self.style.SUCCESS('Stopping server...'))
        finally:
            # Cleanup
            self.cleanup()
    
    def start_ngrok(self):
        """Start ngrok tunnel to expose local server"""
        try:
            subprocess.run(
                ['ngrok', 'http', '8000', '--log=stdout'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        except Exception as e:
            logger.error(f"Error starting ngrok: {str(e)}")
    
    def get_ngrok_url(self):
        """Get the public ngrok URL"""
        try:
            response = requests.get('http://localhost:4040/api/tunnels')
            if response.status_code == 200:
                data = response.json()
                for tunnel in data.get('tunnels', []):
                    if tunnel.get('proto') == 'https':
                        return tunnel.get('public_url')
                # Fall back to http if https not found
                for tunnel in data.get('tunnels', []):
                    if tunnel.get('proto') == 'http':
                        return tunnel.get('public_url')
            return None
        except Exception as e:
            logger.error(f"Error getting ngrok URL: {str(e)}")
            return None
    
    def sync_with_supabase(self):
        """Synchronize users with Supabase"""
        self.stdout.write(self.style.SUCCESS('Synchronizing users with Supabase...'))
        
        try:
            # Get admin client
            admin_client = get_supabase_admin_client()
            if not admin_client:
                self.stdout.write(self.style.ERROR('Failed to get Supabase admin client'))
                return
            
            # Get users from Supabase
            self.stdout.write(self.style.SUCCESS('Fetching users from Supabase...'))
            supabase_users = self.get_supabase_users(admin_client)
            
            # Get Django users
            django_users = User.objects.all()
            
            # Display info
            self.stdout.write(self.style.SUCCESS(f'Found {len(supabase_users)} users in Supabase'))
            self.stdout.write(self.style.SUCCESS(f'Found {django_users.count()} users in Django'))
            
            # Display Supabase users
            self.stdout.write(self.style.SUCCESS('\nSupabase Users:'))
            for user in supabase_users:
                email = user.get('email', 'Unknown')
                user_id = user.get('id', 'Unknown')
                confirmed = 'Verified' if user.get('email_confirmed_at') else 'Not Verified'
                self.stdout.write(f"  • {email} (ID: {user_id}) - {confirmed}")
            
            # Display Django users
            self.stdout.write(self.style.SUCCESS('\nDjango Users:'))
            for user in django_users:
                try:
                    profile = UserProfile.objects.get(user=user)
                    supabase_uid = profile.supabase_uid or 'Not linked'
                    verified = 'Verified' if profile.verified else 'Not Verified'
                except UserProfile.DoesNotExist:
                    supabase_uid = 'No profile'
                    verified = 'Unknown'
                    
                self.stdout.write(f"  • {user.email} (ID: {user.id}, Supabase: {supabase_uid}) - {verified}")
            
            # Check for inconsistencies
            self.check_user_consistency(django_users, supabase_users)
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error during synchronization: {str(e)}'))
    
    def get_supabase_users(self, admin_client):
        """Get users from Supabase"""
        try:
            users_response = admin_client.auth.admin.list_users()
            if users_response:
                return users_response
            return []
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error fetching Supabase users: {str(e)}'))
            return []
    
    def check_user_consistency(self, django_users, supabase_users):
        """Check for inconsistencies between Django and Supabase users"""
        self.stdout.write(self.style.SUCCESS('\nChecking for inconsistencies...'))
        
        # Create dictionaries for faster lookup
        django_dict = {user.email.lower(): user for user in django_users}
        supabase_dict = {user.get('email', '').lower(): user for user in supabase_users if user.get('email')}
        
        # Users in Django but not in Supabase
        in_django_only = set(django_dict.keys()) - set(supabase_dict.keys())
        if in_django_only:
            self.stdout.write(self.style.WARNING('Users in Django but not in Supabase:'))
            for email in in_django_only:
                user = django_dict[email]
                self.stdout.write(f"  • {user.email} (ID: {user.id})")
        else:
            self.stdout.write(self.style.SUCCESS('No users found only in Django'))
        
        # Users in Supabase but not in Django
        in_supabase_only = set(supabase_dict.keys()) - set(django_dict.keys())
        if in_supabase_only:
            self.stdout.write(self.style.WARNING('Users in Supabase but not in Django:'))
            for email in in_supabase_only:
                user = supabase_dict[email]
                self.stdout.write(f"  • {email} (ID: {user.get('id')})")
        else:
            self.stdout.write(self.style.SUCCESS('No users found only in Supabase'))
        
        # Check verification status mismatches
        self.stdout.write(self.style.SUCCESS('\nChecking verification status...'))
        mismatches = []
        for email in set(django_dict.keys()) & set(supabase_dict.keys()):
            django_user = django_dict[email]
            supabase_user = supabase_dict[email]
            
            try:
                profile = UserProfile.objects.get(user=django_user)
                django_verified = profile.verified
                supabase_verified = supabase_user.get('email_confirmed_at') is not None
                
                if django_verified != supabase_verified:
                    mismatches.append((
                        email,
                        'Verified' if django_verified else 'Not Verified',
                        'Verified' if supabase_verified else 'Not Verified'
                    ))
            except UserProfile.DoesNotExist:
                mismatches.append((email, 'No profile', 'Unknown'))
        
        if mismatches:
            self.stdout.write(self.style.WARNING('Verification status mismatches:'))
            for email, django_status, supabase_status in mismatches:
                self.stdout.write(f"  • {email} - Django: {django_status}, Supabase: {supabase_status}")
        else:
            self.stdout.write(self.style.SUCCESS('No verification status mismatches found'))
    
    def cleanup(self):
        """Clean up resources"""
        # Try to kill any lingering ngrok processes
        try:
            if sys.platform == 'win32':
                subprocess.run(['taskkill', '/F', '/IM', 'ngrok.exe'], 
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL)
            else:
                subprocess.run("pkill -f ngrok", shell=True, 
                               stdout=subprocess.DEVNULL, 
                               stderr=subprocess.DEVNULL)
        except Exception:
            pass
        
        self.stdout.write(self.style.SUCCESS('Cleanup completed')) 
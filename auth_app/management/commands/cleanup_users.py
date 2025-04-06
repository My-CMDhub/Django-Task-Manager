from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

User = get_user_model()

class Command(BaseCommand):
    help = 'Remove all users from Django and attempt to remove from Supabase'

    def add_arguments(self, parser):
        parser.add_argument(
            '--preserve-admin',
            action='store_true',
            help='Preserve admin/superuser accounts',
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm deletion without prompting',
        )

    def handle(self, *args, **options):
        preserve_admin = options['preserve_admin']
        confirm = options['confirm']
        
        # Count users
        total_users = User.objects.count()
        if preserve_admin:
            users_to_delete = User.objects.filter(is_superuser=False).count()
        else:
            users_to_delete = total_users
            
        if not confirm:
            self.stdout.write(f"About to delete {users_to_delete} of {total_users} users.")
            if preserve_admin:
                self.stdout.write("Admin accounts will be preserved.")
            else:
                self.stdout.write("WARNING: This will also delete admin accounts!")
                
            confirm_delete = input("Are you sure you want to proceed? (yes/no): ")
            if confirm_delete.lower() != 'yes':
                self.stdout.write(self.style.WARNING("Operation cancelled."))
                return
        
        # Delete from Django
        try:
            self.stdout.write("Deleting users from Django database...")
            if preserve_admin:
                deleted, _ = User.objects.filter(is_superuser=False).delete()
            else:
                deleted, _ = User.objects.all().delete()
            self.stdout.write(self.style.SUCCESS(f"Successfully deleted {deleted} users from Django."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error deleting Django users: {e}"))
        
        # Attempt to delete from Supabase
        try:
            from mysite.settings import get_supabase_admin_client
            admin_client = get_supabase_admin_client()
            
            if admin_client:
                self.stdout.write("Attempting to delete users from Supabase...")
                
                # List all users
                users_response = admin_client.auth.admin.list_users()
                
                user_count = 0
                if users_response and hasattr(users_response, 'data'):
                    for user in users_response.data:
                        if 'id' in user:
                            try:
                                # Skip admin users if preserve_admin is True
                                if preserve_admin and 'app_metadata' in user:
                                    role = user.get('app_metadata', {}).get('role', '')
                                    if role == 'admin' or role == 'supabase_admin':
                                        self.stdout.write(f"Preserving admin user {user.get('email', 'unknown')}")
                                        continue
                                
                                admin_client.auth.admin.delete_user(user['id'])
                                user_count += 1
                                self.stdout.write(f"Deleted Supabase user: {user.get('email', 'unknown')}")
                            except Exception as delete_error:
                                self.stdout.write(
                                    self.style.WARNING(f"Failed to delete Supabase user {user.get('email', 'unknown')}: {delete_error}")
                                )
                
                self.stdout.write(self.style.SUCCESS(f"Deleted {user_count} users from Supabase."))
            else:
                self.stdout.write(self.style.WARNING("No Supabase admin client available. Only Django users were deleted."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error accessing Supabase: {e}"))
        
        self.stdout.write(self.style.SUCCESS("User cleanup completed.")) 
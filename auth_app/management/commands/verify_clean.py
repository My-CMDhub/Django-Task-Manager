from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.conf import settings
import logging
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

User = get_user_model()

class Command(BaseCommand):
    help = 'Verify that both Django and Supabase databases are clean of users'

    def handle(self, *args, **options):
        # Check Django users
        django_user_count = User.objects.count()
        if django_user_count == 0:
            self.stdout.write(self.style.SUCCESS("✅ Django database is clean (0 users)"))
        else:
            self.stdout.write(self.style.ERROR(f"❌ Django database has {django_user_count} users"))
            
        # Check Supabase users
        try:
            from auth_app.views import get_supabase_admin_client
            admin_client = get_supabase_admin_client()
            
            if admin_client:
                self.stdout.write("Checking Supabase users...")
                
                try:
                    # Use direct API call for reliability
                    headers = {
                        "apikey": settings.SUPABASE_SERVICE_KEY,
                        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
                        "Content-Type": "application/json"
                    }
                    
                    # Construct the Auth API URL for listing users
                    auth_api_url = f"{settings.SUPABASE_URL}/auth/v1/admin/users"
                    
                    # Get the list of all users
                    response = requests.get(auth_api_url, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        users = response.json()
                        if isinstance(users, list):
                            supabase_user_count = len(users)
                            if supabase_user_count == 0:
                                self.stdout.write(self.style.SUCCESS("✅ Supabase database is clean (0 users)"))
                            else:
                                self.stdout.write(self.style.ERROR(f"❌ Supabase has {supabase_user_count} users"))
                                # Print user emails
                                self.stdout.write("User emails in Supabase:")
                                for user in users:
                                    if isinstance(user, dict) and 'email' in user:
                                        self.stdout.write(f" - {user['email']}")
                        else:
                            self.stdout.write(self.style.ERROR("❌ Unable to determine Supabase user count (invalid response format)"))
                    else:
                        self.stdout.write(self.style.ERROR(f"❌ Unable to check Supabase users: HTTP {response.status_code}"))
                        
                except Exception as api_error:
                    self.stdout.write(self.style.ERROR(f"❌ Error checking Supabase users via API: {str(api_error)}"))
                    
                    # Fallback to using the admin client
                    try:
                        users_response = admin_client.auth.admin.list_users()
                        if users_response and hasattr(users_response, 'data'):
                            supabase_user_count = len(users_response.data)
                            if supabase_user_count == 0:
                                self.stdout.write(self.style.SUCCESS("✅ Supabase database is clean (0 users)"))
                            else:
                                self.stdout.write(self.style.ERROR(f"❌ Supabase has {supabase_user_count} users"))
                                # Print user emails
                                self.stdout.write("User emails in Supabase:")
                                for user in users_response.data:
                                    if 'email' in user:
                                        self.stdout.write(f" - {user['email']}")
                        else:
                            self.stdout.write(self.style.ERROR("❌ Unable to determine Supabase user count"))
                    except Exception as client_error:
                        self.stdout.write(self.style.ERROR(f"❌ Error checking Supabase users via client: {str(client_error)}"))
            else:
                self.stdout.write(self.style.ERROR("❌ No Supabase admin client available. Cannot check Supabase users."))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error accessing Supabase: {str(e)}"))
            
        # Print summary
        if django_user_count == 0:
            self.stdout.write(self.style.SUCCESS("\n✅ Django database is clean and ready for new registrations"))
        else:
            self.stdout.write(self.style.ERROR("\n❌ Django still has users - run 'python manage.py cleanup_users --confirm' to clean it"))
            
        self.stdout.write("\nTo register a new user, go to: http://127.0.0.1:8000/auth/register/")
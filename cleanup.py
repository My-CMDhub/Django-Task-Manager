import os
import sys
import django
from dotenv import load_dotenv

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
load_dotenv()
django.setup()

# Import Django models and Supabase utils
from auth_app.models import User
from auth_app.views import delete_supabase_user, get_supabase_admin_client

def clear_all_users():
    """
    Remove all users from both Django and Supabase systems
    """
    # Get all users from Django
    users = User.objects.all()
    email_list = [user.email for user in users]
    
    print(f"Found {len(email_list)} users in Django database:")
    for email in email_list:
        print(f" - {email}")
    
    # Ask for confirmation
    confirm = input("\nAre you sure you want to delete ALL users? This cannot be undone. (yes/no): ")
    if confirm.lower() != 'yes':
        print("Operation cancelled.")
        return
    
    # Delete users from Django
    print("\nDeleting users from Django...")
    User.objects.all().delete()
    print(f"Deleted {len(email_list)} users from Django")
    
    # Delete users from Supabase
    print("\nDeleting users from Supabase...")
    for email in email_list:
        print(f"Attempting to delete {email} from Supabase...")
        result = delete_supabase_user(email)
        print(f" - {'Success' if result else 'Failed or not found'}")
    
    print("\nCleanup complete. All users have been removed from the system.")
    print("You can now register fresh accounts.")

if __name__ == "__main__":
    clear_all_users() 
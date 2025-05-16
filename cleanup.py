import os
import sys
import django
from dotenv import load_dotenv
import requests  # Added for direct API calls
import logging

# Setup Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
load_dotenv()
django.setup()

# Import Django models and Supabase utils
from django.conf import settings  # Added to access Supabase settings
from auth_app.models import User
# We won't use the old delete_supabase_user function anymore from views
# from auth_app.views import delete_supabase_user, get_supabase_admin_client

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def clear_all_users():
    """
    Remove all users from both Django and Supabase systems,
    fetching users directly from Supabase for deletion.
    """
    
    # --- Supabase Deletion ---
    logger.info("Attempting to delete all users from Supabase...")
    supabase_users_deleted = 0
    supabase_deletion_failed = 0
    
    try:
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
            logger.error("Supabase URL or Service Key not configured in settings.")
            raise ValueError("Supabase credentials missing.")

        headers = {
            "apikey": settings.SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
        }
        list_users_url = f"{settings.SUPABASE_URL}/auth/v1/admin/users"

        response = requests.get(list_users_url, headers=headers, timeout=15)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

        users_data = response.json()
        # Supabase might return {'users': [], 'aud': '...', ...} or just a list []
        supabase_user_list = users_data.get('users', []) if isinstance(users_data, dict) else users_data

        if not supabase_user_list:
            logger.info("No users found in Supabase.")
        else:
            logger.info(f"Found {len(supabase_user_list)} users in Supabase. Proceeding with deletion...")
    
            # Ask for confirmation before Supabase deletion
            confirm = input(f"\nAre you sure you want to delete ALL {len(supabase_user_list)} users from Supabase? This cannot be undone. (yes/no): ")
    if confirm.lower() != 'yes':
                logger.info("Supabase deletion cancelled by user.")
        print("Operation cancelled.")
        return
    
            for user in supabase_user_list:
                user_id = user.get('id')
                user_email = user.get('email', 'N/A')
                if user_id:
                    logger.info(f"Attempting to delete Supabase user ID: {user_id} (Email: {user_email})")
                    delete_url = f"{settings.SUPABASE_URL}/auth/v1/admin/users/{user_id}"
                    try:
                        delete_response = requests.delete(delete_url, headers=headers, timeout=10)
                        if delete_response.status_code in [200, 204]:
                            logger.info(f"Successfully deleted Supabase user ID: {user_id}")
                            supabase_users_deleted += 1
                        else:
                            logger.error(f"Failed to delete Supabase user ID: {user_id}. Status: {delete_response.status_code}, Response: {delete_response.text}")
                            supabase_deletion_failed += 1
                    except requests.exceptions.RequestException as delete_err:
                        logger.error(f"Error deleting Supabase user ID: {user_id}. Error: {delete_err}")
                        supabase_deletion_failed += 1
                else:
                    logger.warning(f"Could not find ID for Supabase user: {user_email}")
                    supabase_deletion_failed += 1
            
            logger.info(f"Supabase Deletion Summary: {supabase_users_deleted} deleted, {supabase_deletion_failed} failed.")

    except requests.exceptions.Timeout:
        logger.error("Timeout connecting to Supabase API.")
        supabase_deletion_failed = -1 # Indicate general API failure
    except requests.exceptions.RequestException as req_err:
        logger.error(f"Error communicating with Supabase API: {req_err}")
        supabase_deletion_failed = -1 # Indicate general API failure
    except Exception as e:
        logger.error(f"An unexpected error occurred during Supabase cleanup: {e}")
        supabase_deletion_failed = -1 # Indicate general API failure

    if supabase_deletion_failed > 0 :
         print(f"\nWarning: Failed to delete {supabase_deletion_failed} users from Supabase. Check logs.")
    elif supabase_deletion_failed == -1:
         print(f"\nWarning: Could not complete Supabase user deletion due to API errors. Check logs.")
    else:
         print(f"\nSuccessfully deleted {supabase_users_deleted} users from Supabase.")


    # --- Django Deletion ---
    django_users = User.objects.all()
    django_user_count = django_users.count()
    
    print(f"\nFound {django_user_count} users in Django database.")
    
    if django_user_count > 0:
        # Ask for confirmation for Django deletion
        confirm_django = input(f"Are you sure you want to delete ALL {django_user_count} users from Django? (yes/no): ")
        if confirm_django.lower() != 'yes':
            print("Django deletion cancelled.")
        else:
            print("Deleting users from Django...")
            deleted_count, _ = User.objects.all().delete()
            print(f"Deleted {deleted_count} users from Django.")
    else:
        print("No users found in Django to delete.")
    
    print("\nCleanup process finished.")
    if supabase_deletion_failed != 0 or django_user_count > 0 and confirm_django.lower() != 'yes':
         print("Please review logs and statuses above. Some cleanup steps may have been skipped or failed.")
    else:
        print("All users should now be removed from the system.")
    print("You can now register fresh accounts.")

if __name__ == "__main__":
    clear_all_users() 
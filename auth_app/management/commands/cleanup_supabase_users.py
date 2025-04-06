from django.core.management.base import BaseCommand
import os
import logging
import requests
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Clean up all users from Supabase using REST API directly'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm deletion without prompting',
        )

    def handle(self, *args, **options):
        confirm = options['confirm']
        
        # Get required environment variables or command arguments
        supabase_url = os.environ.get('SUPABASE_URL', '')
        service_key = os.environ.get('SUPABASE_SERVICE_KEY', '')
        
        # If environment variables not available, use the hard-coded values
        # IMPORTANT: These should be used only for development and testing
        if not supabase_url:
            supabase_url = "https://***REMOVED***.supabase.co"
            self.stdout.write(self.style.WARNING(f"Using hard-coded Supabase URL: {supabase_url}"))
        
        if not service_key:
            service_key = "***REMOVED***"
            self.stdout.write(self.style.WARNING("Using hard-coded service key (for development only)"))

        if not supabase_url or not service_key:
            self.stdout.write(self.style.ERROR("Missing Supabase URL or service role key."))
            return
        
        # Get list of users from Supabase
        headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json"
        }
        
        # Construct the Auth API URL
        auth_api_url = f"{supabase_url}/auth/v1/admin/users"
        
        try:
            # First, let's list all users
            response = requests.get(auth_api_url, headers=headers)
            
            if response.status_code != 200:
                self.stdout.write(self.style.ERROR(f"Failed to list users: {response.status_code} - {response.text}"))
                return
            
            # Parse the JSON response
            try:
                users_data = response.json()
                # Check the structure of the response
                self.stdout.write(f"Response structure: {type(users_data)}")
                
                # Handle different response structures
                if isinstance(users_data, dict) and 'users' in users_data:
                    users = users_data['users']
                elif isinstance(users_data, list):
                    users = users_data
                else:
                    # Print the full response for debugging
                    self.stdout.write(f"Unexpected response format: {json.dumps(users_data, indent=2)}")
                    users = []
                    
                    # Try to extract users from the response
                    if isinstance(users_data, dict):
                        for key, value in users_data.items():
                            if isinstance(value, list) and value and isinstance(value[0], dict) and 'email' in value[0]:
                                users = value
                                self.stdout.write(f"Found users array in key: {key}")
                                break
            except json.JSONDecodeError:
                self.stdout.write(self.style.ERROR(f"Invalid JSON response: {response.text[:200]}..."))
                return
            
            user_count = len(users)
            
            if user_count == 0:
                self.stdout.write(self.style.SUCCESS("No users found in Supabase."))
                return
            
            # Print users that will be deleted
            self.stdout.write(f"Found {user_count} users in Supabase:")
            for user in users:
                if isinstance(user, dict):
                    email = user.get('email', 'No email')
                    user_id = user.get('id', 'No ID')
                    self.stdout.write(f"- {email} (ID: {user_id})")
                else:
                    self.stdout.write(f"- Invalid user format: {user}")
            
            # Confirm deletion
            if not confirm:
                confirmation = input(f"Are you sure you want to delete all {user_count} users? (yes/no): ")
                if confirmation.lower() != 'yes':
                    self.stdout.write(self.style.WARNING("Operation cancelled."))
                    return
            
            # Delete each user
            deleted_count = 0
            for user in users:
                if not isinstance(user, dict):
                    self.stdout.write(self.style.WARNING(f"Skipping invalid user format: {user}"))
                    continue
                    
                user_id = user.get('id')
                email = user.get('email', 'unknown')
                
                if not user_id:
                    self.stdout.write(self.style.WARNING(f"Skipping user with no ID: {email}"))
                    continue
                
                # Make DELETE request to delete user
                delete_url = f"{auth_api_url}/{user_id}"
                delete_response = requests.delete(delete_url, headers=headers)
                
                if delete_response.status_code in (200, 204):
                    self.stdout.write(self.style.SUCCESS(f"Deleted user: {email}"))
                    deleted_count += 1
                else:
                    self.stdout.write(self.style.ERROR(
                        f"Failed to delete user {email}: {delete_response.status_code} - {delete_response.text}"
                    ))
            
            self.stdout.write(self.style.SUCCESS(f"Successfully deleted {deleted_count} of {user_count} users from Supabase."))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error: {str(e)}")) 
import os
import sys
import json
import time
import requests
import sqlite3
import threading
import subprocess
from datetime import datetime

# Set up logging
WEBHOOK_LOG_FILE = os.path.join('logs', 'webhook.log')
MONITOR_LOG_FILE = os.path.join('logs', 'user_monitor.log')
SYNC_LOG_FILE = os.path.join('logs', 'sync.log')

# ANSI color codes
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
RED = '\033[0;31m'
CYAN = '\033[0;36m'
MAGENTA = '\033[0;35m'
NC = '\033[0m'  # No Color

# Load environment variables from .env file
def load_env():
    env_vars = {}
    try:
        with open('.env', 'r') as f:
            for line in f:
                if '=' in line and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    env_vars[key] = value
        return env_vars
    except Exception as e:
        print(f"{RED}Error loading .env file: {str(e)}{NC}")
        return {}

env_vars = load_env()
SUPABASE_URL = env_vars.get('SUPABASE_URL', '')
SUPABASE_SERVICE_KEY = env_vars.get('SUPABASE_SERVICE_KEY', '')
NGROK_URL = env_vars.get('NGROK_URL', '')

# Connect to Django database
def get_django_user_count():
    try:
        # Connect to SQLite database
        conn = sqlite3.connect('db.sqlite3')
        cursor = conn.cursor()
        
        # Check if deleted_at column exists
        cursor.execute("PRAGMA table_info(auth_app_user)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Count users that are not deleted
        if 'deleted_at' in columns:
            cursor.execute("SELECT COUNT(*) FROM auth_app_user WHERE deleted_at IS NULL")
        else:
            cursor.execute("SELECT COUNT(*) FROM auth_app_user")
        count = cursor.fetchone()[0]
        
        # Get user details - adapt query based on available columns
        if 'email_verified' in columns:
            if 'deleted_at' in columns:
                cursor.execute("SELECT email, date_joined, last_login, email_verified FROM auth_app_user WHERE deleted_at IS NULL")
            else:
                cursor.execute("SELECT email, date_joined, last_login, email_verified FROM auth_app_user")
        else:
            if 'deleted_at' in columns:
                cursor.execute("SELECT email, date_joined, last_login FROM auth_app_user WHERE deleted_at IS NULL")
            else:
                cursor.execute("SELECT email, date_joined, last_login FROM auth_app_user")
        users = cursor.fetchall()
        
        conn.close()
        return count, users
    except Exception as e:
        print(f"{RED}Error getting Django user count: {str(e)}{NC}")
        return 0, []

# Get details of Django users for comparison
def get_django_users_detailed():
    try:
        conn = sqlite3.connect('db.sqlite3')
        cursor = conn.cursor()
        
        # Check schema first
        cursor.execute("PRAGMA table_info(auth_app_user)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Build query based on available columns
        select_fields = ["id", "email", "username"]
        where_clause = ""
        
        if 'supabase_id' in columns:
            select_fields.append("supabase_id")
        else:
            select_fields.append("NULL as supabase_id")
            
        if 'email_verified' in columns:
            select_fields.append("email_verified")
        else:
            select_fields.append("0 as email_verified")
            
        select_fields.append("date_joined")
        
        if 'deleted_at' in columns:
            where_clause = "WHERE deleted_at IS NULL"
        
        # Construct and execute the query
        query = f"""
            SELECT {', '.join(select_fields)} 
            FROM auth_app_user 
            {where_clause}
        """
        
        cursor.execute(query)
        
        users = {}
        for row in cursor.fetchall():
            row_data = list(row)
            user_id, email = row_data[0:2]
            
            # Create a dictionary dynamically based on the order of select_fields
            user_dict = {
                'id': user_id,
                'email': email,
                'username': row_data[2]
            }
            
            idx = 3
            if 'supabase_id' in select_fields:
                user_dict['supabase_id'] = row_data[idx]
                idx += 1
                
            if 'email_verified' in select_fields:
                user_dict['email_verified'] = row_data[idx]
                idx += 1
                
            user_dict['date_joined'] = row_data[idx]
            
            users[email.lower()] = user_dict
        
        conn.close()
        return users
    except Exception as e:
        print(f"{RED}Error getting detailed Django users: {str(e)}{NC}")
        return {}

# Direct deletion of Django users that don't exist in Supabase
def delete_django_user(email):
    try:
        conn = sqlite3.connect('db.sqlite3')
        cursor = conn.cursor()
        
        # First check if user exists
        cursor.execute("SELECT id FROM auth_app_user WHERE email = ?", (email,))
        user_id = cursor.fetchone()
        
        if user_id:
            user_id = user_id[0]
            
            # Always perform hard delete to ensure user is actually removed
            # Delete related user profile first if it exists
            cursor.execute("SELECT id FROM auth_app_userprofile WHERE user_id = ?", (user_id,))
            profile_id = cursor.fetchone()
            if profile_id:
                cursor.execute("DELETE FROM auth_app_userprofile WHERE user_id = ?", (user_id,))
                conn.commit()
                print(f"{GREEN}✓ Deleted Django user profile for: {email}{NC}")
            
            # Now delete the user
            cursor.execute("DELETE FROM auth_app_user WHERE id = ?", (user_id,))
            conn.commit()
            print(f"{GREEN}✓ Completely deleted Django user: {email}{NC}")
            
            conn.close()
            return True
        else:
            conn.close()
            print(f"{YELLOW}Django user not found: {email}{NC}")
            return False
    except Exception as e:
        print(f"{RED}Error deleting Django user {email}: {str(e)}{NC}")
        return False

# Direct creation of Django user that exists in Supabase but not in Django
def create_django_user(email, supabase_id, username=None):
    try:
        conn = sqlite3.connect('db.sqlite3')
        cursor = conn.cursor()
        
        # Check if user already exists (shouldn't happen, but check anyway)
        cursor.execute("SELECT id FROM auth_app_user WHERE email = ?", (email,))
        if cursor.fetchone():
            conn.close()
            print(f"{YELLOW}Django user already exists: {email}{NC}")
            return False
            
        # Generate a username if none provided
        if not username:
            username = email.split('@')[0]
            
            # Make sure username is unique
            count = 0
            base_username = username
            while True:
                cursor.execute("SELECT id FROM auth_app_user WHERE username = ?", (username,))
                if not cursor.fetchone():
                    break
                count += 1
                username = f"{base_username}{count}"
        
        # Generate a random password
        import random
        import string
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        
        # For password hashing, we'll use Django's standard method
        # But for direct DB access, we'll create a simplified version:
        from hashlib import pbkdf2_hmac
        salt = os.urandom(16).hex()
        hashed_password = pbkdf2_hmac(
            'sha256', 
            password.encode('utf-8'), 
            salt.encode('utf-8'), 
            150000
        ).hex()
        password_string = f"pbkdf2_sha256$150000${salt}${hashed_password}"
        
        # Get current time
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Check table schema to determine available columns
        cursor.execute("PRAGMA table_info(auth_app_user)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Prepare base fields that should always exist
        fields = ["username", "email", "password", "is_active", "is_staff", "is_superuser", "date_joined"]
        values = [username, email, password_string, 1, 0, 0, now]
        
        # Add all custom fields that might be required by the User model
        field_mapping = {
            'supabase_id': supabase_id,
            'email_verified': 1,  # Assume verified from Supabase
            'created_at': now,
            'first_name': "",     # Default empty string
            'last_name': "",      # Default empty string
            'last_password_change': now,
            'failed_login_attempts': 0,
            'requires_password_change': 0,
            'mfa_enabled': 0,
        }
        
        # Add fields from mapping if they exist in schema
        for field, value in field_mapping.items():
            if field in columns:
                fields.append(field)
                values.append(value)
                
        # Build the SQL query dynamically
        placeholders = ", ".join(["?" for _ in fields])
        fields_str = ", ".join(fields)
        
        query = f"INSERT INTO auth_app_user ({fields_str}) VALUES ({placeholders})"
        cursor.execute(query, values)
        
        user_id = cursor.lastrowid
        conn.commit()
        
        # Check if UserProfile table exists and create a profile if needed
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='auth_app_userprofile'")
        if cursor.fetchone():
            # Check UserProfile schema
            cursor.execute("PRAGMA table_info(auth_app_userprofile)")
            profile_columns = [col[1] for col in cursor.fetchall()]
            
            # Prepare base fields
            profile_fields = ["user_id"]
            profile_values = [user_id]
            
            # Add additional fields if they exist
            profile_field_mapping = {
                'supabase_uid': supabase_id,
                'verified': 1,
                'created_at': now,
                'last_synced': now,
            }
            
            # Add fields from mapping if they exist in schema
            for field, value in profile_field_mapping.items():
                if field in profile_columns:
                    profile_fields.append(field)
                    profile_values.append(value)
                
            # Build and execute profile insertion query
            profile_placeholders = ", ".join(["?" for _ in profile_fields])
            profile_fields_str = ", ".join(profile_fields)
            
            profile_query = f"INSERT INTO auth_app_userprofile ({profile_fields_str}) VALUES ({profile_placeholders})"
            cursor.execute(profile_query, profile_values)
            conn.commit()
        
        conn.close()
        print(f"{GREEN}✓ Completely created Django user: {email} (Supabase ID: {supabase_id}){NC}")
        return True
    except Exception as e:
        print(f"{RED}Error creating Django user {email}: {str(e)}{NC}")
        return False

# Get Supabase user count
def get_supabase_user_count():
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print(f"{YELLOW}Warning: Supabase URL or service key not found in .env file{NC}")
        return 0, []
    
    try:
        headers = {
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/json"
        }
        
        # Construct the Auth API URL
        auth_api_url = f"{SUPABASE_URL}/auth/v1/admin/users"
        response = requests.get(auth_api_url, headers=headers)
        
        if response.status_code != 200:
            print(f"{RED}Failed to list Supabase users: {response.status_code} - {response.text}{NC}")
            return 0, []
        
        users_data = response.json()
        
        # Handle different response structures
        if isinstance(users_data, dict) and 'users' in users_data:
            users = users_data['users']
        elif isinstance(users_data, list):
            users = users_data
        else:
            print(f"{RED}Unexpected response format from Supabase{NC}")
            return 0, []
        
        return len(users), users
    except Exception as e:
        print(f"{RED}Error getting Supabase user count: {str(e)}{NC}")
        return 0, []

# Get details of Supabase users for comparison
def get_supabase_users_detailed():
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return {}
    
    try:
        headers = {
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/json"
        }
        
        auth_api_url = f"{SUPABASE_URL}/auth/v1/admin/users"
        response = requests.get(auth_api_url, headers=headers)
        
        if response.status_code != 200:
            return {}
        
        users_data = response.json()
        
        if isinstance(users_data, dict) and 'users' in users_data:
            users_list = users_data['users']
        elif isinstance(users_data, list):
            users_list = users_data
        else:
            return {}
        
        # Create a dictionary of users by email
        users = {}
        for user in users_list:
            email = user.get('email', '').lower()
            if email:
                users[email] = {
                    'id': user.get('id'),
                    'email': email,
                    'email_verified': bool(user.get('email_confirmed_at')),
                    'created_at': user.get('created_at'),
                    'raw_user_meta_data': user.get('raw_user_meta_data', {})
                }
        
        return users
    except Exception as e:
        print(f"{RED}Error getting detailed Supabase users: {str(e)}{NC}")
        return {}

# Compare users between systems and identify discrepancies with Supabase priority
def compare_users():
    django_users = get_django_users_detailed()
    supabase_users = get_supabase_users_detailed()
    
    discrepancies = []
    prioritize_supabase = []
    
    # First check for users in Django but not in Supabase
    # These should be DELETED from Django to match Supabase (Supabase is source of truth)
    for email, django_user in django_users.items():
        if email not in supabase_users:
            discrepancies.append(f"User {email} exists in Django but not in Supabase")
            prioritize_supabase.append(f"delete_from_django:{email}")
        else:
            # Check for mismatched Supabase IDs
            django_supabase_id = django_user.get('supabase_id')
            supabase_id = supabase_users[email].get('id')
            if django_supabase_id and supabase_id and django_supabase_id != supabase_id:
                discrepancies.append(f"User {email} has mismatched Supabase IDs: Django={django_supabase_id}, Supabase={supabase_id}")
                prioritize_supabase.append(f"update_django_id:{email}:{supabase_id}")
    
    # Then check for users in Supabase but not in Django
    # These should be ADDED to Django to match Supabase
    for email, supabase_user in supabase_users.items():
        if email not in django_users:
            discrepancies.append(f"User {email} exists in Supabase but not in Django")
            prioritize_supabase.append(f"add_to_django:{email}:{supabase_user['id']}")
    
    return discrepancies, prioritize_supabase

# Direct synchronization actions
def perform_direct_actions(actions):
    success_count = 0
    failure_count = 0
    
    for action in actions:
        if action.startswith("delete_from_django:"):
            email = action.split(":", 1)[1]
            if delete_django_user(email):
                success_count += 1
            else:
                failure_count += 1
                
        elif action.startswith("add_to_django:"):
            parts = action.split(":")
            email = parts[1]
            supabase_id = parts[2]
            if create_django_user(email, supabase_id):
                success_count += 1
            else:
                failure_count += 1
    
    return success_count, failure_count

# Monitor webhook log file for events
def monitor_webhook_log():
    last_position = 0
    
    if not os.path.exists(WEBHOOK_LOG_FILE):
        with open(WEBHOOK_LOG_FILE, 'w') as f:
            pass  # Create empty file
    
    while True:
        try:
            with open(WEBHOOK_LOG_FILE, 'r') as f:
                f.seek(last_position)
                new_content = f.read()
                last_position = f.tell()
            
            if new_content:
                lines = new_content.strip().split('\n')
                for line in lines:
                    if line:
                        if "webhook" in line.lower():
                            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            print(f"\n{BLUE}[{timestamp}] Webhook event detected:{NC}")
                            print(f"{CYAN}{line}{NC}")
                            
                            # Wait a moment for the database to update
                            time.sleep(1)
                            
                            # Show updated counts and perform sync if needed
                            is_synced, priority_actions = display_user_counts()
                            if not is_synced:
                                print(f"{YELLOW}Detected user count mismatch after webhook event. Performing immediate direct synchronization...{NC}")
                                
                                # First try direct actions for immediate effect
                                success, failure = perform_direct_actions(priority_actions)
                                print(f"{CYAN}Direct actions: {success} successful, {failure} failed{NC}")
                                
                                # Then run the sync command to handle any complex cases
                                if failure > 0:
                                    perform_sync(priority_actions)
                                
                                # Display counts again after sync
                                time.sleep(1)
                                display_user_counts()
        except Exception as e:
            print(f"{RED}Error monitoring webhook log: {str(e)}{NC}")
        
        time.sleep(2)  # Check every 2 seconds

# Perform automatic synchronization prioritizing Supabase
def perform_sync(priority_actions=None):
    print(f"{MAGENTA}Starting automatic user synchronization...{NC}")
    
    try:
        with open(SYNC_LOG_FILE, 'a') as log_file:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_file.write(f"\n[{timestamp}] Running automatic synchronization\n")
            
            # If we have priority actions, perform a directed sync
            if priority_actions and len(priority_actions) > 0:
                log_file.write(f"[{timestamp}] Priority actions needed: {len(priority_actions)}\n")
                for action in priority_actions:
                    log_file.write(f"[{timestamp}] Action: {action}\n")
                
                # First try direct actions for immediate effect
                success, failure = perform_direct_actions(priority_actions)
                log_file.write(f"[{timestamp}] Direct actions: {success} successful, {failure} failed\n")
                
                # Only run the command if direct actions failed
                if failure > 0:
                    # Run sync with to-django direction to respect Supabase as source of truth
                    subprocess.run(
                        ["python", "manage.py", "sync_users", "--direction=to-django", "--force"],
                        stdout=log_file,
                        stderr=subprocess.STDOUT
                    )
            else:
                # Default sync but prioritize Supabase direction
                subprocess.run(
                    ["python", "manage.py", "sync_users", "--direction=to-django", "--force"],
                    stdout=log_file,
                    stderr=subprocess.STDOUT
                )
            
            log_file.write(f"[{timestamp}] Synchronization completed\n")
        
        print(f"{GREEN}Automatic synchronization completed. See {SYNC_LOG_FILE} for details.{NC}")
        return True
    except Exception as e:
        print(f"{RED}Error during automatic synchronization: {str(e)}{NC}")
        return False

# Display user counts
def display_user_counts():
    django_count, django_users = get_django_user_count()
    supabase_count, supabase_users = get_supabase_user_count()
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    print(f"\n{BLUE}[{timestamp}] User Count:{NC}")
    print(f"{GREEN}Found {supabase_count} user(s) in Supabase{NC}")
    print(f"{GREEN}Found {django_count} user(s) in Django{NC}")
    
    # Get user emails for detailed comparison
    django_emails = set()
    for user in django_users:
        if isinstance(user, tuple) and len(user) > 0:
            django_emails.add(user[0].lower())
    
    supabase_emails = set()
    for user in supabase_users:
        email = user.get('email', '').lower()
        if email:
            supabase_emails.add(email)
    
    # Check synchronization status - both count and actual users
    count_synced = django_count == supabase_count
    users_synced = django_emails == supabase_emails
    is_synced = count_synced and users_synced
    
    priority_actions = []
    
    if is_synced:
        print(f"{GREEN}✓ Systems are synchronized (same number of users with matching emails){NC}")
    else:
        if not count_synced:
            print(f"{YELLOW}⚠ User counts don't match: Django={django_count}, Supabase={supabase_count}{NC}")
        
        if not users_synced:
            print(f"{YELLOW}⚠ User email addresses don't match{NC}")
            
            # Show users in Django but not in Supabase
            django_only = django_emails - supabase_emails
            if django_only:
                print(f"{YELLOW}Users in Django but not in Supabase:{NC}")
                for email in django_only:
                    print(f"{YELLOW}  - {email}{NC}")
            
            # Show users in Supabase but not in Django
            supabase_only = supabase_emails - django_emails
            if supabase_only:
                print(f"{YELLOW}Users in Supabase but not in Django:{NC}")
                for email in supabase_only:
                    print(f"{YELLOW}  - {email}{NC}")
        
        # Get more detailed information about discrepancies
        discrepancies, priority_actions = compare_users()
        if discrepancies:
            print(f"{YELLOW}Detected discrepancies:{NC}")
            for issue in discrepancies:
                print(f"{YELLOW}  - {issue}{NC}")
                
        if priority_actions:
            print(f"{CYAN}Supabase will be treated as the source of truth{NC}")
    
    # Log to monitor file
    with open(MONITOR_LOG_FILE, 'a') as f:
        f.write(f"[{timestamp}] Supabase: {supabase_count}, Django: {django_count}, Same Users: {users_synced}, Fully Synced: {is_synced}\n")
    
    # Return True if synchronized and the priority actions
    return is_synced, priority_actions

# Send test webhook to verify setup
def send_test_webhook():
    if not NGROK_URL:
        print(f"{RED}Error: NGROK_URL not found in .env file{NC}")
        return False
    
    try:
        webhook_url = f"{NGROK_URL}/auth/test-webhook/"
        response = requests.post(webhook_url, json={
            "type": "test",
            "event": "user.test",
            "timestamp": datetime.now().isoformat()
        })
        
        if response.status_code == 200:
            print(f"{GREEN}Test webhook sent successfully to {webhook_url}{NC}")
            return True
        else:
            print(f"{RED}Failed to send test webhook: {response.status_code} - {response.text}{NC}")
            return False
    except Exception as e:
        print(f"{RED}Error sending test webhook: {str(e)}{NC}")
        return False

# Periodic monitoring with automatic synchronization
def periodic_monitor():
    sync_interval = 60  # seconds between full sync checks
    last_full_sync = time.time() - sync_interval  # start with immediate sync
    
    while True:
        # Check if user counts match
        is_synced, priority_actions = display_user_counts()
        
        # Perform a full sync periodically or if systems are out of sync
        current_time = time.time()
        if not is_synced or (current_time - last_full_sync >= sync_interval):
            if not is_synced:
                print(f"{YELLOW}User count mismatch detected. Initiating synchronization...{NC}")
                print(f"{CYAN}Supabase will be treated as the source of truth{NC}")
                
                # Try direct actions first for immediate effect
                success, failure = perform_direct_actions(priority_actions)
                print(f"{CYAN}Direct actions: {success} successful, {failure} failed{NC}")
                
                # Only run the command if direct actions failed
                if failure > 0:
                    perform_sync(priority_actions)
            else:
                print(f"{BLUE}Running periodic synchronization check...{NC}")
                perform_sync(priority_actions)
                
            last_full_sync = time.time()
        
        # Wait before next check
        time.sleep(30)  # Check every 30 seconds

# Main function
def main():
    print(f"{BLUE}Starting Enhanced User Monitoring and Synchronization...{NC}")
    print(f"{CYAN}Supabase is the source of truth - Django will sync to match Supabase{NC}")
    
    # Create log files if they don't exist
    for log_file in [WEBHOOK_LOG_FILE, MONITOR_LOG_FILE, SYNC_LOG_FILE]:
        if not os.path.exists(log_file):
            with open(log_file, 'w') as f:
                pass
    
    # Send a test webhook to verify setup
    print(f"{YELLOW}Testing webhook functionality...{NC}")
    send_test_webhook()
    
    # Start webhook log monitoring in a separate thread
    webhook_thread = threading.Thread(target=monitor_webhook_log, daemon=True)
    webhook_thread.start()
    
    # Start periodic monitoring in a separate thread
    monitor_thread = threading.Thread(target=periodic_monitor, daemon=True)
    monitor_thread.start()
    
    # Display initial counts
    synchronized, priority_actions = display_user_counts()
    
    if not synchronized:
        print(f"\n{YELLOW}Warning: Django and Supabase user counts don't match.{NC}")
        print(f"{YELLOW}Running initial synchronization from Supabase to Django...{NC}")
        print(f"{CYAN}Supabase will be treated as the source of truth{NC}")
        
        # First try direct actions for immediate effect
        success, failure = perform_direct_actions(priority_actions)
        print(f"{CYAN}Direct actions: {success} successful, {failure} failed{NC}")
        
        # Only run the command if direct actions failed
        if failure > 0:
            perform_sync(priority_actions)
        
        # Check again after sync
        time.sleep(2)
        synchronized, _ = display_user_counts()
        
        if not synchronized:
            print(f"{YELLOW}Systems still not synchronized after initial sync. Check logs for details.{NC}")
        else:
            print(f"{GREEN}Initial synchronization successful!{NC}")
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print(f"\n{BLUE}Stopping user monitoring...{NC}")

if __name__ == "__main__":
    main()

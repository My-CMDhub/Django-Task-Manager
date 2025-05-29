#!/usr/bin/env python
import os
import sys
import django

# Set up Django environment
os.environ.setdefault('DJANGO_ENV', 'production')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.production_settings')
django.setup()

# Now import your Supabase utilities
from mysite.supabase_utils import get_supabase_admin_client

# Get the admin client
client = get_supabase_admin_client()
print(f"Client type: {type(client)}")

# Try to list users
try:
    response = client.auth.admin.list_users()
    print(f"Response type: {type(response)}")
    print(f"Response dir: {dir(response)}")
    print(f"Response: {response}")
    
    # Try to access as a list
    if isinstance(response, list):
        print(f"Users count: {len(response)}")
        if response:
            print(f"First user: {response[0]}")
            print(f"First user dir: {dir(response[0])}")
    else:
        print("Response is not a list")
        
except Exception as e:
    print(f"Error: {e}")

# Try to create a user
try:
    test_email = f"test{os.urandom(4).hex()}@example.com"
    print(f"Creating test user with email: {test_email}")
    create_response = client.auth.admin.create_user({
        "email": test_email,
        "password": "password123",
        "email_confirm": True,
        "user_metadata": {
            "username": "testuser",
            "registered_via": "test_script"
        }
    })
    print(f"Create response: {create_response}")
    print(f"Create response dir: {dir(create_response)}")
except Exception as e:
    print(f"Error creating user: {e}") 
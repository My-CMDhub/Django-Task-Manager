#!/usr/bin/env python
"""
Script to fix database path issues in production
"""
import os
import sys

# Check if we're in production environment
if os.environ.get('RENDER') == 'true':
    print("Running in Render production environment")
    
    # Ensure the database directory exists
    db_dir = '/opt/render/project/src/'
    print(f"Checking if database directory exists: {db_dir}")
    
    if not os.path.exists(db_dir):
        print(f"Error: Database directory does not exist: {db_dir}")
        sys.exit(1)
    
    # Check if we have write permissions
    try:
        test_file = os.path.join(db_dir, 'test_write.tmp')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        print(f"Successfully wrote to directory: {db_dir}")
    except Exception as e:
        print(f"Error: Cannot write to database directory: {e}")
        sys.exit(1)
    
    # All checks passed
    print("Database directory exists and is writable")
    print("You can now run migrations with:")
    print("python manage.py migrate")
    
else:
    print("Not running in production environment")
    print("This script is intended for use in the Render production environment only")

print("\nTo test email verification without database access, run:")
print("python test_email_verification.py your-email@example.com") 
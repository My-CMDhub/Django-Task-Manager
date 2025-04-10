import os
import django

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

from auth_app.models import User

# Check if admin already exists
admin_username = 'admin'
admin_email = 'admin@example.com'
admin_password = 'admin1234'  # Use a strong password in production

try:
    admin_user = User.objects.get(username=admin_username)
    print(f"Admin user already exists with username: {admin_username}")
    
    # Update permissions
    admin_user.is_staff = True
    admin_user.is_superuser = True
    admin_user.email_verified = True
    admin_user.set_password(admin_password)
    admin_user.save()
    print("Admin user permissions updated")
    
except User.DoesNotExist:
    # Create new admin user
    admin_user = User.objects.create_user(
        username=admin_username,
        email=admin_email,
        password=admin_password
    )
    admin_user.is_staff = True
    admin_user.is_superuser = True
    admin_user.email_verified = True
    admin_user.save()
    print(f"Created new admin user: {admin_username}")

print("Admin credentials:")
print(f"Username: {admin_username}")
print(f"Password: {admin_password}")
print(f"Email: {admin_email}")
print("Login at: http://127.0.0.1:8000/admin/") 
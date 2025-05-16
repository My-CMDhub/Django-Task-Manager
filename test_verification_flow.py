#!/usr/bin/env python
import os
import django
import uuid
import random
import string

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()

from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.core.mail import send_mail
from django.urls import reverse
from email.utils import make_msgid, formatdate

User = get_user_model()

def generate_random_username():
    """Generate a random username"""
    return ''.join(random.choices(string.ascii_lowercase, k=8))

def generate_random_email():
    """Generate a random email"""
    username = generate_random_username()
    return f"{username}@example.com"

def create_test_user():
    """Create a test user with email verification disabled"""
    email = generate_random_email()
    username = generate_random_username()
    password = "testpassword"
    
    # Create user with email_verified=False
    user = User.objects.create_user(
        username=username,
        email=email,
        password=password,
        email_verified=False,
        supabase_id=f"django-{str(uuid.uuid4())}"
    )
    
    print(f"Created test user: {username}, email: {email}")
    return user

def test_verification_email():
    """Test sending a verification email directly"""
    print("\n=== TESTING EMAIL VERIFICATION FLOW ===")
    
    # Check settings
    print(f"BYPASS_SUPABASE: {settings.BYPASS_SUPABASE}")
    print(f"AUTO_VERIFY_USERS: {getattr(settings, 'AUTO_VERIFY_USERS', False)}")
    
    # Create a test user
    user = create_test_user()
    
    # Generate a fake verification token and URL
    token = "test-verification-token"
    verify_url = f"http://127.0.0.1:8000/auth/verify-email/{token}/"
    
    # Prepare the email context
    context = {
        'user': user,
        'verify_url': verify_url,
        'site_name': 'Task Manager',
        'domain': '127.0.0.1:8000',
        'protocol': 'http',
        'current_year': timezone.now().year,
    }
    
    # Render the email templates
    try:
        html_email = render_to_string('emails/verification_email.html', context)
        text_email = strip_tags(html_email)  # Fallback plain text version
        
        # Prepare email headers
        msg_id = make_msgid(domain='127.0.0.1:8000')
        headers = {
            'Message-ID': msg_id,
            'Date': formatdate(localtime=True),
            'X-Priority': '1',
            'Importance': 'High',
            'List-Unsubscribe': f'<http://127.0.0.1:8000/auth/unsubscribe/?email={user.email}>',
        }
        
        # Send the email
        result = send_mail(
            f'Please Verify Your Email - Task Manager Account Activation',
            text_email,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            html_message=html_email,
            fail_silently=False,
        )
        
        print(f"Verification email sent: {result == 1}")
        
        # For testing, also send to the actual configured email
        if settings.EMAIL_HOST_USER:
            # Send to test email that actually exists
            result = send_mail(
                f'Task Manager Test - Please Verify Your Email',
                text_email,
                settings.DEFAULT_FROM_EMAIL,
                [settings.EMAIL_HOST_USER],  # Send to actual email
                html_message=html_email,
                fail_silently=False,
            )
            print(f"Verification email sent to actual email ({settings.EMAIL_HOST_USER}): {result == 1}")
        
    except Exception as e:
        print(f"Error sending verification email: {str(e)}")
    
    print("\nIf you received the email at either address, the verification flow is working!")
    return user

if __name__ == "__main__":
    test_verification_email() 
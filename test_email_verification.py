#!/usr/bin/env python
import os
import django
import uuid
import random
import string
import sys

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
os.environ["DJANGO_SETTINGS_MODULE"] = "mysite.production_settings"  # Use production settings
django.setup()

from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.core.mail import send_mail
from django.urls import reverse
from email.utils import make_msgid, formatdate
from auth_app.views import encode_verification_token

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
    
    # Print current settings to verify
    print(f"SITE_DOMAIN: {settings.SITE_DOMAIN}")
    print(f"SITE_URL: {settings.SITE_URL}")
    print(f"SENDER_NAME: {getattr(settings, 'SENDER_NAME', 'Not set')}")
    print(f"SENDER_EMAIL: {getattr(settings, 'SENDER_EMAIL', 'Not set')}")
    print(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
    
    # Create a test user
    user = create_test_user()
    
    # Generate a real verification token
    token = encode_verification_token(user.email)
    
    # Generate the verification URL
    verify_url = f"{settings.SITE_PROTOCOL}://{settings.SITE_DOMAIN}/auth/verify-email/{token}/"
    
    # Print the verification URL to see if it looks correct
    print(f"\nVerification URL: {verify_url}")
    
    # Prepare the email context
    context = {
        'user': user,
        'verify_url': verify_url,
        'site_name': 'Task Manager',
        'domain': settings.SITE_DOMAIN,
        'protocol': settings.SITE_PROTOCOL,
        'current_year': timezone.now().year,
    }
    
    # Render the email templates
    try:
        html_email = render_to_string('emails/verification_email.html', context)
        text_email = strip_tags(html_email)  # Fallback plain text version
        
        # Prepare email headers
        msg_id = make_msgid(domain=settings.SITE_DOMAIN)
        headers = {
            'Message-ID': msg_id,
            'Date': formatdate(localtime=True),
            'X-Priority': '1',
            'Importance': 'High',
            'List-Unsubscribe': f'<{settings.SITE_PROTOCOL}://{settings.SITE_DOMAIN}/auth/unsubscribe/?email={user.email}>',
        }
        
        # Send to test recipient if provided as command line argument
        recipient_email = sys.argv[1] if len(sys.argv) > 1 else user.email
        
        print(f"\nSending test email to: {recipient_email}")
        print(f"From: {settings.DEFAULT_FROM_EMAIL}")
        
        # Send the email
        result = send_mail(
            f'Please Verify Your Email - Task Manager Account Activation',
            text_email,
            settings.DEFAULT_FROM_EMAIL,
            [recipient_email],
            html_message=html_email,
            fail_silently=False,
            headers=headers
        )
        
        print(f"Verification email sent: {result == 1}")
        
    except Exception as e:
        print(f"Error sending verification email: {str(e)}")
    
    print("\nCheck your email to verify the production URLs and sender name are correct!")
    return user

if __name__ == "__main__":
    test_verification_email() 
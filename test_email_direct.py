#!/usr/bin/env python
import os
import sys
import django
from django.utils import timezone
from email.utils import make_msgid, formatdate

# Set Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()

# Import settings after Django is set up
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

def test_send_verification_email():
    """Send a test verification email with production-like settings"""
    print("\n=== TESTING EMAIL CONFIGURATION ===")
    
    # Use command line argument for recipient email or default
    recipient_email = sys.argv[1] if len(sys.argv) > 1 else "***REMOVED***"
    
    # Override settings with production values for testing
    settings.SITE_DOMAIN = "taskmanager-mztm.onrender.com"
    settings.SITE_PROTOCOL = "https"
    settings.SITE_URL = f"{settings.SITE_PROTOCOL}://{settings.SITE_DOMAIN}"
    
    # Set sender information
    settings.SENDER_NAME = "Task Manager"
    settings.SENDER_EMAIL = "***REMOVED***"
    settings.DEFAULT_FROM_EMAIL = f"{settings.SENDER_NAME} <{settings.SENDER_EMAIL}>"
    
    # Print current settings
    print(f"SITE_DOMAIN: {settings.SITE_DOMAIN}")
    print(f"SITE_URL: {settings.SITE_URL}")
    print(f"FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
    print(f"RECIPIENT: {recipient_email}")
    
    # Create a fake verification URL
    sample_token = "sample-verification-token-123456"
    verify_url = f"{settings.SITE_URL}/auth/verify-email/{sample_token}/"
    
    # Print the URL
    print(f"\nVerification URL will be: {verify_url}")
    
    # Prepare email context
    context = {
        'user': {'username': 'TestUser', 'email': recipient_email},
        'verify_url': verify_url,
        'site_name': 'Task Manager',
        'domain': settings.SITE_DOMAIN,
        'protocol': settings.SITE_PROTOCOL,
        'current_year': timezone.now().year,
    }
    
    # Render email
    try:
        html_email = render_to_string('emails/verification_email.html', context)
        text_email = strip_tags(html_email)
        
        # Prepare email headers
        msg_id = make_msgid(domain=settings.SITE_DOMAIN)
        headers = {
            'Message-ID': msg_id,
            'Date': formatdate(localtime=True),
            'X-Priority': '1',
            'Importance': 'High',
        }
        
        # Send the email
        print("\nSending test email...")
        result = send_mail(
            subject="Task Manager - Test Verification Email",
            message=text_email,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            html_message=html_email,
            fail_silently=False
        )
        
        if result == 1:
            print("✅ Test email sent successfully!")
            print(f"Check {recipient_email} to verify the sender name and verification URL are correct.")
        else:
            print("❌ Failed to send email!")
            
    except Exception as e:
        print(f"Error sending email: {str(e)}")

if __name__ == "__main__":
    test_send_verification_email() 
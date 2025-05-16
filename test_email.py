#!/usr/bin/env python
import os
import sys
import django

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()

from django.core.mail import send_mail
from django.conf import settings

def test_email():
    print("Email Configuration:")
    print(f"HOST: {settings.EMAIL_HOST}")
    print(f"PORT: {settings.EMAIL_PORT}")
    print(f"USER: {settings.EMAIL_HOST_USER}")
    print(f"SSL: {getattr(settings, 'EMAIL_USE_SSL', False)}")
    print(f"TLS: {getattr(settings, 'EMAIL_USE_TLS', False)}")
    print(f"FROM: {settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'Not set'}")
    
    print("\nAttempting to send test email...")
    
    try:
        from_email = settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else settings.EMAIL_HOST_USER
        to_email = settings.EMAIL_HOST_USER  # Send to yourself
        
        result = send_mail(
            subject="Test Email from Django",
            message="This is a test email sent from Django to verify the email configuration is working.",
            from_email=from_email,
            recipient_list=[to_email],
            fail_silently=False,
        )
        
        print(f"Email sent successfully! Result: {result}")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

if __name__ == "__main__":
    test_email() 
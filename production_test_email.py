#!/usr/bin/env python
"""
Script to test email configuration in production environment with detailed diagnostics
"""
import os
import sys
import traceback
import socket
import smtplib
import logging
import django
from collections import namedtuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('production_email_test')

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
os.environ["DJANGO_SETTINGS_MODULE"] = "mysite.production_settings"
django.setup()

from django.conf import settings
from django.core.mail import send_mail, get_connection
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from email.utils import make_msgid, formatdate

def test_email_direct():
    """Test email configuration directly with detailed diagnostics"""
    logger.info("=== PRODUCTION EMAIL TEST ===")
    
    # Check if recipient was provided
    if len(sys.argv) < 2:
        logger.error("Please provide recipient email as argument")
        logger.info("Usage: python production_test_email.py your-email@example.com")
        return False
    
    recipient = sys.argv[1]
    logger.info(f"Will send test email to: {recipient}")
    
    # Print detailed email settings for diagnosis
    logger.info("=== EMAIL CONFIGURATION ===")
    logger.info(f"EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
    logger.info(f"EMAIL_HOST: {settings.EMAIL_HOST}")
    logger.info(f"EMAIL_PORT: {settings.EMAIL_PORT}")
    logger.info(f"EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
    logger.info(f"EMAIL_USE_SSL: {settings.EMAIL_USE_SSL}")
    logger.info(f"EMAIL_TIMEOUT: {getattr(settings, 'EMAIL_TIMEOUT', 'Not set (will use default 30)')}")
    logger.info(f"SENDER_NAME: {getattr(settings, 'SENDER_NAME', 'Not set')}")
    logger.info(f"SENDER_EMAIL: {getattr(settings, 'SENDER_EMAIL', 'Not set')}")
    logger.info(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
    
    # Print important site settings
    logger.info("=== SITE CONFIGURATION ===")
    logger.info(f"SITE_DOMAIN: {settings.SITE_DOMAIN}")
    logger.info(f"SITE_PROTOCOL: {settings.SITE_PROTOCOL}")
    logger.info(f"SITE_URL: {settings.SITE_URL}")
    
    # Create a simple HTML message for testing
    html_message = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ padding: 20px; max-width: 600px; margin: 0 auto; }}
            .header {{ background-color: #4a69bd; color: white; padding: 10px 20px; text-align: center; }}
            .content {{ padding: 20px; background-color: #f9f9f9; }}
            .footer {{ text-align: center; margin-top: 20px; font-size: 12px; color: #999; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Email Test from {settings.SITE_DOMAIN}</h1>
            </div>
            <div class="content">
                <p>This is a test email sent from your Task Manager production environment.</p>
                <p>If you're seeing this email, your email configuration is working correctly.</p>
                <hr>
                <p><strong>Server Details:</strong></p>
                <ul>
                    <li>Domain: {settings.SITE_DOMAIN}</li>
                    <li>Protocol: {settings.SITE_PROTOCOL}</li>
                    <li>Sender: {settings.DEFAULT_FROM_EMAIL}</li>
                    <li>Time Sent: {formatdate(localtime=True)}</li>
                </ul>
                <p>You can now proceed with confidence that email notifications will work properly.</p>
            </div>
            <div class="footer">
                <p>This is an automated test email from your Task Manager application.</p>
            </div>
        </div>
    </body>
    </html>
    """
    text_message = strip_tags(html_message)
    
    # Prepare email headers for better deliverability
    msg_id = make_msgid(domain=settings.SITE_DOMAIN)
    headers = {
        'Message-ID': msg_id,
        'Date': formatdate(localtime=True),
        'X-Priority': '1',
        'Importance': 'High',
        'X-Test-Email': 'True',
    }
    
    try:
        logger.info("Creating email connection...")
        # Get connection with timeout
        connection = get_connection(
            backend=settings.EMAIL_BACKEND,
            host=settings.EMAIL_HOST,
            port=settings.EMAIL_PORT,
            username=settings.EMAIL_HOST_USER,
            password=settings.EMAIL_HOST_PASSWORD,
            use_tls=settings.EMAIL_USE_TLS,
            use_ssl=settings.EMAIL_USE_SSL,
            timeout=getattr(settings, 'EMAIL_TIMEOUT', 30)
        )
        
        logger.info(f"Sending email from {settings.DEFAULT_FROM_EMAIL} to {recipient}...")
        # Send the email
        result = send_mail(
            f'Test Email from {settings.SITE_DOMAIN}',
            text_message,
            settings.DEFAULT_FROM_EMAIL,
            [recipient],
            html_message=html_message,
            headers=headers,
            connection=connection,
            fail_silently=False
        )
        
        if result == 1:
            logger.info("✅ Email sent successfully!")
            logger.info(f"Check {recipient} for the test email.")
            return True
        else:
            logger.error(f"❌ Failed to send email. Result: {result}")
            return False
            
    except smtplib.SMTPAuthenticationError as auth_error:
        logger.error(f"❌ SMTP Authentication Error: {str(auth_error)}")
        logger.error("This usually means your username or password is incorrect.")
        logger.error("For Gmail, make sure you're using an App Password if 2FA is enabled.")
        return False
    except smtplib.SMTPException as smtp_error:
        logger.error(f"❌ SMTP Error: {str(smtp_error)}")
        return False
    except socket.timeout as timeout_error:
        logger.error(f"❌ Timeout connecting to mail server: {str(timeout_error)}")
        logger.error("The mail server took too long to respond. Check your network and server settings.")
        return False
    except socket.error as conn_error:
        logger.error(f"❌ Connection error: {str(conn_error)}")
        logger.error("Could not connect to the mail server. Check your EMAIL_HOST and EMAIL_PORT settings.")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error sending email: {str(e)}")
        logger.error("Traceback:")
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_email_direct() 
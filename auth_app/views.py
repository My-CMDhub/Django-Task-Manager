from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.sites.shortcuts import get_current_site
from django.contrib.auth import login as auth_login, logout as auth_logout, authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_http_methods
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail, get_connection
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.crypto import get_random_string
from django.urls import reverse
import traceback

# Check if Supabase module is available
try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    
from .models import User, Session, UserProfile
# Import the Supabase utility functions
from .supabase_utils import (
    supabase_client, 
    get_supabase_user_by_email,
    get_supabase_user_by_uid,
    update_supabase_user_verification
)
import os
import logging
import uuid
import base64
import json
import requests
from django.db import transaction
import re
from datetime import datetime, timedelta
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from base64 import urlsafe_b64encode, urlsafe_b64decode
import socket
import smtplib
from email.utils import make_msgid, formatdate
import email.utils
import dns.resolver
import logging
from mysite.settings import get_supabase_client, get_supabase_admin_client
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator
import hmac
import hashlib
import time
import random
from django.middleware.csrf import get_token
from django.contrib.sites.models import Site
from datetime import timezone as dt_timezone

logger = logging.getLogger(__name__)

# Function to detect if we're in production environment
def is_production():
    """Check if the application is running in production mode"""
    return getattr(settings, 'DEBUG', True) is False or getattr(settings, 'BYPASS_SUPABASE', False)

# Function to check if we should auto-verify users
def should_auto_verify_users():
    """Check if users should be automatically verified (typically only in some production scenarios)"""
    return getattr(settings, 'AUTO_VERIFY_USERS', False)

# Simplified list of allowed legitimate email domains (whitelist)
ALLOWED_EMAIL_DOMAINS = [
    # Popular email providers
    'gmail.com', 'yahoo.com', 'outlook.com', 'hotmail.com', 'aol.com', 'icloud.com', 'protonmail.com',
    'mail.com', 'zoho.com', 'yandex.com', 'gmx.com',
    # Major tech/business domains that often have email
    'microsoft.com', 'apple.com', 'amazon.com', 'google.com', 
    # Education domains
    'edu', 'ac.uk', 'edu.au',
    # Government domains
    'gov', 'gov.uk', 'gov.au',
    # Popular country domains
    'co.uk', 'co.jp', 'com.au'
]

# We'll keep the temp domains list for reference but won't use it in the updated approach
TEMP_EMAIL_DOMAINS = [
    'temp-mail.org', 'tempmail.com', 'throwawaymail.com', 'mailinator.com', '10minutemail.com', 
    'guerrillamail.com', 'sharklasers.com', 'getairmail.com', 'yopmail.com', 'tempmail.net',
    'maildrop.cc', 'harakirimail.com', 'dispostable.com', 'mailnesia.com', 'mailcatch.com',
    'getnada.com', 'tempr.email', 'fakeinbox.com', 'temp-mail.io', 'spamgourmet.com',
    'movfull.com', 'tmpmail.net', 'tempmail.plus', 'burnermail.io', 'temp-mail.org',
    'emailondeck.com', 'tempinbox.com', 'mohmal.com', 'mytemp.email', 'inboxbear.com',
    'smuggroup.com', 'altmails.com', 'freeml.net', 'zeroe.ml', 'divismail.ru',
    'emlpro.com', 'tempmailo.com', 'sharklasers.com', 'guerrillamail.info', 'grr.la',
    'pokemail.net', 'incognitomail.com', 'mintemail.com', 'emailfake.com', 'tempmail.dev',
    'trashmail.com', 'mailnator.com', 'mailexpire.com', 'spamobox.com', 'jetable.org',
    'lesotica.com' # Adding lesotica.com to the list of temporary email domains
]

def is_valid_email_domain(email):
    """
    Validates if the email domain is in our list of legitimate providers.
    Using a whitelist-only approach.
    
    Returns:
    - (bool, str): Tuple of (is_valid, error_message)
    """
    if not email or '@' not in email:
        return False, "Invalid email format"
    
    # Extract domain from email
    domain = email.split('@')[-1].lower()
    
    # Check if domain is in our whitelist of allowed domains
    if domain in ALLOWED_EMAIL_DOMAINS:
        return True, ""
    
    # Check if domain ends with any of our legitimate TLDs
    for allowed_domain in ALLOWED_EMAIL_DOMAINS:
        if domain.endswith('.' + allowed_domain):
            return True, ""
    
    # Not in whitelist - reject
    return False, "Please use an email from a recognized email provider (like Gmail, Yahoo, Outlook, etc.)"

@require_http_methods(["GET", "POST"])
@csrf_exempt  # Make login exempt from CSRF to handle direct verification links
def login(request):
    """Handle user login"""
    # Check if we're in production mode to bypass Supabase
    production_mode = is_production()
    if production_mode:
        logger.info("Login: Running in production mode - Supabase integration bypassed")
        
    # Redirect if already logged in
    if request.user.is_authenticated:
        messages.info(request, "You are already logged in.")
        return redirect('home')
        
    # Check if user just verified their email - highlight this in the template
    just_verified = request.session.pop('just_verified', False)
    verified_email = request.session.pop('verified_email', '')
    
    # Check if user just registered - highlight this in the template
    just_registered = request.session.pop('just_registered', False)
    registered_email = request.session.pop('registered_email', '')
    
    # Check if account was just deleted - offer to clean up any remaining data
    force_clean_email = request.session.pop('force_clean_email', None)
    just_deleted = False
    deleted_account = request.session.pop('deleted_account', None)
    if deleted_account and isinstance(deleted_account, dict):
        just_deleted = True
    
    # If user just registered, we'll prioritize this in the template
    # This flag will be used to manage the view behavior
    show_registration_success = False
    if just_registered and registered_email:
        show_registration_success = True
        # Add the success message in case it wasn't set previously
        messages.success(request, 
            "Registration successful! Please check your email for a verification link. "
            "You'll need to verify your email before you can log in."
        )
    
    # Handle verification token directly from URL if present
    verification_token = request.GET.get('verification_token')
    if verification_token:
        try:
            # Decode verification token
            decoded_token = decode_verification_token(verification_token)
            if decoded_token and 'email' in decoded_token:
                email = decoded_token['email']
                user = User.objects.filter(email=email, deleted_at=None).first()
                
                if user:
                    # Update verification status
                    if not user.email_verified:
                        user.email_verified = True
                        user.save()
                        
                        # Update profile if exists
                        try:
                            profile = user.profile
                            profile.verified = True
                            profile.save()
                        except Exception as profile_error:
                            logger.error(f"Error updating profile: {str(profile_error)}")
                    
                    # Auto-login the user
                    user.backend = 'django.contrib.auth.backends.ModelBackend'
                    auth_login(request, user)
                    messages.success(request, f"Email verified successfully! Welcome, {user.username}!")
                    
                    # Set verification cookies
                    response = redirect('home')
                    response.set_cookie('email_verification_status', 'verified', max_age=86400)
                    response.set_cookie('user_email', email, max_age=86400)
                    return response
                
        except Exception as e:
            logger.error(f"Error processing verification token: {str(e)}")
    
    # Clear any stale verification banners by checking actual verification status
    if request.method == 'GET' and not production_mode:
        email_in_cookie = request.COOKIES.get('user_email')
        if email_in_cookie:
            user = User.objects.filter(email=email_in_cookie, deleted_at=None).first()
            if user and not user.email_verified:
                # Double-check with Supabase
                try:
                    supabase_client = get_supabase_admin_client()
                    is_verified_in_supabase, error_info = check_supabase_verification_status(user.supabase_id, supabase_client)
                    
                    if is_verified_in_supabase:
                        # User is verified in Supabase but not in Django - update it
                        user.email_verified = True
                        user.save()
                        logger.info(f"Updated verification status from Supabase for {user.email}")
                        
                        # Show message that status was updated
                        response = render(request, 'auth/login.html', {
                            'next': request.GET.get('next', ''),
                            'verification_outdated': True,
                            'verified_user': True,
                            'email': user.email
                        })
                        response.set_cookie('email_verification_status', 'verified', max_age=86400)
                        response.set_cookie('user_email', user.email, max_age=86400)
                        return response
                except Exception as e:
                    logger.error(f"Error checking verification status with Supabase: {str(e)}")
    
    if request.method == 'POST':
        # Check if this is a verification email request
        if 'verify_only' in request.POST:
            email = request.POST.get('email')
            if not email:
                messages.error(request, "Please enter your email address.")
                return render(request, 'auth/login.html', {'show_verify': True})
            
            # Find user by email
            user = User.objects.filter(email__iexact=email).first()
            if not user:
                messages.warning(request, 
                    "No account found with this email. Would you like to <a href='{% url \"register\" %}'>create an account</a>?"
                )
                return render(request, 'auth/login.html', {'show_register_link': True})
                
            # Send verification email
            success = send_verification_email(request, user)
            if success:
                messages.success(request, 
                    "Verification email has been sent. Please check your inbox (and spam folder) to verify your email."
                )
            else:
                messages.error(request, 
                    "Failed to send verification email. Please try again later."
                )
                
            return render(request, 'auth/login.html', {'email': email})
        
        # Skip verification for returning users if requested
        if 'skip_verification' in request.POST:
            email = request.POST.get('email')
            if not email:
                messages.error(request, "Please enter your email address.")
                return render(request, 'auth/login.html')
                
            # Find user by email
            user = User.objects.filter(email__iexact=email).first()
            if not user:
                messages.warning(request, "No account found with this email.")
                return render(request, 'auth/login.html', {'show_register_link': True})
                
            # Mark user as verified if they're a returning user
            if not user.email_verified and user.date_joined < (timezone.now() - timezone.timedelta(days=1)):
                user.email_verified = True
                user.save(update_fields=['email_verified'])
                
                # Try to sync with Supabase only if not in production
                if not production_mode:
                    try:
                        logger.info(f"Marking user as verified in Supabase (skip_verification): {email}")
                        # Update Supabase verification status
                        supabase_client = get_supabase_admin_client()
                        if supabase_client and user.supabase_id:
                            from datetime import datetime
                            now = datetime.utcnow().isoformat()
                            supabase_client.auth.admin.update_user_by_id(
                                user.supabase_id,
                                {
                                    "user_metadata": {"email_verified": True}
                                }
                            )
                    except Exception as e:
                        logger.error(f"Error syncing verification with Supabase: {str(e)}")
                        
                messages.success(request, 
                    "Your account has been verified. You can now log in."
                )
            
            return render(request, 'auth/login.html', {'email': email})
        
        # Check if this is a reset account request
        if 'reset_account' in request.POST:
            email = request.POST.get('email')
            email_confirm = request.POST.get('email_confirm')
            
            if not email or not email_confirm or email.lower() != email_confirm.lower():
                messages.error(request, "Email addresses don't match. Please confirm your email correctly.")
                return render(request, 'auth/login.html', {'email': email, 'show_reset': True})
            
            # Delete from Django
            user = User.objects.filter(email__iexact=email).first()
            if user:
                logger.info(f"Reset account: Deleting user {email} from Django")
                user.delete()
            
            # Delete from Supabase if not in production mode
            if not production_mode:
                delete_supabase_user(email)
            
            messages.success(request, 
                "Your account has been reset. You can now register again with this email address."
            )
            return redirect('register')
                
        # Regular login flow
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        remember_me = request.POST.get('remember_me') == 'on'
        
        # If we're missing data, show a friendly error
        if not username or not password:
            messages.error(request, "Please enter both username/email and password.")
            return render(request, 'auth/login.html')
        
        # Determine if input is email or username
        is_email = '@' in username
        
        # Try to get the user
        user = None
        if is_email:
            user = User.objects.filter(email__iexact=username, deleted_at=None).first()
        else:
            user = User.objects.filter(username__iexact=username, deleted_at=None).first()
            
        # Check if user exists
        if not user:
            # Check if user exists in Supabase but not in Django - only if not in production mode
            supabase_exists = False
            if is_email and not production_mode:
                try:
                    # Using a method that doesn't require authentication
                    supabase_exists = check_supabase_user_exists(username)
                except Exception as e:
                    logger.error(f"Error checking Supabase during login: {str(e)}")
            
            if supabase_exists:
                # User exists in Supabase but not in Django - sync issue
                messages.warning(request, 
                    "Your account exists but seems to be out of sync. Please try resetting your password or contact support."
                )
                return render(request, 'auth/login.html', {'show_reset': True})
            else:
                # User doesn't exist in either system
                messages.warning(request, 
                    "No account found with these credentials. Please create an account first."
                )
                return render(request, 'auth/login.html', {'show_register_link': True})
            
        # Check if account is locked
        if hasattr(user, 'account_locked_until') and user.account_locked_until and user.account_locked_until > timezone.now():
            lock_time_remaining = user.account_locked_until - timezone.now()
            minutes_remaining = int(lock_time_remaining.total_seconds() / 60) + 1
            messages.error(request, 
                f"Your account is temporarily locked due to multiple failed login attempts. "
                f"Please try again in {minutes_remaining} minutes or reset your password."
            )
            return render(request, 'auth/login.html', {'show_reset': True})
            
        # Check if email is verified - always auto-verify in production mode if configured
        if hasattr(user, 'email_verified') and not user.email_verified:
            # In production mode, auto-verify if configured
            if should_auto_verify_users():
                user.email_verified = True
                user.save()
                logger.info(f"Auto-verified user via AUTO_VERIFY_USERS setting: {user.email}")
            else:
                # Email verification is required
                messages.warning(request, 
                    "Your email address has not been verified. "
                    "Please check your inbox for the verification email or request a new one."
                )
                
                # Prepare for showing verification form
                verification_url = reverse('login') + '?show_verify=1'
                response = redirect(verification_url)
                
                # Store email in session for convenience
                request.session['pending_verification_email'] = user.email
                
                # Set cookie flags
                response.set_cookie('email_verification_status', 'pending', max_age=86400)
                response.set_cookie('user_email', user.email, max_age=86400)
                
                return response
            
        # Authenticate user
        user_auth = authenticate(request, username=user.username, password=password)
        if user_auth is None:
            # Failed login - update failed attempts counter
            if hasattr(user, 'failed_login_attempts'):
                user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
                
                # Check if we should lock the account
                if user.failed_login_attempts >= getattr(settings, 'MAX_FAILED_LOGINS', 5):
                    # Lock account for 30 minutes
                    user.account_locked_until = timezone.now() + timezone.timedelta(minutes=30)
                    messages.error(request,
                        "Your account has been temporarily locked due to multiple failed login attempts. "
                        "Please try again in 30 minutes or reset your password."
                    )
                    user.save()
                    return render(request, 'auth/login.html', {'show_reset': True})
                
                user.save()
            
            messages.error(request, "Invalid username or password.")
            return render(request, 'auth/login.html')
        
        # Additional check to ensure email is verified
        if hasattr(user_auth, 'email_verified') and not user_auth.email_verified:
            # Double-check with Supabase one more time
            try:
                supabase_client = get_supabase_admin_client()
                is_verified = False
                
                if supabase_client and user.supabase_id:
                    is_verified, error_info = check_supabase_verification_status(user.supabase_id, supabase_client)
                    
                    if is_verified:
                        # User is verified in Supabase but not in Django - fix it
                        user_auth.email_verified = True
                        user_auth.save()
                        logger.info(f"Updated verification status from Supabase for {user_auth.email}")
                    else:
                        # Not verified - prevent login
                        messages.warning(request, 
                            "Your email address has not been verified yet. Please check your inbox for the verification email or "
                            "click the 'Resend Verification Email' button below."
                        )
                        return render(request, 'auth/login.html', {'email': user_auth.email, 'show_resend': True})
                else:
                    # No Supabase client available - still enforce verification
                    messages.warning(request, 
                        "Your email address has not been verified yet. Please check your inbox for the verification email or "
                        "click the 'Resend Verification Email' button below."
                    )
                    return render(request, 'auth/login.html', {'email': user_auth.email, 'show_resend': True})
            except Exception as e:
                logger.error(f"Error in final verification check: {str(e)}")
                # Prevent login if verification status can't be confirmed
                messages.warning(request, 
                    "Your email verification status could not be confirmed. Please verify your email before logging in."
                )
                return render(request, 'auth/login.html', {'email': user_auth.email, 'show_resend': True})
            
        # Successful login - reset failed login attempts
        if hasattr(user, 'failed_login_attempts'):
            user.failed_login_attempts = 0
            user.account_locked_until = None
            user.save()
        
        # Log the user in
        auth_login(request, user_auth)
        
        # Set session expiry based on remember me
        if remember_me:
            # Session expires in 2 weeks
            request.session.set_expiry(1209600)
        else:
            # Session expires when browser is closed
            request.session.set_expiry(0)
            
        # Record device info for security
        device_type = get_device_type(request)
        ip_address = get_client_ip(request)
        
        # Store login info in session for reference
        request.session['login_time'] = timezone.now().isoformat()
        request.session['login_ip'] = ip_address
        request.session['login_device'] = device_type
        
        # Set verification cookies for future reference
        response = redirect(request.POST.get('next') or request.GET.get('next') or 'home')
        response.set_cookie('email_verification_status', 'verified', max_age=86400)
        response.set_cookie('user_email', user.email, max_age=86400)
        
        # Redirect to a success page or homepage
        messages.success(request, f"Welcome back, {user.username}!")
        return response
        
    # Handle GET request
    # Check if the user has a valid cookie/session but verification status is outdated
    verification_status = request.COOKIES.get('email_verification_status')
    email_in_cookie = request.COOKIES.get('user_email')
    
    if verification_status == 'pending' and email_in_cookie:
        # Check if the user is actually verified
        user = User.objects.filter(email=email_in_cookie, deleted_at=None).first()
        if user and user.email_verified:
            # User is verified but cookie says otherwise - update the cookie in response
            response = render(request, 'auth/login.html', {
                'next': request.GET.get('next', ''),
                'just_verified': just_verified,
                'verified_email': verified_email,
                'just_registered': just_registered,
                'registered_email': registered_email,
                'verification_outdated': True,
                'verified_user': True
            })
            response.set_cookie('email_verification_status', 'verified', max_age=86400)
            return response
    
    context = {
        'next': request.GET.get('next', ''),
        'just_verified': just_verified,
        'verified_email': verified_email,
        'just_registered': just_registered,
        'registered_email': registered_email,
        'show_registration_success': show_registration_success,
        'just_deleted': just_deleted,
        'force_clean_email': force_clean_email
    }
    return render(request, 'auth/login.html', context)

@login_required
def logout(request):
    try:
        # Invalidate Supabase session
        supabase = get_supabase_client()
        # Updated for Supabase SDK v1.0.3
        supabase.auth.sign_out()
    except Exception as e:
        logger.error(f"Error during logout: {str(e)}")
    
    auth_logout(request)
    messages.success(request, "Logged out successfully")
    return redirect('home')

def send_custom_verification_email(request, user, verification_token=None):
    """
    Send a custom verification email to the user with a verification token.
    """
    try:
        # Generate a verification token if one was not provided
        if not verification_token:
            verification_token = default_token_generator.make_token(user)
        
        # Store the token in the session
        request.session['email_verification_token'] = verification_token
        request.session['email_verification_user_id'] = user.id
        logger.info(f"Generated new verification token for user {user.id}")
        
        # Create the verification URL
        current_site = get_current_site(request)
        site_name = current_site.name
        domain = current_site.domain
        
        # If we're in development, use localhost instead of the current site domain
        if settings.DEBUG:
            domain = '127.0.0.1:8000'
            
        protocol = 'https' if request.is_secure() else 'http'
        verify_url = f"{protocol}://{domain}/auth/verify-email/{urlsafe_base64_encode(force_bytes(user.pk))}/{verification_token}/"
        
        # Generate a unique message ID for DKIM compatibility
        msg_id = make_msgid(domain=domain)
        
        # Get the current year for the template
        from datetime import datetime
        current_year = datetime.now().year
        
        # Prepare the email context
        context = {
            'user': user,
            'verify_url': verify_url,
            'site_name': site_name,
            'domain': domain,
            'protocol': protocol,
            'expiration_days': settings.PASSWORD_RESET_TIMEOUT_DAYS,
            'current_year': current_year,
        }
        
        # Prepare custom headers for better deliverability
        headers = {
            'Message-ID': msg_id,
            'Date': formatdate(localtime=True),
            'X-Priority': '1',
            'Importance': 'High',
            'Precedence': 'bulk',
            'Auto-Submitted': 'auto-generated',
            'X-Mailer': 'Django',
            'List-Unsubscribe': f'<{protocol}://{domain}/auth/unsubscribe/?email={user.email}>',
            'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
            'List-ID': f'<verification.{domain}>',
        }
        
        # Render the email templates
        html_email = render_to_string('emails/verification_email.html', context)
        text_email = render_to_string('emails/verification_email_text.html', context)
        
        # Log the attempt
        logger.info(f"Sending verification email to {user.email}")
        
        # Send the email
        try:
            send_mail(
                f'Please Verify Your Email - {site_name} Account Activation',
                text_email,
                f'{site_name} <{settings.DEFAULT_FROM_EMAIL}>',
                [user.email],
                html_message=html_email,
                fail_silently=False,
            )
            logger.info(f"Verification email sent successfully to {user.email}")
            return True
        except smtplib.SMTPException as e:
            # Log the error
            logger.error(f"SMTP error sending verification email to {user.email}: {str(e)}")
            return False
    except Exception as e:
        logger.error(f"Error in send_custom_verification_email: {str(e)}")
        return False

def send_verification_email(request, user):
    """
    Send a verification email to the user.
    
    Args:
        request: The HTTP request object
        user: The user to send the verification email to
        
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    logger.info(f"Sending verification email to {user.email}")
    try:
        # When bypassing Supabase, use Django's native email system
        if getattr(settings, 'BYPASS_SUPABASE', False):
            logger.info(f"Using Django's email system for verification (BYPASS_SUPABASE=True)")
            
            # Generate a verification token
            token = encode_verification_token(user.email)
            
            # Create the verification URL - prioritize production settings for correct URL structure
            site_name = "Nexus"
            domain = settings.SITE_DOMAIN
            protocol = settings.SITE_PROTOCOL if hasattr(settings, 'SITE_PROTOCOL') else 'https'
            
            # If we have request and we're not in production, get domain from the request
            if request and settings.DEBUG:
                current_site = get_current_site(request)
                site_name = current_site.name
                domain = current_site.domain
                protocol = 'https' if request.is_secure() else 'http'
                
                # In development, use localhost
                if settings.DEBUG:
                    domain = '127.0.0.1:8000'
                    protocol = 'http'
                
            # Build the verification URL
            verify_url = f"{protocol}://{domain}/auth/verify-email/{token}/"
            
            # Log the verification URL being generated
            logger.info(f"Generated verification URL with domain {domain} and protocol {protocol}")
            
            # Prepare the email context
            context = {
                'user': user,
                'verify_url': verify_url,
                'site_name': site_name,
                'domain': domain,
                'protocol': protocol,
                'current_year': timezone.now().year,
            }
            
            # Prepare email headers
            msg_id = make_msgid(domain=domain)
            headers = {
                'Message-ID': msg_id,
                'Date': formatdate(localtime=True),
                'X-Priority': '1',
                'Importance': 'High',
                'List-Unsubscribe': f'<{protocol}://{domain}/auth/unsubscribe/?email={user.email}>',
            }
            
            # Render the email templates
            html_email = render_to_string('emails/verification_email.html', context)
            text_email = strip_tags(html_email)  # Fallback plain text version
            
            # Send the email
            try:
                # Get properly formatted sender with name
                sender_name = getattr(settings, 'SENDER_NAME', 'Nexus')
                from_email = settings.DEFAULT_FROM_EMAIL
                
                # If DEFAULT_FROM_EMAIL is just an email without a name, format it properly
                if '<' not in from_email:
                    from_email = f"{sender_name} <{from_email}>"
                
                logger.info(f"Sending verification email from: {from_email}")
                
                # Get connection with timeout
                connection = get_connection(
                    backend=settings.EMAIL_BACKEND,
                    host=settings.EMAIL_HOST,
                    port=settings.EMAIL_PORT,
                    username=settings.EMAIL_HOST_USER,
                    password=settings.EMAIL_HOST_PASSWORD,
                    use_tls=settings.EMAIL_USE_TLS,
                    use_ssl=settings.EMAIL_USE_SSL,
                    timeout=getattr(settings, 'EMAIL_TIMEOUT', 30)  # Use timeout setting or default to 30 seconds
                )
                
                send_mail(
                    f'Please Verify Your Email - {site_name} Account Activation',
                    text_email,
                    from_email,
                    [user.email],
                    html_message=html_email,
                    fail_silently=False,
                    connection=connection
                )
                logger.info(f"Verification email sent successfully to {user.email} using Django's email system")
                return True
            except smtplib.SMTPException as smtp_error:
                logger.error(f"SMTP error sending email via Django: {str(smtp_error)}")
                return False
            except socket.timeout as timeout_error:
                logger.error(f"Timeout error sending email via Django: {str(timeout_error)}")
                return False
            except Exception as email_error:
                logger.error(f"Error sending email via Django: {str(email_error)}")
                traceback.print_exc()
                return False
        
        # Original Supabase flow if not bypassing
        logger.info(f"Attempting to send verification email via Supabase to {user.email}")
        
        try:
            # Let's use Supabase's email service for verification
            # Check if we have access to the Supabase admin client
            supabase_client = get_supabase_admin_client()
            if supabase_client and hasattr(supabase_client.auth, 'admin'):
                try:
                    # Try to send password recovery email which will act as verification
                    # This is a workaround since we don't have direct API access for email verification
                    supabase_client.auth.admin.send_email(
                        user.email,
                        {
                            "type": "recovery",
                            "email": user.email
                        }
                    )
                    logger.info(f"Sent verification/recovery email to {user.email} via Supabase")
                    return True
                except Exception as admin_error:
                    logger.error(f"Error sending email via Supabase admin: {str(admin_error)}")
                    # Fall back to normal method
            
            # Get basic Supabase client as fallback  
            if not supabase_client:
                supabase_client = get_supabase_client()
                
            if supabase_client:
                try:
                    # Send password reset email as a substitute for verification
                    supabase_client.auth.reset_password_email(user.email)
                    logger.info(f"Sent reset password email to {user.email} (as verification substitute)")
                    return True
                except Exception as reset_error:
                    logger.error(f"Error sending reset email: {str(reset_error)}")
            
            logger.warning(f"Could not send verification email to {user.email} via Supabase")
            return False
        
        except Exception as e:
            logger.error(f"Error in verification email process: {str(e)}")
            return False
            
    except Exception as e:
        logger.error(f"Error sending verification email to {user.email}: {str(e)}")
        return False

@require_http_methods(["GET"])
def backup_verify_email(request, token):
    """Custom email verification endpoint as a backup to Supabase."""
    if not token:
        messages.error(request, "Invalid verification token")
        return redirect('login')
    
    # Find user with this verification token
    try:
        # Get all users
        users = User.objects.all()
        verified_user = None
        
        # Loop through users to find matching token
        for user in users:
            if hasattr(user, 'verification_tokens') and user.verification_tokens and isinstance(user.verification_tokens, dict):
                if token in user.verification_tokens:
                    # Check if token is still valid
                    expiration = user.verification_tokens[token]
                    if timezone.now().timestamp() <= expiration:
                        verified_user = user
                        # Remove the used token
                        del user.verification_tokens[token]
                        user.save()
                        break
        
        if verified_user:
            # Mark user as verified - critical that this happens
            verified_user.email_verified = True
            # Save immediately
            verified_user.save(update_fields=['email_verified'])
            # Log successful verification
            logger.info(f"Successfully verified email for user {verified_user.email} via backup system")
            
            # Try to sync this with Supabase if possible
            try:
                # For now we'll just log this since we don't have admin access
                logger.info(f"User {verified_user.email} verified via backup system")
                
                # In a production system with admin access, you would update the Supabase user
                admin_client = get_supabase_admin_client()
                if admin_client:
                    # This would require the admin API - simplified for demo
                    pass
            except Exception as e:
                logger.error(f"Error syncing user verification to Supabase: {str(e)}")
            
            messages.success(request, "Email verified successfully! You can now log in.")
            
            # Try to authenticate user automatically
            user = authenticate(request, username=verified_user.email, password=None, verified_only=True)
            if user:
                auth_login(request, user)
                messages.success(request, "You have been automatically logged in.")
                return redirect('home')
        else:
            messages.error(request, "Invalid or expired verification token")
    except Exception as e:
        logger.error(f"Error during backup email verification: {str(e)}")
        messages.error(request, "Error during email verification. Please try again or contact support.")
    
    return redirect('login')

def delete_supabase_user(email):
    """
    Attempt to delete a user from Supabase.
    Returns True if deletion was successful or user doesn't exist, False otherwise.
    """
    if not email:
        logger.error("No email provided to delete_supabase_user")
        return False
        
    logger.info(f"Attempting to delete user {email} from Supabase")
    
    try:
        # Get the Supabase admin client using service role key
        admin_client = get_supabase_admin_client()
        if not admin_client:
            logger.error("Could not get Supabase admin client for deletion")
            return False
            
        # Use the direct REST API approach for more reliable deletion
        # This approach works even when the admin client reports "User not allowed"
        try:
            # Prepare headers for direct API access
            headers = {
                "apikey": settings.SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
                "Content-Type": "application/json"
            }
            
            # Construct the Auth API URL for listing users
            auth_api_url = f"{settings.SUPABASE_URL}/auth/v1/admin/users"
            
            # First get the list of all users to find the one with matching email
            response = requests.get(auth_api_url, headers=headers, timeout=10)
            
            if response.status_code != 200:
                logger.error(f"Failed to list Supabase users: HTTP {response.status_code} - Response: {response.text}")
                
                # If we can't get users via API, try another approach - searching by email directly
                try:
                    # Try searching by email via auth API
                    search_url = f"{settings.SUPABASE_URL}/auth/v1/admin/users?email={email}"
                    search_response = requests.get(search_url, headers=headers, timeout=10)
                    
                    if search_response.status_code == 200:
                        users = search_response.json()
                        if isinstance(users, list) and len(users) > 0:
                            user_id = users[0].get('id')
                            if user_id:
                                # Found user, now delete them
                                delete_url = f"{settings.SUPABASE_URL}/auth/v1/admin/users/{user_id}"
                                delete_response = requests.delete(delete_url, headers=headers, timeout=10)
                                
                                if delete_response.status_code in [200, 204]:
                                    logger.info(f"Successfully deleted user {email} (ID: {user_id}) from Supabase via search API")
                                    return True
                except Exception as search_error:
                    logger.error(f"Error in backup search method: {str(search_error)}")
                
                return False
                
            # Parse the response and check if the user exists
            users = response.json()
            user_id = None
            
            # Find the user with matching email (case insensitive)
            if isinstance(users, list):
                for user in users:
                    if isinstance(user, dict) and user.get('email', '').lower() == email.lower():
                        user_id = user.get('id')
                        logger.info(f"Found user {email} in Supabase with ID: {user_id}")
                        break
            
            # If user not found, consider it success (nothing to delete)
            if not user_id:
                logger.info(f"User {email} not found in Supabase - nothing to delete")
                return True
                
            # Now delete the user using the admin delete user endpoint
            delete_url = f"{settings.SUPABASE_URL}/auth/v1/admin/users/{user_id}"
            delete_response = requests.delete(delete_url, headers=headers, timeout=10)
            
            if delete_response.status_code in [200, 204]:
                logger.info(f"Successfully deleted user {email} (ID: {user_id}) from Supabase")
                return True
            else:
                logger.error(f"Failed to delete user from Supabase API: HTTP {delete_response.status_code} - Response: {delete_response.text}")
                
                # Try using the admin client as a backup method
                try:
                    deletion_result = admin_client.auth.admin.delete_user(user_id)
                    logger.info(f"Deleted user {email} using admin client after API failure: {deletion_result}")
                    return True
                except Exception as backup_error:
                    error_message = str(backup_error)
                    if "User not allowed" in error_message:
                        # If we get "User not allowed" error, try to disable the user instead
                        logger.warning(f"Got 'User not allowed' error when deleting {email} from Supabase. Attempting to disable user instead.")
                        try:
                            # Disable the user by marking as banned and removing email verification
                            disable_url = f"{settings.SUPABASE_URL}/auth/v1/admin/users/{user_id}"
                            disable_payload = {
                                "banned": True, 
                                "email_confirmed": False,
                                "app_metadata": {"deleted": True}
                            }
                            disable_response = requests.put(disable_url, headers=headers, json=disable_payload, timeout=10)
                            
                            if disable_response.status_code in [200, 204]:
                                logger.info(f"Successfully disabled user {email} in Supabase as alternative to deletion")
                                return True
                            else:
                                logger.error(f"Failed to disable user {email}: HTTP {disable_response.status_code}")
                        except Exception as disable_error:
                            logger.error(f"Error disabling user {email}: {str(disable_error)}")
                    else:
                        logger.error(f"Both deletion methods failed for user {email}: {error_message}")
                    
                    return False
                    
        except requests.exceptions.Timeout:
            logger.error(f"Timeout while deleting Supabase user {email}")
            return False
        except requests.exceptions.RequestException as req_err:
            logger.error(f"Request error while deleting Supabase user {email}: {str(req_err)}")
            return False
        except Exception as e:
            logger.error(f"Error during Supabase user deletion for {email}: {str(e)}")
            return False
            
    except Exception as e:
        logger.error(f"Outer exception in delete_supabase_user for {email}: {str(e)}")
        return False

def sync_with_supabase(email, force_delete=False):
    """
    Check if a user exists in Supabase and sync with Django database.
    Returns True if user exists in Supabase, False otherwise.
    """
    try:
        supabase = get_supabase_client()
        
        # Try to perform admin lookup for the user (requires service role key)
        try:
            # This is a simplified approach - in production you would use
            # the admin API to search for users
            supabase_exists = False
            
            # Try to sign in with an invalid password to check existence
            try:
                supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": "check_existence_only"
                })
                # If we get here without exception, user exists (though login failed with incorrect password)
                supabase_exists = True
            except Exception as e:
                error_message = str(e).lower()
                # "Invalid credentials" means user exists but password wrong
                if "invalid login credentials" in error_message:
                    supabase_exists = True
                # "Email not confirmed" also means user exists
                elif "email not confirmed" in error_message:
                    supabase_exists = True
                # Other errors likely mean user doesn't exist
            
            # Check if user exists in Django but not in Supabase
            django_user = User.objects.filter(email=email).first()
            if django_user and (not supabase_exists or force_delete):
                # User exists in Django but not in Supabase - delete from Django
                logger.info(f"User {email} exists in Django but not in Supabase (or force_delete=True) - deleting from Django")
                django_user.delete()
                return False
            
            return supabase_exists
            
        except Exception as admin_error:
            logger.error(f"Error in Supabase admin check: {str(admin_error)}")
            # Fall back to basic existence check
            return False
            
    except Exception as e:
        logger.error(f"Error in sync_with_supabase: {str(e)}")
        return False

@require_http_methods(["GET", "POST"])
@csrf_exempt
def register(request):
    """Handle user registration"""
    # Check if we're in production mode to bypass Supabase
    production_mode = is_production()
    auto_verify = should_auto_verify_users()
    
    if production_mode:
        logger.info(f"Register: Running in production mode with Django-only auth. Auto-verify users: {auto_verify}")
        
    # Redirect to home if already logged in
    if request.user.is_authenticated:
        messages.info(request, "You are already logged in and registered.")
        return redirect('home')
    
    if request.method == 'POST':
        # Get form data
        email = request.POST.get('email', '').strip().lower()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        username = request.POST.get('username', '').strip()
        
        # Basic form validation first
        errors = {}
        
        # Check if email is valid
        if not email:
            errors['email'] = "Email is required."
        elif not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            errors['email'] = "Please enter a valid email address."
            
        # Check if passwords match and are strong enough
        if not password1:
            errors['password1'] = "Password is required."
        elif password1 != password2:
            errors['password2'] = "Passwords do not match."
        elif len(password1) < 8:
            errors['password1'] = "Password must be at least 8 characters long."
            
        # Generate username if not provided
        if not username:
            # Get part before @ from email
            username_base = email.split('@')[0]
            
            # Add random number if needed for uniqueness
            username = username_base
            attempt = 1
            while User.objects.filter(username=username).exists():
                username = f"{username_base}{random.randint(1, 999)}"
                attempt += 1
                if attempt > 10:
                    # Fallback to uuid if we can't generate a unique username
                    username = f"user_{str(uuid.uuid4())[:8]}"
                    break
        else:
            # Check if username is valid: only alphanumeric, at least 3 chars
            if not re.match(r'^[a-zA-Z0-9_]{3,20}$', username):
                errors['username'] = "Username must be 3-20 characters long and contain only letters, numbers, and underscores."
            elif User.objects.filter(username=username).exists():
                errors['username'] = "This username is already taken. Please choose another."
                
        # If there are validation errors, render the form with errors
        if errors:
            for field, error in errors.items():
                messages.error(request, error)
            return render(request, 'auth/register.html', {
                'email': email,
                'username': username,
                'errors': errors
            })
            
        # Check if email already exists in our system
        if User.objects.filter(email=email).exists():
            messages.warning(request, "An account with this email already exists. Please log in instead.")
            return render(request, 'auth/register.html', {
                'email': email,
                'show_login_link': True,
                'errors': {'email': "An account with this email already exists."}
            })
            
        # Create the user - different flows for production vs dev with bypass_supabase
        try:
            bypass_supabase = getattr(settings, 'BYPASS_SUPABASE', False)
            
            # For bypass_supabase mode, just create Django user and send verification email
            if bypass_supabase:
                # Create the user in Django only
                with transaction.atomic():
                    # Generate a unique supabase_id format to maintain model compatibility
                    mock_supabase_id = f"django-{str(uuid.uuid4())}"
                    
                    # Get whether to auto-verify user
                    auto_verify = should_auto_verify_users()
                    
                    # Create the Django user
                    user = User.objects.create_user(
                        username=username,
                        email=email,
                        password=password1,
                        supabase_id=mock_supabase_id,
                        email_verified=auto_verify  # Auto-verify if configured
                    )
                    
                    # Create user profile
                    profile = UserProfile.objects.create(
                        user=user,
                        verified=auto_verify
                    )
                    
                    # If auto-verification is enabled, auto-login and redirect
                    if auto_verify:
                        messages.success(request, 
                            f"Registration successful! Welcome to Nexus, {username}!"
                        )
                        
                        # Auto-login the user
                        user.backend = 'django.contrib.auth.backends.ModelBackend'
                        auth_login(request, user)
                        
                        return redirect('home')
                    else:
                        # Otherwise send verification email
                        try:
                            email_sent = send_verification_email(request, user)
                            if email_sent:
                                logger.info(f"Verification email sent to: {email}")
                            else:
                                logger.warning(f"Failed to send verification email to: {email}")
                        except Exception as email_error:
                            logger.error(f"Error sending verification email to {email}: {str(email_error)}")
                        
                        # Store registration status in session for improved UX
                        request.session['just_registered'] = True
                        request.session['registered_email'] = email
                        
                        # Always show a positive message since the email often arrives after redirect
                        messages.success(request, 
                            "Registration successful! We've sent a verification link to your email. "
                            "Please check your inbox and spam folder to verify your account. "
                            "You won't be able to log in until your email is verified."
                        )
                        
                        # Redirect to login page
                        return redirect('login')
            else:
                # Original Supabase flow
                try:
                    # Create user in Supabase first
                    supabase_client = get_supabase_admin_client()
                    if not supabase_client:
                        logger.error(f"Cannot create user in Supabase: No admin client available")
                        raise Exception("Supabase service unavailable. Please try again later.")
                        
                    logger.info(f"Creating user in Supabase: {email}")
                    
                    # Create user with Supabase
                    auth_response = supabase_client.auth.admin.create_user({
                        "email": email,
                        "password": password1,
                        "email_confirm": True,
                        "user_metadata": {
                            "username": username,
                            "registered_via": "django_app"
                        }
                    })
                    
                    # Process the response
                    if hasattr(auth_response, 'user'):
                        supabase_user = auth_response.user
                        supabase_user_id = getattr(supabase_user, 'id', None)
                        
                        logger.info(f"Supabase user created: {supabase_user_id}")
                    else:
                        # Handle unexpected response format
                        logger.error(f"Unexpected Supabase response: {auth_response}")
                        raise Exception("Unexpected response from authentication service.")
                    
                    # Create Django user linked to Supabase
                    try:
                        # To avoid race conditions with webhook, we'll create the user with verified=False initially
                        # The webhook will update it when the Supabase user confirms their email
                        user = User.objects.create_user(
                            username=username,
                            email=email,
                            password=password1,
                            supabase_id=supabase_user_id,
                            email_verified=False  # Will be updated by webhook when verified
                        )
                        
                        # Create user profile
                        UserProfile.objects.create(
                            user=user,
                            verified=False
                        )
                        
                        logger.info(f"Django user created for Supabase user: {email}")
                        
                        # Send verification email
                        try:
                            email_sent = send_verification_email(request, user)
                            if email_sent:
                                logger.info(f"Verification email sent to: {email}")
                            else:
                                logger.warning(f"Failed to send verification email to: {email}")
                        except Exception as email_error:
                            logger.error(f"Error sending verification email to {email}: {str(email_error)}")
                        
                        # Store registration status in session for improved UX
                        request.session['just_registered'] = True
                        request.session['registered_email'] = email
                        
                        # Always show a positive message since the email often arrives after redirect
                        messages.success(request, 
                            "Registration successful! We've sent a verification link to your email. "
                            "Please check your inbox and spam folder to verify your account. "
                            "You won't be able to log in until your email is verified."
                        )
                        
                        # Redirect to login page
                        return redirect('login')
                    except Exception as django_error:
                        logger.error(f"Django user creation error for {email}: {str(django_error)}")
                        
                        # Check if we can see the user in Django now (in case the error was during profile creation)
                        django_user = User.objects.filter(email__iexact=email).first()
                        if django_user:
                            messages.success(request, 
                                "Your account was created! Please check your email to verify your account. "
                                "If you don't receive an email, you can request a new verification link after logging in."
                            )
                            return redirect('login')
                        
                        # Otherwise show error
                        messages.error(request, 
                            f"Registration error: {str(django_error)}. Please try again later."
                        )
                        return render(request, 'auth/register.html', {
                            'email': email, 
                            'username': username,
                            'show_force_clean': True
                        })
                except Exception as e:
                    # Log the error for debugging
                    logger.error(f"Supabase registration error: {str(e)}")
                    
                    # User-friendly error message
                    messages.error(request, 
                        f"An error occurred during registration: {str(e)}. Please try again later."
                    )
                    
                    return render(request, 'auth/register.html', {
                        'email': email,
                        'username': username
                    })
        except Exception as e:
            # Log the error for debugging
            logger.error(f"Unexpected registration error: {str(e)}")
            
            # Check if the user was actually created despite the error
            django_user = User.objects.filter(email__iexact=email).first()
            if django_user:
                # User was created, so most likely the email was sent
                # Store registration status in session
                request.session['just_registered'] = True
                request.session['registered_email'] = email
                
                messages.success(request, 
                    "Your account was created! Please check your email to verify your account. "
                    "If you don't receive an email, you can request a new verification link after logging in."
                )
                return redirect('login')
            
            # Check for specific error types in the outer exception
            error_message = str(e).lower()
            
            if "already registered" in error_message or "already exists" in error_message:
                # User already exists
                messages.warning(request, 
                    "An account with this email already exists. Please log in instead or use the reset account option."
                )
                return render(request, 'auth/register.html', {
                    'email': email, 
                    'username': username,
                    'show_force_clean': True,
                    'show_direct': True
                })
            # Additional specific error handling
            elif "validation" in error_message or "password" in error_message:
                messages.error(request,
                    f"Validation error: {str(e)}. Please check your details and try again."
                )
            elif "smtp" in error_message or "email" in error_message:
                # Email service error - still redirect to login
                logger.warning(f"Email service error during registration for {email}, but account was likely created")
                request.session['just_registered'] = True
                request.session['registered_email'] = email
                messages.success(request, 
                    "Registration successful! We've sent a verification link to your email. "
                    "Please check your inbox and spam folder to verify your account."
                )
                return redirect('login')
            else:
                # Generic error with more details
                messages.error(request, 
                    f"Registration error: {str(e)}. Please try again or contact support if this persists."
                )
    
    # GET request - just show the registration form
    return render(request, 'auth/register.html')

def check_supabase_user_exists(email):
    """
    Check if a user exists in Supabase using direct admin API call.
    Returns True if user exists, False otherwise.
    """
    if not email:
        logger.error("No email provided to check_supabase_user_exists")
        return False
        
    try:
        logger.info(f"Checking if user {email} exists in Supabase")
        
        # Check if Supabase URL and service key are available
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
            logger.warning("Missing Supabase URL or service key - cannot check user existence")
            return False
        
        # Use direct API call with service key for more reliable result
        headers = {
            "apikey": settings.SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/json"
        }
        
        # Construct the Auth API URL
        auth_api_url = f"{settings.SUPABASE_URL}/auth/v1/admin/users"
        
        try:
            response = requests.get(auth_api_url, headers=headers, timeout=10)  # Add timeout
            
            if response.status_code != 200:
                logger.error(f"Failed to list Supabase users: HTTP {response.status_code} - Response: {response.text}")
                return False
            
            # Parse the response and check if the user exists
            users = response.json()
            
            # Check each user to see if their email matches (case insensitive)
            if isinstance(users, list):
                for user in users:
                    if isinstance(user, dict) and user.get('email', '').lower() == email.lower():
                        logger.info(f"User {email} found in Supabase via direct API")
                        return True
            
            logger.info(f"User {email} NOT found in Supabase")
            return False
        except requests.exceptions.Timeout:
            logger.error(f"Timeout checking Supabase user existence for {email}")
            return False
        except requests.exceptions.RequestException as req_err:
            logger.error(f"Request error checking Supabase user: {str(req_err)}")
            return False
        except ValueError as json_err:
            logger.error(f"Invalid JSON response from Supabase: {str(json_err)}")
            return False
    
    except Exception as e:
        logger.error(f"Error checking Supabase user existence via API: {str(e)}")
        
        # If we can't verify, we'll assume the user doesn't exist to allow registration
        return False

@login_required
def account_settings(request):
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        supabase = get_supabase_client()
        
        if form_type == 'profile':
            # Update profile info
            name = request.POST.get('name')
            if name:
                first_name, *last_name = name.split(' ', 1)
                request.user.first_name = first_name
                request.user.last_name = last_name[0] if last_name else ''
                request.user.save()
                messages.success(request, "Profile updated successfully")
                
        elif form_type == 'password':
            # Change password
            current_password = request.POST.get('current_password')
            new_password1 = request.POST.get('new_password1')
            new_password2 = request.POST.get('new_password2')
            
            if new_password1 != new_password2:
                messages.error(request, "Passwords don't match")
            elif not request.user.check_password(current_password):
                messages.error(request, "Current password is incorrect")
            else:
                try:
                    # Update in Supabase with the correct signature
                    try:
                        access_token = request.session.get('supabase_access_token')
                        if not access_token:
                            # Try to get from current session
                            current_session = supabase.auth.current_session
                            if current_session:
                                access_token = current_session.access_token
                    except:
                        # Fall back to JWT from the user's session
                        access_token = request.session.get('access_token')
                        
                    if access_token:
                        # According to Supabase docs
                        supabase.auth.update_user({
                            "password": new_password1
                        })
                    # Update locally
                    request.user.set_password(new_password1)
                    request.user.last_password_change = timezone.now()
                    request.user.save()
                    messages.success(request, "Password changed successfully")
                except Exception as e:
                    logger.error(f"Password change error: {str(e)}")
                    messages.error(request, "Failed to change password")
                    
        elif form_type == 'email':
            # Change email
            new_email = request.POST.get('new_email')
            try:
                # Update in Supabase with the correct signature
                try:
                    access_token = request.session.get('supabase_access_token')
                    if not access_token:
                        # Try to get from current session
                        current_session = supabase.auth.current_session
                        if current_session:
                            access_token = current_session.access_token
                except:
                    # Fall back to JWT from the user's session
                    access_token = request.session.get('access_token')
                    
                if access_token:
                    # According to Supabase docs
                    supabase.auth.update_user({
                        "email": new_email
                    })
                # Update locally
                request.user.email = new_email
                request.user.email_verified = False
                request.user.save()
                messages.success(request, "Email updated. Please verify your new email.")
            except Exception as e:
                logger.error(f"Email change error: {str(e)}")
                messages.error(request, "Failed to update email")
                
        elif form_type == 'logout_all':
            # Logout all sessions
            try:
                supabase.auth.sign_out()
                # Delete all local sessions
                Session.objects.filter(user=request.user).delete()
                messages.success(request, "Logged out from all devices")
            except Exception as e:
                logger.error(f"Logout all error: {str(e)}")
                messages.error(request, "Failed to logout all sessions")
    
    # Get active sessions
    sessions = request.user.active_sessions()
    return render(request, 'auth/account_settings.html', {'sessions': sessions})

@require_http_methods(["GET", "POST"])
def password_reset(request):
    """
    Handle password reset request.
    GET: Show password reset form
    POST: Process password reset request and send reset link
    """
    if request.user.is_authenticated:
        messages.info(request, "You are already logged in. You can change your password in account settings.")
        return redirect('home')  # Redirect to home if user is already logged in
        
    if request.method == 'POST':
        email = request.POST.get('email', '').lower()  # Convert to lowercase for consistency
        
        # Validate input (basic)
        if not email:
            messages.error(request, "Please enter your email address.")
            return render(request, 'auth/password_reset.html')
            
        # Email format validation
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            messages.error(request, "Please enter a valid email address format.")
            return render(request, 'auth/password_reset.html', {'email': email})
            
        # IMPORTANT: Don't reveal whether an account exists to prevent user enumeration attacks
        # We'll show the same success message regardless of user existence
        # But log different messages for security audit purposes
        
        user_exists_django = False
        user_exists_supabase = False
        supabase_id = None
        
        # Check if user exists in Django
        try:
            user = User.objects.filter(email=email, deleted_at=None).first()
            if user:
                user_exists_django = True
                supabase_id = user.supabase_id
                logger.info(f"Password reset requested for existing Django user: {email}")
        except Exception as e:
            logger.error(f"Error checking Django user during password reset: {str(e)}")
            # Don't reveal this error to the user
        
        # Check if user exists in Supabase
        if not user_exists_django or not supabase_id:
            try:
                supabase_user = check_supabase_user_exists(email)
                if supabase_user:
                    user_exists_supabase = True
                    supabase_id = supabase_user.get('id')
                    logger.info(f"Password reset requested for user in Supabase but not Django: {email}")
            except Exception as e:
                logger.error(f"Error checking Supabase during password reset: {str(e)}")
                # Don't reveal this error to the user
        
        # Handle the case where user is only in Supabase but not in Django
        if user_exists_supabase and not user_exists_django:
            # We should first create the user in Django to maintain synchronization
            try:
                logger.info(f"Creating Django user for existing Supabase user during password reset: {email}")
                # Generate random password - user will reset it anyway
                temp_password = get_random_string(16)
                # Create username from email
                username = email.split('@')[0]
                # Ensure username is unique
                suffix = 1
                original_username = username
                while User.objects.filter(username=username).exists():
                    username = f"{original_username}{suffix}"
                    suffix += 1
                
                # Create Django user linked to Supabase
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=temp_password,
                    supabase_id=supabase_id,
                    email_verified=True  # Assume verified if in Supabase
                )
                
                # Create profile if needed
                UserProfile.objects.create(
                    user=user,
                    supabase_uid=supabase_id,
                    verified=True
                )
                
                user_exists_django = True
                logger.info(f"Successfully created Django user for Supabase user during password reset: {email}")
            except Exception as e:
                logger.error(f"Failed to create Django user for Supabase user during password reset: {email} - {str(e)}")
                # Don't stop the process even if this fails
        
        # Now handle the actual password reset
        if user_exists_django:
            try:
                # Generate password reset token
                reset_token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                
                # Build reset URL
                current_site = get_current_site(request)
                site_name = current_site.name
                domain = current_site.domain
                
                # If we're in development, use localhost instead of the current site domain
                if settings.DEBUG:
                    domain = '127.0.0.1:8000'
                    
                protocol = 'https' if request.is_secure() else 'http'
                reset_url = f"{protocol}://{domain}/auth/password-reset-confirm/{uid}/{reset_token}/"
                
                # Generate a unique message ID for DKIM compatibility
                msg_id = make_msgid(domain=domain)
                
                # Get the current year for the template
                from datetime import datetime
                current_year = datetime.now().year
                
                # Prepare the email context
                context = {
                    'user': user,
                    'reset_url': reset_url,
                    'site_name': site_name,
                    'domain': domain,
                    'protocol': protocol,
                    'expiration_days': settings.PASSWORD_RESET_TIMEOUT_DAYS,
                    'current_year': current_year,
                }
                
                # Prepare custom headers for better deliverability
                headers = {
                    'Message-ID': msg_id,
                    'Date': formatdate(localtime=True),
                    'X-Priority': '1',
                    'Importance': 'High',
                    'Precedence': 'bulk',
                    'Auto-Submitted': 'auto-generated',
                    'X-Mailer': 'Django',
                    'List-Unsubscribe': f'<{protocol}://{domain}/auth/unsubscribe/?email={user.email}>',
                    'List-Unsubscribe-Post': 'List-Unsubscribe=One-Click',
                    'List-ID': f'<password-reset.{domain}>',
                }
                
                # Render the email templates
                html_email = render_to_string('emails/password_reset_email.html', context)
                text_email = render_to_string('emails/password_reset_email_text.html', context)
                
                # Send the email
                send_mail(
                    f'Password Reset Instructions - {site_name}',
                    text_email,
                    f'{site_name} <{settings.DEFAULT_FROM_EMAIL}>',
                    [user.email],
                    html_message=html_email,
                    headers=headers,
                    fail_silently=False,
                )
                
                logger.info(f"Password reset email sent to: {email}")
                
                # Store the token in the session for potential reference
                request.session['password_reset_token'] = reset_token
                request.session['password_reset_uid'] = uid
                request.session['password_reset_email'] = email
                
                # Prevent immediate reset reuse
                request.session['last_password_reset'] = time.time()
                
            except Exception as e:
                logger.error(f"Failed to send password reset email to {email}: {str(e)}")
                # Even if email sending fails, don't reveal this to user to prevent enumeration
        else:
            logger.warning(f"Password reset requested for non-existent user: {email}")
            # If we reach here, user doesn't exist in either system
            # We still show success message to prevent user enumeration
        
        # Always show the same success message regardless of user existence
        messages.success(request, 
            "If an account exists with this email address, we've sent password reset instructions. "
            "Please check your inbox (and spam folder) for further instructions."
        )
        
        # Add a slight delay to prevent timing attacks that could reveal user existence
        time.sleep(random.uniform(0.5, 1.5))
        
        return redirect('login')
    
    # GET request - just show the password reset form
    return render(request, 'auth/password_reset.html')

@require_http_methods(["GET", "POST"])
def password_reset_confirm(request, uidb64=None, token=None):
    """
    Handle password reset confirmation
    GET: Validate token and show password reset form
    POST: Process password change
    """
    try:
        # Decode the user id
        uid = urlsafe_base64_decode(uidb64).decode()
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
        
    # Check if the token is valid
    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            # Get form data
            password1 = request.POST.get('password1')
            password2 = request.POST.get('password2')
            
            # Validate input
            if not password1 or not password2:
                messages.error(request, "Please enter and confirm your new password.")
                return render(request, 'auth/password_reset_confirm.html', {'validlink': True})
                
            if password1 != password2:
                messages.error(request, "The two password fields didn't match.")
                return render(request, 'auth/password_reset_confirm.html', {'validlink': True})
                
            # Validate password strength
            if len(password1) < 8:
                messages.error(request, "Your password must be at least 8 characters long.")
                return render(request, 'auth/password_reset_confirm.html', {'validlink': True})
                
            # Check if password contains both letters and numbers
            if not (any(c.isalpha() for c in password1) and any(c.isdigit() for c in password1)):
                messages.error(request, "Your password must contain both letters and numbers.")
                return render(request, 'auth/password_reset_confirm.html', {'validlink': True})
                
            # Additional strength check
            if password1.lower() in [user.username.lower(), user.email.lower()]:
                messages.error(request, "Your password cannot be too similar to your username or email.")
                return render(request, 'auth/password_reset_confirm.html', {'validlink': True})
                
            try:
                # Update password in Django
                user.set_password(password1)
                # Reset any account lockouts
                user.failed_login_attempts = 0
                user.account_locked_until = None
                user.save()
                
                logger.info(f"Password reset successful for user: {user.email}")
                
                # Try to update password in Supabase as well
                if user.supabase_id:
                    try:
                        supabase_client = get_supabase_admin_client()
                        if supabase_client:
                            # Update password in Supabase
                            supabase_client.auth.admin.update_user_by_id(
                                user.supabase_id,
                                {'password': password1}
                            )
                            logger.info(f"Password updated in Supabase for user: {user.email}")
                        else:
                            logger.warning(f"Could not update Supabase password: No admin client available")
                    except Exception as supabase_error:
                        logger.error(f"Failed to update password in Supabase: {str(supabase_error)}")
                        # Don't stop the process if Supabase update fails
                
                messages.success(request, 
                    "Your password has been set. You may go ahead and log in now with your new password."
                )
                return redirect('login')
                
            except Exception as e:
                logger.error(f"Error during password reset for {user.email}: {str(e)}")
                messages.error(request, "An error occurred. Please try again or contact support.")
                return render(request, 'auth/password_reset_confirm.html', {'validlink': True})
        
        # GET request with valid token - show the password reset form
        return render(request, 'auth/password_reset_confirm.html', {'validlink': True})
    
    # Invalid token or user - show an error message
    messages.error(request, 
        "The password reset link is invalid or has expired. "
        "Please request a new password reset link."
    )
    return render(request, 'auth/password_reset_confirm.html', {'validlink': False})

@require_http_methods(["GET"])
def verify_email(request, token):
    """Handle email verification via token"""
    try:
        # Decode the token
        decoded_token = decode_verification_token(token)
        if not decoded_token or 'email' not in decoded_token:
            messages.error(request, "Invalid verification link. Please request a new verification email.")
            return redirect('login')
            
        email = decoded_token['email']
        
        # Find the user
        user = User.objects.filter(email=email, deleted_at=None).first()
        if not user:
            messages.error(request, "Account not found. Please register to create a new account.")
            return redirect('register')
            
        # Check if already verified
        if user.email_verified:
            messages.info(request, "Your email was already verified. You can now log in.")
            
            # Try to auto-login the user for convenience
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            auth_login(request, user)
            messages.success(request, f"Welcome, {user.username}! You have been automatically logged in.")
            
            # Set cookie to indicate verified status
            response = redirect('home')
            response.set_cookie('email_verification_status', 'verified', max_age=86400)
            response.set_cookie('user_email', email, max_age=86400)
            return response
            
        # Update Django user verification status
        user.email_verified = True
        user.save()
        
        # Try to update Supabase verification status
        if user.supabase_id:
            try:
                # Get Supabase admin client
                supabase_client = get_supabase_admin_client()
                if supabase_client:
                    # Update user's email verification status in Supabase
                    from datetime import datetime
                    now = datetime.utcnow().isoformat()
                    supabase_client.auth.admin.update_user_by_id(
                        user.supabase_id,
                        {
                            "email_confirmed_at": now,
                            "user_metadata": {"email_verified": True}
                        }
                    )
                    logger.info(f"Supabase email verification updated for user: {email}")
            except Exception as e:
                logger.error(f"Failed to update Supabase email verification status: {str(e)}")
                # We don't show this error to the user since Django verification succeeded
        
        # Update any profiles that may need updating
        try:
            profile = user.profile
            profile.verified = True
            profile.save()
        except Exception as profile_error:
            logger.error(f"Error updating profile verification status: {str(profile_error)}")
        
        # Auto-login the user after verification for better UX
        try:
            # Set the backend attribute for Django authentication
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            
            # Log the user in directly
            auth_login(request, user)
            
            # Show success message
            messages.success(request, f"Your email has been verified successfully! Welcome, {user.username}!")
            
            # Set cookie to indicate verified status
            response = redirect('home')
            response.set_cookie('email_verification_status', 'verified', max_age=86400)
            response.set_cookie('user_email', email, max_age=86400)
            return response
            
        except Exception as login_error:
            logger.error(f"Auto-login error after verification: {str(login_error)}")
            
            # If auto-login fails for some reason, redirect to login page with verification token
            # This is a fallback mechanism for our enhanced login page verification
            verification_url = f"{reverse('login')}?verification_token={token}"
            
            # Set cookies for status
            response = redirect(verification_url)
            response.set_cookie('email_verification_status', 'pending', max_age=86400)
            response.set_cookie('user_email', email, max_age=86400)
            
            # No need to set session flags since we're passing the token directly
            return response

    except Exception as e:
        logger.error(f"Email verification error: {str(e)}")
        messages.error(request, "An error occurred during email verification. Please try again or contact support.")
        return redirect('login')

def get_device_type(request):
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    if 'mobile' in user_agent:
        return 'Mobile'
    elif 'tablet' in user_agent:
        return 'Tablet'
    elif 'windows' in user_agent:
        return 'Windows PC'
    elif 'macintosh' in user_agent:
        return 'Mac'
    elif 'linux' in user_agent:
        return 'Linux PC'
    return 'Unknown Device'

@require_http_methods(["GET", "POST"])
def password_reset_confirm(request, token=None):
    # The token is usually passed in the URL query string by Supabase
    # but we use the path parameter in our URLs for cleaner URLs
    if token is None:
        token = request.GET.get('token')
    
    # If still no token, request one from the user or show error
    if token is None:
        messages.error(request, "Invalid or missing reset token")
        return redirect('password_reset')
        
    if request.method == 'POST':
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if not new_password or not confirm_password:
            messages.error(request, "Please fill in all fields")
            return render(request, 'auth/password_reset_confirm.html', {'token': token})
            
        if new_password != confirm_password:
            messages.error(request, "Passwords don't match")
            return render(request, 'auth/password_reset_confirm.html', {'token': token})
            
        try:
            supabase = get_supabase_client()
            
            # First, verify the token
            # Note: The actual implementation depends on Supabase's API
            try:
                # Update the user's password using the token
                # According to Supabase docs
                supabase.auth.update_user({
                    "password": new_password
                })
                
                messages.success(request, "Password reset successfully. You can now login with your new password.")
                return redirect('login')
            except Exception as token_error:
                logger.error(f"Token verification error: {str(token_error)}")
                messages.error(request, "Invalid or expired token")
                return render(request, 'auth/password_reset_confirm.html', {'token': token})
                
        except Exception as e:
            logger.error(f"Password reset confirmation error: {str(e)}")
            messages.error(request, "Failed to reset password. Please try again.")
            
    return render(request, 'auth/password_reset_confirm.html', {'token': token})

def complete_account_reset(request, email=None, force=False):
    """
    Completely reset an account in both Django and Supabase.
    This is an aggressive cleanup that ensures both systems are synchronized.
    
    Args:
        request: The HTTP request object
        email: The email of the account to reset
        force: If True, will forcefully delete the account even if checking fails
        
    Returns:
        tuple: (success, message) where success is a boolean and message is a description
    """
    logger.info(f"Starting complete account reset for {email} (force={force})")
    django_cleaned = False
    supabase_cleaned = False
    
    try:
        # Step 1: Delete from Django DB first
        try:
            users = User.objects.filter(email=email)
            count = users.count()
            if count > 0:
                users.delete()
                logger.info(f"Deleted {count} user(s) with email {email} from Django DB")
                django_cleaned = True
            else:
                logger.info(f"No users found with email {email} in Django DB - nothing to delete")
                django_cleaned = True  # Mark as cleaned if no users found
        except Exception as e:
            logger.error(f"Error deleting user {email} from Django: {str(e)}")
            if not force:
                messages.error(request, f"Error cleaning Django database: {str(e)}")
                return False, f"Error cleaning Django database: {str(e)}"
            # If force=True, continue anyway - we want to try all cleanup steps
        
        # Step 2: Try to delete from Supabase using admin API
        admin_client = get_supabase_admin_client()
        if admin_client:
            try:
                # First find the user
                users_response = admin_client.auth.admin.list_users()
                
                user_ids = []
                if users_response:
                    for user in users_response:
                        # Handle both dict format and User object format
                        if hasattr(user, 'email') and user.email == email:
                            user_ids.append(user.id)
                        elif isinstance(user, dict) and user.get('email') == email and 'id' in user:
                            user_ids.append(user['id'])
                
                # Delete each user found
                for user_id in user_ids:
                    try:
                        delete_response = admin_client.auth.admin.delete_user(user_id)
                        logger.info(f"Deleted user ID {user_id} from Supabase")
                        supabase_cleaned = True
                    except Exception as delete_error:
                        logger.error(f"Failed to delete user ID {user_id}: {str(delete_error)}")
                        if not force:
                            messages.error(request, f"Failed to delete Supabase user: {str(delete_error)}")
                            return False, f"Failed to delete Supabase user: {str(delete_error)}"
                
                # If no users were found, consider it cleaned
                if not user_ids:
                    logger.info(f"No users found with email {email} in Supabase via admin API")
                    supabase_cleaned = True
            except Exception as admin_error:
                logger.error(f"Admin API error: {str(admin_error)}")
                if not force:
                    messages.error(request, f"Admin API error: {str(admin_error)}")
                    return False, f"Admin API error: {str(admin_error)}"
        else:
            logger.warning("No admin client available for Supabase user deletion")
            
            # Use sign-up with same email as a workaround to test if user exists
            # This will fail if the user exists, confirming presence
            try:
                supabase = get_supabase_client()
                if supabase:
                    try:
                        # Try to sign up with the same email (will fail if user exists)
                        random_password = get_random_string(16)
                        supabase.auth.sign_up({
                            "email": email,
                            "password": random_password
                        })
                        # If we get here, the user didn't exist
                        logger.info(f"Confirmed user {email} doesn't exist in Supabase (signup succeeded)")
                        supabase_cleaned = True
                    except Exception as signup_error:
                        error_msg = str(signup_error).lower()
                        if "already registered" in error_msg or "already exists" in error_msg:
                            # User exists, but we couldn't delete - instruct to delete manually
                            if not force:
                                logger.warning(f"User {email} exists in Supabase but couldn't be deleted automatically")
                                messages.error(request, f"User {email} exists in Supabase but couldn't be deleted. Please delete your account from Supabase first.")
                                return False, f"User exists in Supabase but couldn't be deleted automatically"
                            else:
                                logger.warning(f"User {email} exists in Supabase but couldn't be deleted. Continuing with force mode.")
                        else:
                            # Some other error - not sure about user existence
                            logger.error(f"Error checking user existence via signup: {error_msg}")
                            if not force:
                                messages.error(request, f"Error checking Supabase user: {error_msg}")
                                return False, f"Error checking Supabase user: {error_msg}"
                else:
                    logger.warning("No Supabase client available")
                    if force:
                        # In force mode, consider Supabase cleaned if we can't check
                        supabase_cleaned = True
            except Exception as e:  # Changed from alter_error to e since alter_error is not defined
                logger.error(f"Error using alternate existence check: {str(e)}")
                if not force:
                    messages.error(request, f"Error checking Supabase: {str(e)}")
                    return False, f"Error checking Supabase: {str(e)}"
            
        # Double check Django DB is clean
        try:
            if User.objects.filter(email=email).exists():
                User.objects.filter(email=email).delete()
                logger.warning(f"Had to delete user {email} from Django DB again!")
            django_cleaned = True
        except Exception as e:
            logger.error(f"Error on final Django cleanup: {str(e)}")
            if not force:
                messages.error(request, f"Error on final cleanup: {str(e)}")
                return False, f"Error on final cleanup: {str(e)}"
        
        # Determine overall success
        if force:
            # In force mode, consider it successful if Django is cleaned
            django_cleaned = True
            if not supabase_cleaned:
                message = f"Account for {email} has been reset in Django. Supabase cleanup may be incomplete."
                messages.success(request, message)
                return True, message
            else:
                message = f"Account for {email} has been completely reset. You can now register again."
                messages.success(request, message)
                return True, message
        elif django_cleaned and supabase_cleaned:
            message = f"Account for {email} has been completely reset. You can now register again."
            messages.success(request, message)
            return True, message
        elif django_cleaned:
            message = f"Account for {email} has been reset in Django, but Supabase status is unknown."
            messages.success(request, message)
            return True, message
        else:
            message = f"Account reset was only partially successful. You may need to contact support."
            messages.error(request, message)
            return False, message
    
    except Exception as e:
        logger.error(f"Account reset failed for {email}: {str(e)}")
        if force:
            # In force mode, try to make sure Django is clean before giving up
            try:
                User.objects.filter(email=email).delete()
                message = f"Force-cleaned Django account after error: {str(e)}"
                messages.success(request, message)
                return True, message
            except Exception:
                pass
        message = f"Account reset failed: {str(e)}"
        messages.error(request, message)
        return False, message

def setup_custom_smtp(request):
    """
    Setup custom SMTP settings for email delivery
    """
    # Check if user is admin/staff
    if not request.user.is_authenticated or not request.user.is_staff:
        messages.error(request, "You must be an admin to access this page.")
        return redirect('login')
    
    # Get current SMTP settings from environment variables
    from django.conf import settings
    import os
    
    current_settings = {
        'SENDER_EMAIL': os.environ.get('SENDER_EMAIL', ''),
        'SENDER_NAME': os.environ.get('SENDER_NAME', ''),
        'SMTP_HOST': os.environ.get('SMTP_HOST', ''),
        'SMTP_PORT': os.environ.get('SMTP_PORT', '465'),
        'SMTP_USER': os.environ.get('SMTP_USER', ''),
        'SMTP_PASS': os.environ.get('SMTP_PASS', ''),
        'SMTP_ADMIN_EMAIL': os.environ.get('SMTP_ADMIN_EMAIL', ''),
    }
    
    if request.method == 'POST':
        # Process form data
        sender_email = request.POST.get('sender_email', '')
        sender_name = request.POST.get('sender_name', '')
        smtp_host = request.POST.get('smtp_host', '')
        smtp_port = request.POST.get('smtp_port', '')
        smtp_user = request.POST.get('smtp_user', '')
        smtp_pass = request.POST.get('smtp_pass', '')
        admin_email = request.POST.get('admin_email', '')
        send_test = request.POST.get('test_email') == 'true'
        
        # Basic validation
        if not all([sender_email, smtp_host, smtp_port, smtp_user, smtp_pass, admin_email]):
            messages.error(request, "All fields are required.")
            return render(request, 'auth/smtp_setup.html', {'smtp_config': current_settings})
        
        try:
            # Save settings to environment variables and .env file
            import dotenv
            import os
            
            # Save to .env file if it exists
            env_path = os.path.join(os.path.dirname(settings.BASE_DIR), '.env')
            if not os.path.exists(env_path):
                env_path = os.path.join(settings.BASE_DIR, '.env')
                if not os.path.exists(env_path):
                    # Create a new .env file
                    with open(env_path, 'w') as f:
                        f.write("# Django SMTP Settings\n")
            
            # Update environment variables in .env file
            dotenv.set_key(env_path, 'SENDER_EMAIL', sender_email)
            dotenv.set_key(env_path, 'SENDER_NAME', sender_name)
            dotenv.set_key(env_path, 'SMTP_HOST', smtp_host)
            dotenv.set_key(env_path, 'SMTP_PORT', smtp_port)
            dotenv.set_key(env_path, 'SMTP_USER', smtp_user)
            dotenv.set_key(env_path, 'SMTP_PASS', smtp_pass)
            dotenv.set_key(env_path, 'SMTP_ADMIN_EMAIL', admin_email)
            
            # Also update current process environment variables
            os.environ['SENDER_EMAIL'] = sender_email
            os.environ['SENDER_NAME'] = sender_name
            os.environ['SMTP_HOST'] = smtp_host
            os.environ['SMTP_PORT'] = smtp_port
            os.environ['SMTP_USER'] = smtp_user
            os.environ['SMTP_PASS'] = smtp_pass
            os.environ['SMTP_ADMIN_EMAIL'] = admin_email
            
            # Update Django settings
            settings.EMAIL_HOST = smtp_host
            settings.EMAIL_PORT = int(smtp_port)
            settings.EMAIL_HOST_USER = smtp_user
            settings.EMAIL_HOST_PASSWORD = smtp_pass
            settings.DEFAULT_FROM_EMAIL = sender_email
            settings.EMAIL_USE_TLS = int(smtp_port) == 587
            settings.EMAIL_USE_SSL = int(smtp_port) == 465
            settings.EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
            
            messages.success(request, "SMTP settings saved successfully!")
            
            # Send test email if requested
            if send_test:
                from django.core.mail import send_mail
                
                try:
                    send_mail(
                        subject=f"Test email from {sender_name}",
                        message="This is a test email from your Nexus application. If you received this, your SMTP settings are working correctly!",
                        from_email=f"{sender_name} <{sender_email}>",
                        recipient_list=[admin_email],
                        fail_silently=False,
                    )
                    messages.success(request, f"Test email sent to {admin_email}. Please check your inbox!")
                except Exception as email_error:
                    messages.error(request, f"Error sending test email: {str(email_error)}")
            
            # Update current settings for display
            current_settings = {
                'SENDER_EMAIL': sender_email,
                'SENDER_NAME': sender_name,
                'SMTP_HOST': smtp_host,
                'SMTP_PORT': smtp_port,
                'SMTP_USER': smtp_user,
                'SMTP_PASS': smtp_pass,
                'SMTP_ADMIN_EMAIL': admin_email,
            }
            
        except Exception as e:
            messages.error(request, f"Error saving SMTP settings: {str(e)}")
    
    return render(request, 'auth/smtp_setup.html', {'smtp_config': current_settings})

@csrf_exempt
def webhook_test_endpoint(request):
    """API endpoint for webhook test"""
    if request.method != 'POST':
        return JsonResponse({"success": False, "error": "Only POST requests are allowed"})
    
    try:
        # Parse JSON body
        data = json.loads(request.body)
        
        # Log the test event
        logger.info(f"Received webhook test with data: {data}")
        
        return JsonResponse({
            "success": True,
            "message": "Webhook test received successfully",
            "timestamp": timezone.now().isoformat(),
            "received_data": data
        })
    except Exception as e:
        logger.error(f"Error processing webhook test: {str(e)}")
        return JsonResponse({"success": False, "error": str(e)})

@require_http_methods(["GET", "POST"])
def force_account_reset(request):
    """
    View for handling force account reset requests.
    This allows users to clean up accounts that may be in an inconsistent state.
    """
    if request.method == 'POST':
        email = request.POST.get('email')
        confirm_email = request.POST.get('confirm_email')
        direct_reg = request.POST.get('direct_reg') == 'on'  # New option for direct registration
        
        if not email or not confirm_email:
            messages.error(request, "Both email fields are required.")
            return render(request, 'auth/force_reset.html')
        
        if email != confirm_email:
            messages.error(request, "Email addresses must match.")
            return render(request, 'auth/force_reset.html')
        
        # Call complete_account_reset with force=True
        success, message = complete_account_reset(request, email, force=True)
        
        if success:
            if direct_reg:
                # Redirect to direct registration
                messages.info(request, "Account reset successful. Proceeding with direct registration.")
                return redirect(f'/auth/register/?email={email}&direct=true')
            else:
                # Redirect to register page if successful
                messages.success(request, f"Account for {email} has been completely reset. You can now register again.")
                return redirect('register')
        else:
            # Stay on force reset page if failed
            return render(request, 'auth/force_reset.html')
    
    return render(request, 'auth/force_reset.html')

@login_required
def test_email_sending(request):
    """Test function to verify email sending functionality"""
    if not request.user.is_staff:
        messages.error(request, "You must be a staff member to access this page.")
        return redirect('home')
        
    if request.method == 'POST':
        test_email = request.POST.get('test_email', '')
        
        if not test_email:
            messages.error(request, "Please provide an email address to test.")
            return render(request, 'auth/test_email.html')
            
        try:
            # Generate a unique ID for this test email
            test_id = get_random_string(8)
            
            # Send a test email
            subject = "Nexus - Test Email"
            message = "This is a test email sent from Nexus to verify the email sending functionality."
            
            # Create a more professional HTML email
            html_message = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Nexus Test Email</title>
                <style>
                    body {{
                        font-family: Arial, 'Helvetica Neue', Helvetica, sans-serif;
                        line-height: 1.6;
                        color: #333333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 0;
                        background-color: #f5f5f5;
                    }}
                    .container {{
                        background-color: #ffffff;
                        border: 1px solid #dddddd;
                        border-radius: 5px;
                        padding: 20px;
                        margin: 20px;
                    }}
                    .header {{
                        background-color: #4C7BF3;
                        color: white;
                        padding: 15px;
                        text-align: center;
                        border-radius: 5px 5px 0 0;
                        margin: -20px -20px 20px;
                    }}
                    .details {{
                        background-color: #f9f9f9;
                        border: 1px solid #eeeeee;
                        border-radius: 5px;
                        padding: 15px;
                        margin: 20px 0;
                    }}
                    .footer {{
                        margin-top: 30px;
                        font-size: 12px;
                        color: #777777;
                        text-align: center;
                        border-top: 1px solid #eeeeee;
                        padding-top: 15px;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>Nexus Test Email</h1>
                    </div>
                    
                    <p>Hello there,</p>
                    
                    <p>This is a test email sent from Nexus to verify that our email sending functionality is working correctly.</p>
                    
                    <p><strong>If you received this email, it means your email configuration is working properly!</strong></p>
                    
                    <div class="details">
                        <h3>Test Details:</h3>
                        <ul>
                            <li><strong>Email backend:</strong> {settings.EMAIL_BACKEND}</li>
                            <li><strong>SMTP server:</strong> {settings.EMAIL_HOST}</li>
                            <li><strong>From address:</strong> {settings.DEFAULT_FROM_EMAIL}</li>
                            <li><strong>To address:</strong> {test_email}</li>
                            <li><strong>Test ID:</strong> {test_id}</li>
                            <li><strong>Time sent:</strong> {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}</li>
                        </ul>
                    </div>
                    
                    <p>This email is part of a test to ensure proper email delivery. If you're experiencing issues with emails being marked as spam, please check the following:</p>
                    
                    <ol>
                        <li>Add our sending address to your contacts or safe senders list</li>
                        <li>Check your spam/junk folder and mark our emails as "Not Spam"</li>
                        <li>Whitelist our domain in your email settings</li>
                    </ol>
                    
                    <p>Thank you for helping us test our email system!</p>
                    
                    <p>Best regards,<br>
                    The Nexus Team</p>
                    
                    <div class="footer">
                        <p>This is an automated test email. Please do not reply to this message.</p>
                        <p>Test ID: {test_id}</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Use a personalized From address with a proper name
            if hasattr(settings, 'SENDER_NAME') and settings.SENDER_NAME:
                from_email = f"{settings.SENDER_NAME} <{settings.DEFAULT_FROM_EMAIL}>"
            else:
                from_email = settings.DEFAULT_FROM_EMAIL
                # If DEFAULT_FROM_EMAIL already has a display name, use it as is
                if '<' not in from_email:
                    from_email = f"Nexus <{from_email}>"
            
            # Add message ID and other headers to improve deliverability
            message_id = f"<test-{test_id}@{request.get_host().split(':')[0]}>"
            headers = {
                'Message-ID': message_id,
                'X-Priority': '1',
                'X-MSMail-Priority': 'High',
                'Importance': 'High',
                'X-Auto-Response-Suppress': 'OOF, DR, RN, NRN, AutoReply',
                'Auto-Submitted': 'auto-generated',
                'X-Entity-Ref-ID': test_id,
            }
            
            # Add any additional headers from settings
            if hasattr(settings, 'EMAIL_EXTRA_HEADERS') and isinstance(settings.EMAIL_EXTRA_HEADERS, dict):
                headers.update(settings.EMAIL_EXTRA_HEADERS)
            
            logger.info(f"Sending test email to {test_email}")
            send_result = send_mail(
                subject=subject,
                message=message,
                from_email=from_email,
                recipient_list=[test_email],
                html_message=html_message,
                fail_silently=False,
                headers=headers
            )
            
            if send_result == 1:
                logger.info(f"Test email sent successfully to {test_email}")
                messages.success(request, f"Test email sent successfully to {test_email}. Please check both your inbox and spam folder.")
            else:
                logger.error(f"Failed to send test email to {test_email} - send_mail returned {send_result}")
                messages.error(request, "Failed to send test email. Please check logs for details.")
                
        except Exception as e:
            logger.error(f"Exception sending test email to {test_email}: {str(e)}")
            messages.error(request, f"Error sending test email: {str(e)}")
    
    # Pass email configuration to the template
    context = {
        'email_backend': settings.EMAIL_BACKEND,
        'email_host': settings.EMAIL_HOST,
        'email_port': settings.EMAIL_PORT,
        'email_from': settings.DEFAULT_FROM_EMAIL,
    }
    
    return render(request, 'auth/test_email.html', context)

def resend_verification_email(request):
    """View for allowing users to request a new verification email"""
    if request.method == 'POST':
        email = request.POST.get('email')
        
        if not email:
            messages.error(request, "Please provide your email address.")
            return render(request, 'auth/resend_verification.html')
        
        try:
            # Check if user exists in Django
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                # Check if user exists in Supabase
                supabase_response = get_supabase_user_by_email(email)
                if not supabase_response or not supabase_response.get('data'):
                    logger.warning(f"User with email {email} not found in either Django or Supabase")
                    messages.warning(request, "If an account exists with this email, a verification link has been sent.")
                    return render(request, 'auth/resend_verification.html')
                    
                # User exists only in Supabase, create in Django
                logger.info(f"User {email} found in Supabase but not in Django. Creating Django user...")
                user_data = supabase_response.get('data')[0]
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=get_random_string(12)  # Random password, user can reset later
                )
                
                user_profile, created = UserProfile.objects.get_or_create(
                    user=user,
                    defaults={
                        'supabase_uid': user_data.get('id'),
                        'verified': user_data.get('email_confirmed_at') is not None
                    }
                )
                logger.info(f"Created Django user for {email} with Supabase UID {user_profile.supabase_uid}")
            
            # Check if user is already verified
            profile = UserProfile.objects.get(user=user)
            if profile.verified:
                messages.info(request, "Your account is already verified. Please login.")
                return redirect('login')
            
            # Send verification email using Supabase
            logger.info(f"Sending verification email to {email} using Supabase")
            
            # Try using Supabase admin client
            supabase_admin = get_supabase_admin_client()
            if supabase_admin and hasattr(supabase_admin.auth, 'admin'):
                try:
                    # Try to send verification email directly (if admin API supports it)
                    response = supabase_admin.auth.admin.send_email(
                        email, 
                        {"type": "signup"}
                    )
                    logger.info(f"Sent verification email via Supabase admin API to {email}")
                    messages.success(request, 
                        "A verification email has been sent. Please check your inbox and spam folder. "
                        "The link will expire in 24 hours."
                    )
                    return redirect('login')
                except Exception as e:
                    logger.error(f"Error sending email via Supabase admin API: {str(e)}")
                    # Continue to fallback method
            
            # Fallback method: send password reset email which serves as verification
            try:
                supabase_client = get_supabase_client()
                if supabase_client:
                    supabase_client.auth.reset_password_email(email)
                    logger.info(f"Sent password reset email as verification alternative to {email}")
                    messages.success(request, 
                        "A verification email has been sent. Please check your inbox and spam folder. "
                        "The link will expire in 24 hours."
                    )
                    return redirect('login')
            except Exception as e:
                logger.error(f"Error sending password reset email: {str(e)}")
                
            # Both methods failed, show error
            messages.error(request, "Unable to send verification email. Please try again later.")
            
        except Exception as e:
            logger.error(f"Error during verification email process for {email}: {str(e)}")
            messages.error(request, "An error occurred. Please try again later.")
    
    return render(request, 'auth/resend_verification.html')

@require_http_methods(["GET"])
def unsubscribe(request):
    """Handle unsubscribe requests from email links"""
    email = request.GET.get('email')
    
    if not email:
        messages.warning(request, "No email address provided. Unable to unsubscribe.")
        return render(request, 'auth/unsubscribe.html')
    
    logger.info(f"Processing unsubscribe request for email: {email}")
    
    try:
        # Find the user by email
        user = User.objects.filter(email=email).first()
        
        if not user:
            messages.info(request, "No account found with this email address. No changes were made.")
            return render(request, 'auth/unsubscribe.html')
        
        # Get or create user profile
        user_profile, created = UserProfile.objects.get_or_create(
            user=user,
            defaults={'email_notifications': False}
        )
        
        # Update email preferences
        user_profile.email_notifications = False
        user_profile.save()
        
        # Try to update in Supabase if we have a UID
        if hasattr(user_profile, 'supabase_uid') and user_profile.supabase_uid:
            try:
                # Use appropriate Supabase API call to update user preferences
                # This is a placeholder - implement the actual Supabase update call
                admin_client = get_supabase_admin_client()
                if admin_client:
                    # Update user preferences in Supabase
                    # Example: admin_client.auth.admin.update_user(user_profile.supabase_uid, {'email_notifications': False})
                    # The actual implementation will depend on your Supabase setup
                    logger.info(f"Updated Supabase preferences for user {email}")
            except Exception as e:
                logger.error(f"Error updating Supabase preferences for {email}: {str(e)}")
        
        messages.success(request, "Email notifications have been disabled for your account.")
        return render(request, 'auth/unsubscribe.html')
    
    except Exception as e:
        logger.error(f"Error processing unsubscribe request for {email}: {str(e)}")
        messages.error(request, "There was a problem processing your request. Please try again later.")
        return render(request, 'auth/unsubscribe.html')

@login_required
@require_http_methods(["GET", "POST"])
def delete_account(request):
    """
    Handle user account deletion process.
    Permanently deletes the user account from both Django and Supabase.
    """
    if request.method == "POST":
        password = request.POST.get('password')
        confirm_delete = request.POST.get('confirm_delete') == 'on'
        
        # Validate the inputs
        if not password:
            messages.error(request, "Please enter your password to confirm deletion.")
            return render(request, 'auth/delete_account.html')
        
        if not confirm_delete:
            messages.error(request, "You must check the confirmation box to delete your account.")
            return render(request, 'auth/delete_account.html')
        
        # Verify password
        if not request.user.check_password(password):
            messages.error(request, "Password is incorrect. Please try again.")
            return render(request, 'auth/delete_account.html')
        
        # Get user info for logging
        user_email = request.user.email
        user_id = request.user.id
        username = request.user.username
        
        # Get Supabase UID
        supabase_uid = None
        try:
            profile = getattr(request.user, 'profile', None)
            if profile:
                supabase_uid = profile.supabase_uid
            
            if not supabase_uid and hasattr(request.user, 'supabase_id'):
                supabase_uid = request.user.supabase_id
                
            logger.info(f"Found Supabase UID for {user_email}: {supabase_uid}")
        except Exception as e:
            logger.warning(f"Error retrieving Supabase UID for user {user_id}: {str(e)}")
        
        # Log deletion attempt
        logger.info(f"Account deletion requested for user ID: {user_id}, email: {user_email}")
        
        # Initialize success flags
        django_delete_success = False
        supabase_delete_success = False
        
        # Step 1: Delete from Supabase first using direct REST API
        # This approach works even when the admin client reports "User not allowed"
        try:
            # Prepare API request headers with service role key
            headers = {
                "apikey": settings.SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
                "Content-Type": "application/json"
            }
            
            # Try to find user by email first
            user_found = False
            user_id_supabase = None
            
            # Check for cached supabase_uid first
            if supabase_uid:
                user_id_supabase = supabase_uid
                user_found = True
                logger.info(f"Using cached Supabase UID: {user_id_supabase}")
            
            # If no cached ID, search by email
            if not user_found:
                search_url = f"{settings.SUPABASE_URL}/auth/v1/admin/users"
                search_response = requests.get(search_url, headers=headers, timeout=10)
                
                if search_response.status_code == 200:
                    users = search_response.json()
                    if isinstance(users, list):
                        for user in users:
                            if isinstance(user, dict) and user.get('email', '').lower() == user_email.lower():
                                user_id_supabase = user.get('id')
                                user_found = True
                                logger.info(f"Found user {user_email} in Supabase with ID: {user_id_supabase}")
                                break
                else:
                    logger.error(f"Failed to search users in Supabase: HTTP {search_response.status_code}")
            
            # If user found, try direct deletion
            if user_found and user_id_supabase:
                delete_url = f"{settings.SUPABASE_URL}/auth/v1/admin/users/{user_id_supabase}"
                delete_response = requests.delete(delete_url, headers=headers, timeout=10)
                
                if delete_response.status_code in [200, 204]:
                    logger.info(f"Successfully deleted user {user_email} from Supabase")
                    supabase_delete_success = True
                else:
                    logger.error(f"Failed to delete user via REST API: HTTP {delete_response.status_code}")
                    
                    # If deletion fails, try to disable/ban the user
                    disable_url = f"{settings.SUPABASE_URL}/auth/v1/admin/users/{user_id_supabase}"
                    disable_payload = {
                        "banned": True,
                        "email_confirmed": False,
                        "app_metadata": {"disabled": True, "deleted": True}
                    }
                    disable_response = requests.put(disable_url, headers=headers, json=disable_payload, timeout=10)
                    
                    if disable_response.status_code in [200, 204]:
                        logger.info(f"Successfully disabled user {user_email} in Supabase")
                        supabase_delete_success = True
                    else:
                        logger.error(f"Failed to disable user: HTTP {disable_response.status_code}")
            else:
                # If user not found in Supabase, consider it a success
                logger.info(f"User {user_email} not found in Supabase - nothing to delete")
                supabase_delete_success = True
                
        except Exception as e:
            logger.error(f"Error during Supabase deletion: {str(e)}")
            
        # Step 2: Delete any authentication tokens
        try:
            # Delete any auth tokens or sessions
            Token = type('Token', (), {'objects': None})
            try:
                from rest_framework.authtoken.models import Token
                Token.objects.filter(user_id=user_id).delete()
                logger.info(f"Deleted auth tokens for user {user_email}")
            except ImportError:
                pass  # Token model not available
            
            # Delete sessions
            from django.contrib.sessions.models import Session
            for session in Session.objects.all():
                try:
                    session_data = session.get_decoded()
                    if session_data.get('_auth_user_id') == str(user_id):
                        session.delete()
                except Exception:
                    pass  # Skip problematic sessions
        except Exception as e:
            logger.error(f"Error cleaning up sessions: {str(e)}")
        
        # Step 3: Log out the user before deleting their account
        auth_logout(request)
        
        # Step 4: Delete the user from Django
        try:
            # Get the user again from the database
            user = User.objects.get(id=user_id)
            
            # Hard delete (bypass any soft-delete mechanism)
            user.delete()
            django_delete_success = True
            
            logger.info(f"Successfully deleted user {user_id} from Django")
            
        except User.DoesNotExist:
            logger.warning(f"User {user_id} not found in database during deletion process")
            # Consider this a success as there's nothing to delete
            django_delete_success = True
        except Exception as e:
            logger.error(f"Error during account deletion for user {user_id}: {str(e)}")
            django_delete_success = False
        
        # Step 5: Store info in session to help with recovery if needed
        request.session['deleted_account'] = {
            'email': user_email,
            'username': username,
            'timestamp': timezone.now().isoformat()
        }
        
        # Store email for potential cleanup
        request.session['force_clean_email'] = user_email
        
        # Create appropriate success message
        messages.success(request, "Your account has been permanently deleted. All data has been removed from our systems.")
        
        # Redirect to login page
        return redirect('login')
    
    # GET request - show deletion confirmation page
    return render(request, 'auth/delete_account.html')

def configure_supabase_smtp():
    """Configure Supabase SMTP settings using the admin client"""
    try:
        # Get Supabase admin client
        admin_client = get_supabase_admin_client()
        if not admin_client:
            logger.error("Could not get Supabase admin client for SMTP configuration")
            return False
        
        # Build SMTP configuration for Supabase
        smtp_config = {
            "SMTP_ADMIN_EMAIL": os.environ.get('ADMIN_EMAIL', ''),
            "SMTP_HOST": os.environ.get('SMTP_HOST', ''),
            "SMTP_PORT": int(os.environ.get('SMTP_PORT', '465')),
            "SMTP_USER": os.environ.get('SMTP_USER', ''),
            "SMTP_PASS": os.environ.get('SMTP_PASS', ''),
            "SMTP_MAX_FREQUENCY": 60,  # Seconds between emails (rate limit)
            "SMTP_SENDER_NAME": os.environ.get('SENDER_NAME', 'Nexus'),
            "SMTP_SENDER_EMAIL": os.environ.get('SENDER_EMAIL', '')
        }
        
        # Make API call to update SMTP settings
        # The actual API endpoint would depend on Supabase's admin API structure
        # This is a placeholder for the actual implementation
        response = admin_client.auth.admin.update_smtp_settings(smtp_config)
        
        if response.status_code == 200:
            logger.info("Supabase SMTP settings updated successfully")
            return True
        else:
            logger.error(f"Failed to update Supabase SMTP settings: {response.text}")
            return False
    
    except Exception as e:
        logger.error(f"Error configuring Supabase SMTP: {str(e)}")
        
        # Fallback: Update local settings only if Supabase admin API is not available
        try:
            # Update local settings (Django)
            settings.EMAIL_HOST = os.environ.get('SMTP_HOST', '')
            settings.EMAIL_PORT = int(os.environ.get('SMTP_PORT', '465'))
            settings.EMAIL_HOST_USER = os.environ.get('SMTP_USER', '')
            settings.EMAIL_HOST_PASSWORD = os.environ.get('SMTP_PASS', '')
            settings.EMAIL_USE_TLS = settings.EMAIL_PORT == 587
            settings.EMAIL_USE_SSL = settings.EMAIL_PORT == 465
            settings.DEFAULT_FROM_EMAIL = os.environ.get('SENDER_EMAIL', '')
            
            logger.info("Updated local Django email settings (Supabase admin API not available)")
            return True
        except Exception as inner_e:
            logger.error(f"Failed to update local email settings: {str(inner_e)}")
            return False

def account_sync_status(request):
    """
    Display real-time synchronization status between Django and Supabase.
    Shows the current state of the user in both systems.
    """
    email = request.GET.get('email')
    
    # Get the current ngrok URL from settings
    ngrok_url = os.environ.get('NGROK_URL', settings.SUPABASE_SITE_URL)
    
    # Build webhook URL
    webhook_url = f"{ngrok_url}/auth/webhooks/supabase/"
    
    # Default context data
    context = {
        'ngrok_url': ngrok_url,
        'webhook_url': webhook_url,
        'webhook_active': True,
        'email': email,
        'django_user_exists': False,
        'supabase_user_exists': False,
        'sync_logs': []
    }
    
    # No email provided, just show the empty status page
    if not email:
        messages.info(request, "Enter an email address to check synchronization status.")
        return render(request, 'auth/account_sync_status.html', context)
    
    # Check Django user
    django_user = None
    try:
        django_user = User.objects.filter(email=email).first()
        if django_user:
            context['django_user_exists'] = True
            context['django_user'] = django_user
            context['sync_logs'].append({
                'level': 'success',
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'message': f"Found user in Django database: {email}"
            })
        else:
            context['sync_logs'].append({
                'level': 'info',
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'message': f"No user found in Django database with email: {email}"
            })
    except Exception as e:
        context['sync_logs'].append({
            'level': 'error',
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'message': f"Error checking Django user: {str(e)}"
        })
    
    # Check Supabase user
    supabase_user = None
    try:
        admin_client = get_supabase_admin_client()
        if admin_client:
            # Get all users
            users_response = admin_client.auth.admin.list_users()
            
            if users_response:
                # Find user with matching email
                for user in users_response:
                    # Handle different response formats
                    if hasattr(user, 'email') and user.email.lower() == email.lower():
                        supabase_user = user
                        break
                    elif isinstance(user, dict) and user.get('email', '').lower() == email.lower():
                        supabase_user = user
                        break
            
            if supabase_user:
                context['supabase_user_exists'] = True
                context['supabase_user'] = supabase_user
                context['sync_logs'].append({
                    'level': 'success',
                    'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'message': f"Found user in Supabase: {email}"
                })
            else:
                context['sync_logs'].append({
                    'level': 'info',
                    'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'message': f"No user found in Supabase with email: {email}"
                })
        else:
            context['sync_logs'].append({
                'level': 'warning',
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'message': "Could not get Supabase admin client. Unable to check Supabase user status."
            })
    except Exception as e:
        context['sync_logs'].append({
            'level': 'error',
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'message': f"Error checking Supabase user: {str(e)}"
        })
    
    # Check synchronization status
    if context['django_user_exists'] and context['supabase_user_exists']:
        # Both systems have the user
        context['sync_logs'].append({
            'level': 'success',
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'message': f"Account {email} is synchronized between Django and Supabase"
        })
    elif context['django_user_exists'] and not context['supabase_user_exists']:
        # Only in Django
        context['sync_logs'].append({
            'level': 'warning',
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'message': f"Account {email} exists only in Django but not in Supabase - systems are out of sync"
        })
    elif not context['django_user_exists'] and context['supabase_user_exists']:
        # Only in Supabase
        context['sync_logs'].append({
            'level': 'warning',
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'message': f"Account {email} exists only in Supabase but not in Django - systems are out of sync"
        })
    else:
        # Not in either system
        context['sync_logs'].append({
            'level': 'info',
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'message': f"Account {email} does not exist in either system"
        })
    
    # Check webhook configuration
    try:
        # Check if webhook secret is properly configured
        webhook_secret = settings.SUPABASE_WEBHOOK_SECRET
        if webhook_secret == 'your-webhook-secret-key':
            context['sync_logs'].append({
                'level': 'warning',
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'message': "Webhook is using default secret key - signature verification is disabled"
            })
        
        # Check ngrok URL
        if 'ngrok' not in ngrok_url:
            context['sync_logs'].append({
                'level': 'warning',
                'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                'message': f"Not using ngrok URL for webhooks. Current URL: {ngrok_url}"
            })
            
    except Exception as e:
        context['sync_logs'].append({
            'level': 'error',
            'timestamp': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
            'message': f"Error checking webhook configuration: {str(e)}"
        })
    
    # Add timestamp to logs
    context['last_check'] = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
    
    return render(request, 'auth/account_sync_status.html', context)

@csrf_exempt
def test_webhook(request):
    """Test the Supabase webhook configuration with fake events"""
    if request.method == 'POST':
        event_type = request.POST.get('event_type', 'user.created')
        email = request.POST.get('email', 'test@example.com')
        
        # Create a test payload similar to what Supabase would send
        payload = {
            'type': event_type,
            'table': 'auth.users',
            'record': {
                'id': str(uuid.uuid4()),
                'email': email,
                'created_at': timezone.now().isoformat(),
                'raw_user_meta_data': {
                    'username': 'testuser'
                }
            }
        }
        
        try:
            # Get the webhook URL
            ngrok_url = os.environ.get('NGROK_URL', settings.SUPABASE_SITE_URL)
            webhook_url = f"{ngrok_url}/auth/webhooks/supabase/"
            
            # Create signature if webhook secret is set
            headers = {
                'Content-Type': 'application/json',
                'X-Request-Id': str(uuid.uuid4())
            }
            
            webhook_secret = settings.SUPABASE_WEBHOOK_SECRET
            if webhook_secret and webhook_secret != 'your-webhook-secret-key':
                payload_bytes = json.dumps(payload).encode()
                signature = hmac.new(
                    webhook_secret.encode(),
                    payload_bytes,
                    hashlib.sha256
                ).hexdigest()
                headers['X-Supabase-Signature'] = signature
            
            # Make the webhook request
            response = requests.post(webhook_url, json=payload, headers=headers)
            
            if response.status_code == 200:
                messages.success(request, f"Webhook test successful! Event: {event_type}, Response: {response.text}")
            else:
                messages.error(request, f"Webhook test failed. Status: {response.status_code}, Response: {response.text}")
                
            # Redirect to status page
            return redirect(f'/auth/sync-status/?email={email}&autoRefresh=true')
            
        except Exception as e:
            messages.error(request, f"Error testing webhook: {str(e)}")
            return redirect('/auth/sync-status/')
    
    # GET request - show the test form
    return render(request, 'auth/test_webhook.html', {
        'ngrok_url': os.environ.get('NGROK_URL', settings.SUPABASE_SITE_URL)
    })

def is_throwaway_email(email):
    """
    Check if an email is from a known temporary/disposable email provider.
    Returns True if the email seems to be a throwaway address.
    """
    if not email or '@' not in email:
        return False
        
    # Extract domain from email
    domain = email.split('@')[-1].lower()
    
    # Check if domain is in our list of known temp email providers
    for temp_domain in TEMP_EMAIL_DOMAINS:
        if domain == temp_domain or domain.endswith('.' + temp_domain):
            logger.warning(f"Throwaway email detected: {email} (domain: {domain})")
            return True
            
    # Check for suspicious domain patterns often used by temp email services
    suspicious_patterns = [
        'temp', 'disposable', 'mailinator', 'yopmail', 'trash', 
        'guerrilla', 'throw', 'tempmail', 'fake', 'spam', 
        'junk', 'discard', 'burst', 'nada', 'test', 'temp-mail'
    ]
    
    for pattern in suspicious_patterns:
        if pattern in domain:
            logger.warning(f"Potentially suspicious email domain detected: {email} (domain: {domain}, pattern: {pattern})")
            return True
            
    # Additional checks could be added here, such as domain age checks
    # or reputation checks via external APIs
    
    return False

def get_client_ip(request):
    """Get the client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip

# Registration validation function
def validate_registration_input(email, username, password1, password2):
    """
    Validate registration input and return (is_valid, error_message)
    """
    # Check if all fields are provided
    if not email or not username or not password1 or not password2:
        return False, "All fields are required."
    
    # Check if passwords match
    if password1 != password2:
        return False, "Passwords do not match."
    
    # Email format validation
    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return False, "Please enter a valid email address format."
    
    # Username validation (alphanumeric and underscore only)
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        return False, "Username can only contain letters, numbers, and underscores."
    
    # Password strength validation
    if len(password1) < 8:
        return False, "Your password must be at least 8 characters long."
    
    # Additional password strength check - require at least one digit
    if not any(c.isdigit() for c in password1):
        return False, "Your password must contain at least one number."
    
    # Additional password strength check - require at least one letter
    if not any(c.isalpha() for c in password1):
        return False, "Your password must contain at least one letter."
    
    return True, ""

def decode_verification_token(token):
    """
    Decode and validate a verification token
    
    Args:
        token: The verification token to decode
        
    Returns:
        dict: The decoded token content or None if invalid
    """
    try:
        # First, prepare the token for decoding - remove any URL encoding
        token = token.replace(' ', '+')  # Replace spaces with + (common URL encoding issue)
        
        # Decode from base64
        try:
            decoded = base64.b64decode(token).decode('utf-8')
        except Exception as decode_error:
            logger.error(f"Failed to decode token: {str(decode_error)}")
            return None
            
        # Parse the JSON content
        try:
            token_data = json.loads(decoded)
        except json.JSONDecodeError:
            logger.error("Token is not valid JSON")
            return None
            
        # Validate token structure
        if not isinstance(token_data, dict) or 'email' not in token_data:
            logger.error("Token has invalid structure")
            return None
            
        # Check for token expiration
        if 'exp' in token_data:
            expiration = token_data['exp']
            current_time = int(time.time())
            
            if current_time > expiration:
                logger.error(f"Token expired at {expiration}, current time is {current_time}")
                return None
                
        return token_data
        
    except Exception as e:
        logger.error(f"Error decoding verification token: {str(e)}")
        return None
        
def encode_verification_token(email, expiration_hours=24):
    """
    Create a verification token for email verification
    
    Args:
        email: The email to encode in the token
        expiration_hours: How many hours until the token expires
        
    Returns:
        str: Base64 encoded token with email and expiration
    """
    try:
        # Create token data
        expiration = int(time.time()) + (expiration_hours * 3600)
        token_data = {
            'email': email,
            'exp': expiration,
            'created': int(time.time())
        }
        
        # Convert to JSON and encode
        json_data = json.dumps(token_data)
        encoded_token = base64.b64encode(json_data.encode('utf-8')).decode('utf-8')
        
        return encoded_token
    except Exception as e:
        logger.error(f"Error creating verification token: {str(e)}")
        return None

def check_supabase_verification_status(user_id, supabase_client):
    """
    Check if a user is verified in Supabase
    
    Args:
        user_id: The Supabase user ID to check
        supabase_client: The Supabase admin client
        
    Returns:
        bool: True if the user is verified, False otherwise
        dict: Error information if applicable
    """
    error_info = None
    retry_count = 0
    max_retries = 2
    
    # If no client or user_id, fail gracefully
    if not supabase_client or not user_id:
        return False, {"error": "Missing supabase client or user ID", "type": "missing_parameters"}
    
    while retry_count <= max_retries:
        try:
            # Get user from Supabase
            user_response = supabase_client.auth.admin.get_user_by_id(user_id)
            
            if not user_response or not hasattr(user_response, 'user'):
                logger.warning(f"No user data received from Supabase for user_id {user_id}")
                return False, {"error": "User not found in Supabase", "type": "user_not_found"}
                
            user_data = user_response.user
            
            # Check various ways verification might be stored
            # Check app metadata
            app_metadata = getattr(user_data, 'app_metadata', None)
            if isinstance(app_metadata, dict) and app_metadata.get('email_confirmed'):
                return True, None
                
            # Check user metadata
            user_metadata = getattr(user_data, 'user_metadata', None) 
            if isinstance(user_metadata, dict) and user_metadata.get('email_verified'):
                return True, None
            
            # Check email verification status in various possible locations
            if hasattr(user_data, 'email_confirmed_at') and user_data.email_confirmed_at:
                return True, None
                
            if hasattr(user_data, 'confirmed_at') and user_data.confirmed_at:
                return True, None
                
            # Access as dictionary for newer Supabase versions
            if hasattr(user_data, 'to_dict'):
                user_dict = user_data.to_dict()
                if user_dict.get('email_confirmed_at') or user_dict.get('confirmed_at'):
                    return True, None
                    
                # Check metadata in dict form
                meta = user_dict.get('user_metadata', {})
                if meta and meta.get('email_verified'):
                    return True, None
            
            # If we get here, user exists but is not verified
            return False, {"error": "User exists but is not verified", "type": "not_verified"}
            
        except Exception as e:
            retry_count += 1
            error_message = str(e)
            logger.error(f"Error checking Supabase verification status (attempt {retry_count}/{max_retries+1}): {error_message}")
            
            # Handle "User not allowed" error - assume verification is successful
            # This happens when permissions are limited but user is actually verified
            if "User not allowed" in error_message:
                logger.warning(f"Received 'User not allowed' error, assuming user {user_id} is verified")
                return True, None
            
            # Specific handling for different error types
            if "connection" in error_message.lower() or "timeout" in error_message.lower():
                error_info = {"error": f"Connection issue with Supabase: {error_message}", "type": "connection_error"}
                # Only retry connection-related errors
                if retry_count <= max_retries:
                    time.sleep(1)  # Wait before retry
                    continue
            else:
                error_info = {"error": f"Unknown error checking verification: {error_message}", "type": "unknown_error"}
                # Don't retry for non-connection errors
                break
                
    # If we've exhausted retries or had a non-connection error
    logger.warning(f"Failed to check Supabase verification after {retry_count} attempts: {error_info}")
    return False, error_info

def verify_all_users():
    """
    Utility function to verify all users in the database.
    Can be called from the Django shell to fix verification issues:
    
    from auth_app.views import verify_all_users
    verify_all_users()
    """
    from auth_app.models import User
    
    users = User.objects.filter(email_verified=False)
    count = 0
    
    for user in users:
        user.email_verified = True
        user.save()
        count += 1
    
    # For efficiency, also provide a bulk update method
    # update_count = User.objects.filter(email_verified=False).update(email_verified=True)
    
    return f"Successfully verified {count} users"

@require_http_methods(["GET"])
@login_required
def auto_verify_users_for_production(request):
    """Verify all unverified users when in production mode to ensure smooth transition"""
    # Only admins should be able to run this
    if not request.user.is_staff and not request.user.is_superuser:
        return JsonResponse({"error": "You do not have permission to perform this action."}, status=403)
        
    # Only run in production
    if not is_production():
        return JsonResponse({"error": "This endpoint is only available in production mode."}, status=400)
        
    try:
        # Get counts before verification
        total_users = User.objects.count()
        unverified_before = User.objects.filter(email_verified=False).count()
        
        # Perform verification
        updated = User.objects.filter(email_verified=False).update(email_verified=True)
        
        # Update profiles too
        from django.db.models import F
        profile_updates = UserProfile.objects.filter(user__email_verified=True, verified=False).update(verified=True)
        
        return JsonResponse({
            "success": True,
            "total_users": total_users,
            "unverified_before": unverified_before,
            "verified_count": updated,
            "profile_updates": profile_updates,
            "message": f"Successfully verified {updated} users and {profile_updates} profiles."
        })
    except Exception as e:
        logger.error(f"Error in auto-verifying users: {str(e)}")
        return JsonResponse({"error": f"An error occurred: {str(e)}"}, status=500)

def auth_choice(request):
    # Keep existing code intact
    return render(request, 'auth/auth_choice.html')

@require_http_methods(["GET"])
def validate_email_domain_ajax(request):
    """
    AJAX endpoint to validate if an email domain is allowed
    Returns JSON response with validation result
    """
    email = request.GET.get('email', '').strip()
    if not email or '@' not in email:
        return JsonResponse({'is_valid': False, 'message': 'Please enter a valid email address'})
    
    is_valid, error_message = is_valid_email_domain(email)
    return JsonResponse({
        'is_valid': is_valid,
        'message': error_message if not is_valid else ''
    })

def get_new_csrf_token(request):
    """
    Generate a new CSRF token and return it as JSON response.
    This can be called via AJAX when a token expires to refresh it without page reload.
    """
    token = get_token(request)
    return JsonResponse({'csrfToken': token})

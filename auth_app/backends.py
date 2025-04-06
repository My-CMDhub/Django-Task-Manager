from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db.models import Q
from supabase import create_client
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()

class EmailBackend(ModelBackend):
    """
    Custom authentication backend that allows login with email instead of username.
    Also integrates with Supabase authentication when available.
    """
    
    def authenticate(self, request, username=None, password=None, email=None, verified_only=False, **kwargs):
        # Get the username or email
        login = email or username
        if not login:
            return None
            
        # For verified_only mode (used after email verification)
        if verified_only:
            try:
                # Allow authentication without password for just-verified accounts
                user = User.objects.get(
                    Q(email=login) | Q(username=login),
                    email_verified=True
                )
                # Only for just-verified accounts via our custom verification
                return user
            except User.DoesNotExist:
                return None
        
        # Regular authentication flow
        if not password:
            return None
            
        try:
            # First try local authentication
            try:
                # Check using Django's auth system
                user = User.objects.get(
                    Q(email=login) | Q(username=login)
                )
                
                # If user exists but isn't verified, we'll verify automatically in some cases
                if not user.email_verified:
                    auto_verify = False
                    
                    # Auto-verify returning users
                    if user.last_login:
                        auto_verify = True
                        logger.info(f"Auto-verifying returning user: {login}")
                    
                    # Auto-verify users created more than 24 hours ago
                    elif user.date_joined and user.date_joined < (timezone.now() - timezone.timedelta(days=1)):
                        auto_verify = True
                        logger.info(f"Auto-verifying user registered more than a day ago: {login}")
                    
                    if auto_verify:
                        user.email_verified = True
                        user.save(update_fields=['email_verified'])
                    else:
                        logger.warning(f"Attempted login for unverified account: {login}")
                        return None
                
                # CRITICAL FIX: Check the password BEFORE trying Supabase
                # This ensures we don't hit Supabase unnecessarily and avoid rate limits  
                if self.verify_password(user, password):
                    # If we have a valid local user with correct password, we should NOT fail
                    # even if Supabase auth fails - this ensures login works even with Supabase issues
                    try:
                        # Try Supabase auth for consistency but don't require it to succeed
                        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
                        response = supabase.auth.sign_in_with_password({
                            "email": login,
                            "password": password
                        })
                        # If successful, store the session token
                        if hasattr(response, 'session'):
                            user._supabase_session_token = response.session.access_token
                    except Exception as supabase_error:
                        # Log but don't fail authentication
                        logger.warning(f"Supabase auth failed but local auth succeeded: {str(supabase_error)}")
                    
                    # Return the authenticated user regardless of Supabase status
                    return user
            except User.DoesNotExist:
                logger.info(f"User not found in local database: {login}")
                
            # If local auth fails, try Supabase auth
            if settings.SUPABASE_URL and settings.SUPABASE_KEY:
                try:
                    # Attempt to authenticate with Supabase
                    logger.info(f"Attempting Supabase authentication for: {login}")
                    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
                    response = supabase.auth.sign_in_with_password({
                        "email": login,
                        "password": password
                    })
                    
                    if response and response.user:
                        logger.info(f"Supabase authentication successful for: {login}")
                        # User exists in Supabase - ensure they exist locally too
                        try:
                            user = User.objects.get(email=login)
                            # Update the verified status if needed
                            if not user.email_verified:
                                user.email_verified = True
                                user.supabase_id = response.user.id
                                user.save()
                                logger.info(f"Updated local user verification for: {login}")
                        except User.DoesNotExist:
                            # Create user in the local database
                            logger.info(f"Creating new local user from Supabase auth: {login}")
                            user = User.objects.create_user(
                                username=login,
                                email=login,
                                password=password,  # This will be hashed by Django
                                email_verified=True,
                                supabase_id=response.user.id
                            )
                        
                        # Store Supabase session token for later API calls
                        if hasattr(response, 'session'):
                            user._supabase_session_token = response.session.access_token
                            
                        return user
                except Exception as e:
                    # Log detailed error for debugging
                    error_msg = str(e).lower()
                    if "invalid login credentials" in error_msg:
                        logger.error(f"Invalid Supabase credentials for: {login}")
                    elif "email not confirmed" in error_msg:
                        logger.error(f"Supabase email not confirmed for: {login}")
                    else:
                        logger.error(f"Supabase authentication error for {login}: {str(e)}")
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            
        return None
        
    def verify_password(self, user, password):
        """Check if the password is valid for the user."""
        return user.check_password(password)

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
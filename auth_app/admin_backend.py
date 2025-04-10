from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q
import logging
import json

logger = logging.getLogger(__name__)
User = get_user_model()

# Hard-coded admin credentials as a fallback
ADMIN_USERNAME = 'admin'
ADMIN_EMAIL = 'admin@example.com'
ADMIN_PASSWORD = 'admin1234'

class AdminBackend(ModelBackend):
    """
    Simple authentication backend for Django admin that bypasses Supabase.
    Used specifically for admin login without external dependencies.
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
            
        # Only process admin-related URLs
        if request and not (request.path.startswith('/admin/') or 
                           (request.META.get('HTTP_REFERER', '') and '/admin/' in request.META.get('HTTP_REFERER', ''))):
            return None
            
        logger.info(f"Admin backend processing login for: {username}")
            
        # Direct authentication for admin user
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            # Ensure admin user exists
            try:
                admin_user = User.objects.get(username=ADMIN_USERNAME)
                logger.info("Admin user found, checking credentials")
                
                # Ensure they have the right permissions
                if not admin_user.is_staff or not admin_user.is_superuser:
                    admin_user.is_staff = True
                    admin_user.is_superuser = True
                    admin_user.save()
                    logger.info("Admin permissions updated")
                
                # Update password if needed
                if not admin_user.check_password(ADMIN_PASSWORD):
                    admin_user.set_password(ADMIN_PASSWORD)
                    admin_user.save()
                    logger.info("Admin password updated")
                    
                # Mark user to be excluded from Supabase sync
                # Store this info in verification_tokens JSON field
                if hasattr(admin_user, 'verification_tokens') and admin_user.verification_tokens is None:
                    admin_user.verification_tokens = json.dumps({
                        "exclude_from_sync": True,
                        "is_admin_user": True
                    })
                    admin_user.save(update_fields=['verification_tokens'])
                    logger.info("Admin user marked to exclude from Supabase sync")
                
                return admin_user
                
            except User.DoesNotExist:
                # Admin doesn't exist, create it
                logger.info("Creating admin user directly")
                admin_user = User.objects.create_user(
                    username=ADMIN_USERNAME,
                    email=ADMIN_EMAIL,
                    password=ADMIN_PASSWORD
                )
                admin_user.is_staff = True
                admin_user.is_superuser = True
                admin_user.email_verified = True
                
                # Mark user to be excluded from Supabase sync
                admin_user.verification_tokens = json.dumps({
                    "exclude_from_sync": True,
                    "is_admin_user": True
                })
                
                admin_user.save()
                
                return admin_user
                
        # Other staff users
        try:
            user = User.objects.get(
                Q(username=username) | Q(email=username)
            )
            
            # Make sure it's a staff or superuser
            if not (user.is_staff or user.is_superuser):
                logger.warning(f"Non-staff user {username} attempted admin login")
                return None
                
            # Check the password
            if user.check_password(password):
                return user
        except User.DoesNotExist:
            pass
            
        return None
        
    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None 
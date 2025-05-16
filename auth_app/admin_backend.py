from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q
import logging
import json

logger = logging.getLogger(__name__)
User = get_user_model()



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
            
        # Only allow authentication for staff or superuser users
        try:
            user = User.objects.get(Q(username=username) | Q(email=username))
            
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
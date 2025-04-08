"""
Utility functions for interacting with Supabase
"""
import logging
import json
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Initialize the Supabase client from settings
try:
    from supabase import create_client
    
    # Determine the key to use (try both env var names for flexibility)
    supabase_key = getattr(settings, 'SUPABASE_KEY', None) or getattr(settings, 'SUPABASE_ANON_KEY', None)
    
    if not supabase_key:
        logger.error("No Supabase key found in settings (tried SUPABASE_KEY and SUPABASE_ANON_KEY)")
        supabase_client = None
    else:
        logger.info(f"Initializing Supabase client with URL: {settings.SUPABASE_URL}")
        supabase_client = create_client(settings.SUPABASE_URL, supabase_key)
        logger.info("Supabase client initialized successfully")
except Exception as e:
    logger.error(f"Error initializing Supabase client: {str(e)}")
    supabase_client = None


def get_supabase_user_by_email(email):
    """
    Retrieve a user from Supabase by email
    """
    if not supabase_client:
        logger.error("Supabase client not initialized")
        return None
        
    try:
        # Using service role key for admin API access
        if hasattr(settings, 'SUPABASE_SERVICE_KEY') and settings.SUPABASE_SERVICE_KEY:
            headers = {
                "apikey": settings.SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
                "Content-Type": "application/json"
            }
            
            endpoint = f"{settings.SUPABASE_URL}/auth/v1/admin/users"
            params = {"email": email}
            response = requests.get(endpoint, headers=headers, params=params)
            
            if response.status_code == 200:
                return {'data': response.json()}
                
        return None
    except Exception as e:
        logger.error(f"Error fetching user by email from Supabase: {str(e)}")
        return None


def get_supabase_user_by_uid(uid):
    """
    Retrieve a user from Supabase by their UID
    """
    if not supabase_client:
        logger.error("Supabase client not initialized")
        return None
        
    try:
        # Using service role key to access admin API
        if hasattr(settings, 'SUPABASE_SERVICE_KEY') and settings.SUPABASE_SERVICE_KEY:
            headers = {
                "apikey": settings.SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
                "Content-Type": "application/json"
            }
            
            endpoint = f"{settings.SUPABASE_URL}/auth/v1/admin/users/{uid}"
            response = requests.get(endpoint, headers=headers)
            
            if response.status_code == 200:
                return {'data': response.json()}
                
        return None
    except Exception as e:
        logger.error(f"Error fetching user by UID from Supabase: {str(e)}")
        return None


def update_supabase_user_verification(uid):
    """
    Update a user's email verification status in Supabase
    """
    if not supabase_client:
        logger.error("Supabase client not initialized")
        return None
        
    try:
        # Using service role key to update user
        if hasattr(settings, 'SUPABASE_SERVICE_KEY') and settings.SUPABASE_SERVICE_KEY:
            headers = {
                "apikey": settings.SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
                "Content-Type": "application/json"
            }
            
            endpoint = f"{settings.SUPABASE_URL}/auth/v1/admin/users/{uid}"
            payload = {
                "email_confirmed_at": "now()",
                "user_metadata": {
                    "email_verified": True
                }
            }
            
            response = requests.put(endpoint, headers=headers, json=payload)
            
            if response.status_code in (200, 201, 204):
                return {'status': 'success'}
            else:
                logger.error(f"Failed to update user verification in Supabase: {response.text}")
                return {'status': 'error', 'message': response.text}
                
        return {'status': 'error', 'message': 'No service key available'}
    except Exception as e:
        logger.error(f"Error updating user verification in Supabase: {str(e)}")
        return {'status': 'error', 'message': str(e)} 
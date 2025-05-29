"""
Supabase utility functions for the Task Manager project.
These functions provide access to Supabase clients based on the current Django settings.
"""

from django.conf import settings
import logging

logger = logging.getLogger(__name__)

def get_supabase_client():
    """
    Get the Supabase client based on current Django settings.
    This function will always check the current settings at runtime.
    
    Returns:
        Supabase client instance or None if bypassed or unavailable
    """
    # Check if Supabase is bypassed in the current settings
    if getattr(settings, 'BYPASS_SUPABASE', False):
        logger.debug("Supabase client is bypassed via settings.BYPASS_SUPABASE")
        return None
        
    # Import Supabase client class
    try:
        from supabase import create_client, Client
    except ImportError:
        logger.error("Supabase client could not be imported")
        return None
        
    # Get configuration from current settings
    supabase_url = getattr(settings, 'SUPABASE_URL', None)
    supabase_key = getattr(settings, 'SUPABASE_KEY', None)
    
    if not supabase_url or not supabase_key:
        logger.error("Missing Supabase URL or API key")
        return None
        
    # Create and return client
    try:
        client = create_client(supabase_url, supabase_key)
        return client
    except Exception as e:
        logger.error(f"Error initializing Supabase client: {e}")
        return None
        
def get_supabase_admin_client():
    """
    Get the Supabase admin client with service role key based on current Django settings.
    This function will always check the current settings at runtime.
    
    Returns:
        Supabase admin client instance or None if bypassed or unavailable
    """
    # Check if Supabase is bypassed in the current settings
    if getattr(settings, 'BYPASS_SUPABASE', False):
        logger.debug("Supabase admin client is bypassed via settings.BYPASS_SUPABASE")
        return None
        
    # Import Supabase client class
    try:
        from supabase import create_client, Client
    except ImportError:
        logger.error("Supabase client could not be imported")
        return None
        
    # Get configuration from current settings
    supabase_url = getattr(settings, 'SUPABASE_URL', None)
    supabase_service_key = getattr(settings, 'SUPABASE_SERVICE_KEY', None)
    
    if not supabase_url or not supabase_service_key:
        logger.error("Missing Supabase URL or service key")
        return None
        
    # Create and return admin client
    try:
        admin_client = create_client(supabase_url, supabase_service_key)
        return admin_client
    except Exception as e:
        logger.error(f"Error initializing Supabase admin client: {e}")
        return None 
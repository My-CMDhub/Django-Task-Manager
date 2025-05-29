"""
Supabase utility functions for auth_app.
These functions provide helpers for working with Supabase authentication.
"""

import logging
from django.conf import settings
from mysite.supabase_utils import get_supabase_client, get_supabase_admin_client

logger = logging.getLogger(__name__)

# Create a convenience variable that can be imported
supabase_client = get_supabase_client()

def get_supabase_user_by_email(email, admin_client=None):
    """
    Get a Supabase user by email
    
    Args:
        email: The email to look up
        admin_client: Optional admin client to use
        
    Returns:
        User data dict or None if not found
    """
    if not email:
        return None
        
    client = admin_client or get_supabase_admin_client()
    if not client:
        logger.debug("No Supabase client available for user lookup")
        return None
        
    try:
        # Use the admin API to look up the user
        response = client.auth.admin.list_users()
        
        # In Supabase v2, response is a list of user objects
        if isinstance(response, list):
            for user in response:
                if hasattr(user, 'email') and user.email.lower() == email.lower():
                    return user
        else:
            # Check if we got users as an attribute
            users = getattr(response, 'users', [])
            if users:
                # Filter locally by email
                matching_users = [user for user in users if getattr(user, 'email', '').lower() == email.lower()]
                if matching_users:
                    return matching_users[0]
                
        logger.debug(f"No Supabase user found with email: {email}")
        return None
    except Exception as e:
        logger.error(f"Error looking up Supabase user by email: {e}")
        return None

def get_supabase_user_by_uid(uid, admin_client=None):
    """
    Get a Supabase user by ID
    
    Args:
        uid: The user ID to look up
        admin_client: Optional admin client to use
        
    Returns:
        User data dict or None if not found
    """
    if not uid:
        return None
        
    client = admin_client or get_supabase_admin_client()
    if not client:
        logger.debug("No Supabase client available for user lookup")
        return None
        
    try:
        # Use the admin API to look up the user
        response = client.auth.admin.get_user_by_id(uid)
        
        # Check if we got a user directly or as an attribute
        if hasattr(response, 'user'):
            return response.user
        elif hasattr(response, 'id') and response.id == uid:
            return response
            
        logger.debug(f"No Supabase user found with ID: {uid}")
        return None
    except Exception as e:
        logger.error(f"Error looking up Supabase user by ID: {e}")
        return None

def update_supabase_user_verification(uid, verified=True, admin_client=None):
    """
    Update a Supabase user's email verification status
    
    Args:
        uid: The user ID to update
        verified: True to mark as verified, False to mark as unverified
        admin_client: Optional admin client to use
        
    Returns:
        True if successful, False otherwise
    """
    if not uid:
        return False
        
    client = admin_client or get_supabase_admin_client()
    if not client:
        logger.debug("No Supabase client available for user update")
        return False
        
    try:
        # Use the admin API to update the user
        response = client.auth.admin.update_user_by_id(
            uid,
            {
                "email_confirm": verified,
                "user_metadata": {
                    "email_verified": verified
                }
            }
        )
        
        # Check if we got a user back
        if hasattr(response, 'user'):
            user = response.user
            logger.info(f"Updated Supabase user {uid} verification status to {verified}")
            return True
        elif hasattr(response, 'id') and response.id == uid:
            logger.info(f"Updated Supabase user {uid} verification status to {verified}")
            return True
        else:
            logger.warning(f"Failed to update Supabase user {uid} verification status")
            return False
    except Exception as e:
        logger.error(f"Error updating Supabase user verification: {e}")
        return False 
import json
import logging
import hmac
import hashlib
import base64
import time
import random
from functools import wraps
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.db import connection
from django.utils import timezone

# Configure logger
logger = logging.getLogger(__name__)
User = get_user_model()

def with_retry(max_retries=None):
    """Decorator to retry database operations on failure"""
    if max_retries is None:
        max_retries = getattr(settings, 'WEBHOOK_MAX_RETRIES', 3)
        
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries > max_retries:
                        logger.error(f"Function {func.__name__} failed after {max_retries} retries: {str(e)}")
                        raise
                    
                    # Exponential backoff with jitter
                    sleep_time = 0.1 * (2 ** retries) + (0.1 * random.random())
                    logger.warning(f"Retrying {func.__name__} after error: {str(e)}. Retry {retries}/{max_retries}, waiting {sleep_time:.2f}s")
                    time.sleep(sleep_time)
        return wrapper
    return decorator

@csrf_exempt
@require_POST
def supabase_webhook_handler(request):
    """
    Handle webhooks from Supabase for real-time user synchronization
    
    Supabase will send events like:
    - user.created
    - user.deleted
    - user.updated
    """
    # Skip processing if sync is disabled
    if not getattr(settings, 'SUPABASE_SYNC_ENABLED', True):
        logger.info("Webhook processing skipped - sync disabled in settings")
        return JsonResponse({"status": "skipped", "message": "Sync is disabled"})
    
    # 1. Verify webhook signature if a webhook secret is set
    webhook_secret = getattr(settings, 'SUPABASE_WEBHOOK_SECRET', None)
    if webhook_secret and webhook_secret != 'your-webhook-secret-key':  # Skip verification if using default value
        signature = request.headers.get('X-Supabase-Signature')
        if not signature:
            logger.warning("Received webhook without signature")
            return HttpResponseBadRequest("Missing signature")
        
        # Verify HMAC signature
        payload = request.body
        expected_sig = hmac.new(
            webhook_secret.encode(), 
            payload, 
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(expected_sig, signature):
            logger.warning(f"Invalid webhook signature. Got: {signature}, Expected: {expected_sig}")
            return HttpResponseBadRequest("Invalid signature")
    else:
        logger.info("Webhook signature verification skipped (development mode)")
    
    # 2. Process the webhook payload
    try:
        payload = json.loads(request.body)
        event_type = payload.get('type', '')
        request_id = request.headers.get('X-Request-Id', 'unknown')
        logger.info(f"Received Supabase webhook: {event_type} (Request ID: {request_id})")
        
        # Handle different event types
        if event_type == 'user.deleted':
            return handle_user_deleted(payload)
        elif event_type == 'user.created':
            return handle_user_created(payload)
        elif event_type == 'user.updated':
            return handle_user_updated(payload)
        else:
            logger.info(f"Unhandled webhook event type: {event_type}")
            return JsonResponse({"status": "success", "message": f"Event {event_type} ignored"})
    
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in webhook payload: {request.body}")
        return HttpResponseBadRequest("Invalid JSON")
    except Exception as e:
        logger.exception(f"Error processing webhook: {str(e)}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

@with_retry()
@transaction.atomic
def handle_user_deleted(payload):
    """Handle user deletion event from Supabase"""
    try:
        # Extract user info from the payload
        user_record = payload.get('record', {})
        supabase_user_id = user_record.get('id')
        email = user_record.get('email')
        
        if not supabase_user_id and not email:
            logger.error("User deletion webhook missing user identifiers")
            return JsonResponse({"status": "error", "message": "Missing user identifiers"}, status=400)
        
        # Build a query to find the user(s) by Supabase ID or email
        query = Q()
        if supabase_user_id:
            query |= Q(supabase_id=supabase_user_id)
        if email:
            query |= Q(email=email)
            
        # Find the user(s) in Django DB
        users_to_delete = User.objects.filter(query)
        
        if users_to_delete.exists():
            count = users_to_delete.count()
            
            # Check for deleted_at column
            with connection.cursor() as cursor:
                cursor.execute("PRAGMA table_info(auth_app_user)")
                columns = [col[1] for col in cursor.fetchall()]
                
            # If deleted_at column exists, use soft delete
            if 'deleted_at' in columns:
                for user in users_to_delete:
                    user.deleted_at = timezone.now()
                    user.save(update_fields=['deleted_at'])
                logger.info(f"Soft-deleted {count} Django user(s) for Supabase user {supabase_user_id or email}")
            else:
                # Otherwise use hard delete
                users_to_delete.delete()
                logger.info(f"Hard-deleted {count} Django user(s) for Supabase user {supabase_user_id or email}")
                
            return JsonResponse({
                "status": "success", 
                "message": f"Deleted {count} Django user(s)"
            })
        else:
            logger.warning(f"No Django user found for Supabase user {supabase_user_id or email}")
            return JsonResponse({
                "status": "success", 
                "message": "No matching Django user found"
            })
            
    except Exception as e:
        logger.exception(f"Error handling user deletion: {str(e)}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

@with_retry()
@transaction.atomic
def handle_user_created(payload):
    """Handle user creation event from Supabase"""
    try:
        # Extract user info from the payload
        user_record = payload.get('record', {})
        supabase_user_id = user_record.get('id')
        email = user_record.get('email')
        
        if not supabase_user_id or not email:
            logger.error("User creation webhook missing required user identifiers")
            return JsonResponse({"status": "error", "message": "Missing required user identifiers"}, status=400)
        
        # Check if user already exists in Django
        existing_user = None
        try:
            existing_user = User.objects.get(Q(supabase_id=supabase_user_id) | Q(email=email))
            logger.info(f"User {email} already exists in Django, updating Supabase ID")
            
            # Check what fields exist in User model
            with connection.cursor() as cursor:
                cursor.execute("PRAGMA table_info(auth_app_user)")
                columns = [col[1] for col in cursor.fetchall()]
            
            # Update user with Supabase information
            updated_fields = []
            if existing_user.email != email:
                existing_user.email = email
                updated_fields.append('email')
            
            if 'supabase_id' in columns and existing_user.supabase_id != supabase_user_id:
                existing_user.supabase_id = supabase_user_id
                updated_fields.append('supabase_id')
                
            # Check if email is verified
            is_verified = _check_email_verified(user_record)
            if 'email_verified' in columns and is_verified and not existing_user.email_verified:
                existing_user.email_verified = True
                updated_fields.append('email_verified')
                logger.info(f"Marked user {email} as email verified from Supabase webhook")
                
            if updated_fields:
                existing_user.save(update_fields=updated_fields)
            
            return JsonResponse({
                "status": "success", 
                "message": "Updated existing Django user"
            })
        except User.DoesNotExist:
            pass
        
        # Create new Django user with information from Supabase
        import string
        import random
        from django.utils.crypto import get_random_string
        
        # Generate a random username if not provided - ensuring uniqueness
        username_base = email.split('@')[0]
        username = username_base
        
        # Check if username exists and append numbers until we find a unique one
        suffix = 1
        while User.objects.filter(username=username).exists():
            username = f"{username_base}_{suffix}"
            suffix += 1
        
        # Generate a random password - user will need to reset it
        temp_password = get_random_string(16)
        
        # Extract metadata if available
        user_meta = user_record.get('raw_user_meta_data', {})
        if isinstance(user_meta, dict) and 'username' in user_meta:
            suggested_username = user_meta.get('username')
            # Check if the suggested username is unique
            if not User.objects.filter(username=suggested_username).exists():
                username = suggested_username
        
        # Check email verification status
        email_verified = _check_email_verified(user_record)
        
        # Check what fields are in the User model
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA table_info(auth_app_user)")
            columns = [col[1] for col in cursor.fetchall()]
        
        # Create the user using only available fields
        try:
            # Start with required fields
            user_kwargs = {
                'username': username,
                'email': email,
                'password': temp_password
            }
            
            # Add optional fields if they exist in the model
            if 'supabase_id' in columns:
                user_kwargs['supabase_id'] = supabase_user_id
                
            if 'email_verified' in columns:
                user_kwargs['email_verified'] = email_verified
                
            # Create the user
            new_user = User.objects.create_user(**user_kwargs)
            
            logger.info(f"Created new Django user {email} from Supabase webhook")
            
            # Create profile if needed and if UserProfile model exists
            try:
                # Try accessing profile through related field
                profile = new_user.profile
            except Exception:
                # If UserProfile model exists, try to create one
                try:
                    from auth_app.models import UserProfile
                    # Check if UserProfile exists
                    try:
                        # Check what fields exist in UserProfile
                        with connection.cursor() as cursor:
                            cursor.execute("PRAGMA table_info(auth_app_userprofile)")
                            profile_columns = [col[1] for col in cursor.fetchall()]
                            
                        # Start with required fields
                        profile_kwargs = {'user': new_user}
                        
                        # Add fields that exist
                        if 'supabase_uid' in profile_columns:
                            profile_kwargs['supabase_uid'] = supabase_user_id
                            
                        if 'verified' in profile_columns:
                            profile_kwargs['verified'] = email_verified
                            
                        # Create profile
                        UserProfile.objects.create(**profile_kwargs)
                    except Exception as e:
                        logger.warning(f"Error checking UserProfile schema: {str(e)}")
                except Exception as e:
                    logger.info(f"UserProfile model not found: {str(e)}")
            
            return JsonResponse({
                "status": "success", 
                "message": "Created new Django user from Supabase webhook"
            })
                
        except Exception as e:
            logger.exception(f"Error creating Django user {email}: {str(e)}")
            return JsonResponse({"status": "error", "message": str(e)}, status=500)
            
    except Exception as e:
        logger.exception(f"Error handling user creation: {str(e)}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

@with_retry()
@transaction.atomic
def handle_user_updated(payload):
    """Handle user update event from Supabase"""
    try:
        # Extract user info from the payload
        user_record = payload.get('record', {})
        supabase_user_id = user_record.get('id')
        email = user_record.get('email')
        
        if not supabase_user_id and not email:
            logger.error("User update webhook missing user identifiers")
            return JsonResponse({"status": "error", "message": "Missing user identifiers"}, status=400)
        
        # Build query to find the user
        query = Q()
        if supabase_user_id:
            query |= Q(supabase_id=supabase_user_id)
        if email:
            query |= Q(email=email)
        
        # Try to find the user
        try:
            user = User.objects.get(query)
            
            # Update fields that might have changed
            if email and user.email != email:
                user.email = email
            
            if supabase_user_id and user.supabase_id != supabase_user_id:
                user.supabase_id = supabase_user_id
            
            # Handle email verification
            email_verified = _check_email_verified(user_record)
            if email_verified and not user.email_verified:
                user.email_verified = True
                logger.info(f"Updated email verification status for user {user.email}")
            
            user.save()
            
            return JsonResponse({
                "status": "success", 
                "message": "Django user updated from Supabase webhook"
            })
        except User.DoesNotExist:
            logger.warning(f"No Django user found for Supabase user {supabase_user_id or email} during update")
            # Create user if it doesn't exist (this can happen if user was created in Supabase first)
            return handle_user_created(payload)
        except User.MultipleObjectsReturned:
            logger.warning(f"Multiple Django users found for Supabase user {supabase_user_id or email} during update")
            # Handle potential duplicates - update the first one and mark others for cleanup
            users = User.objects.filter(query).order_by('date_joined')
            primary_user = users.first()
            
            # Update the primary user
            if email:
                primary_user.email = email
            if supabase_user_id:
                primary_user.supabase_id = supabase_user_id
                
            # Handle email verification for primary user    
            email_verified = _check_email_verified(user_record)
            if email_verified:
                primary_user.email_verified = True
                
            primary_user.save()
            
            # Delete duplicates
            for duplicate in users[1:]:
                duplicate.delete()
                logger.info(f"Deleted duplicate user {duplicate.email} during update")
            
            return JsonResponse({
                "status": "success", 
                "message": f"Updated primary user and removed {users.count()-1} duplicates"
            })
            
    except Exception as e:
        logger.exception(f"Error handling user update: {str(e)}")
        return JsonResponse({"status": "error", "message": str(e)}, status=500)

def _check_email_verified(user_record):
    """Helper function to check if email is verified based on Supabase user record"""
    # Check confirmation timestamp
    if user_record.get('email_confirmed_at'):
        return True
        
    # Check raw user metadata
    user_meta = user_record.get('raw_user_meta_data', {})
    if isinstance(user_meta, dict) and user_meta.get('email_verified') is True:
        return True
        
    # Check confirmed_at field  
    if user_record.get('confirmed_at'):
        return True
        
    return False 
from django.urls import path
from . import views
from . import webhooks
from . import basic_auth
from .views import (
    login, logout, register, verify_email, password_reset, password_reset_confirm,
    account_settings, backup_verify_email, 
    setup_custom_smtp, force_account_reset,
    test_email_sending, resend_verification_email, unsubscribe, delete_account,
    account_sync_status, test_webhook
)

urlpatterns = [
    # Authentication choice page
    path('', views.auth_choice, name='auth_choice'),
    
    path('login/', login, name='login'),
    path('logout/', logout, name='logout'),
    path('register/', register, name='register'),
    path('account/', account_settings, name='account_settings'),
    path('password-reset/', password_reset, name='password_reset'),
    
    # Email verification callback
    path('verify-email/<str:token>/', verify_email, name='verify_email'),
    path('verify-email/', verify_email, name='verify_email_query'),  # For query string token
    
    # Additional routes for handling Supabase callbacks
    path('callback/', verify_email, name='auth_callback'),  # For Supabase callbacks with access_token
    
    # Handle direct Supabase redirect (for when users click email links)
    path('auth/callback/', verify_email, name='direct_auth_callback'),
    
    # Backup verification system
    path('backup-verify/<str:token>/', backup_verify_email, name='backup_verify_email'),
    
    # Password reset confirm - handle both path and query parameters
    path('password-reset-confirm/<str:token>/', 
         password_reset_confirm, 
         name='password_reset_confirm'),
    path('password-reset-confirm/', 
         password_reset_confirm, 
         name='password_reset_confirm_query'),  # For query string token
    
    # Add the SMTP configuration URL path
    path('setup-smtp/', setup_custom_smtp, name='setup_smtp'),
    
    # Test email sending
    path('test-email/', test_email_sending, name='test_email'),
    
    # Webhook for Supabase real-time sync
    path('webhooks/supabase/', webhooks.supabase_webhook_handler, name='supabase_webhook'),
    
    # Add our new account reset URL
    path('reset-account/', force_account_reset, name='force_account_reset'),
    
    # Add URL pattern for resending verification emails
    path('resend-verification/', resend_verification_email, name='resend_verification'),
    
    # Add URL pattern for unsubscribe links
    path('unsubscribe/', unsubscribe, name='unsubscribe'),
    
    # Add URL pattern for account deletion
    path('delete-account/', delete_account, name='delete_account'),
    
    # Add URLs for account synchronization monitoring
    path('sync-status/', account_sync_status, name='account_sync_status'),
    path('test-webhook/', test_webhook, name='test_webhook'),
    
    # Basic Authentication Routes (Simple authentication without Supabase)
    path('basic/login/', basic_auth.basic_login, name='basic_login'),
    path('basic/register/', basic_auth.basic_register, name='basic_register'),
    path('basic/logout/', basic_auth.basic_logout, name='basic_logout'),
    path('basic/delete-account/', basic_auth.basic_delete_account, name='basic_delete_account'),
]
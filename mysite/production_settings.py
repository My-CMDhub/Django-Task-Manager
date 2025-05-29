"""
Production settings for Nexus project.
This file imports all base settings and overrides them for production.
"""

import os
from .settings import *  # Import base settings
import dj_database_url

# Import Supabase - needed for client functions
try:
    from supabase import create_client
    from supabase import Client
except ImportError:
    print("WARNING: Supabase client not found, some features may not work.")
    create_client = None
    Client = None

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY', 'replace-with-secure-key-in-pythonanywhere')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# Updated allowed hosts
ALLOWED_HOSTS = [
    'nexuss-baf9e168e5c4.herokuapp.com',
    'taskmanager-mztm.onrender.com',
    'localhost',
    '127.0.0.1',
]

# Database configuration
# Use SQLite for now, change to PostgreSQL with environment variable later
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

# Look for DATABASE_URL environment variable (used by Render and Heroku)
if 'DATABASE_URL' in os.environ:
    DATABASES['default'] = dj_database_url.config(
        conn_max_age=600,
        conn_health_checks=True,
    )
    print(f"Using database URL from environment: {os.environ['DATABASE_URL'][:10]}...") 
else:
    print("WARNING: No DATABASE_URL environment variable set, and so no databases setup")

# Static files (CSS, JavaScript, Images)
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Security settings
# Conditionally set SECURE_SSL_REDIRECT for local development
LOCAL_DEVELOPMENT = os.environ.get('LOCAL_DEVELOPMENT', 'False').lower() in ('true', '1', 't')
SECURE_SSL_REDIRECT = not LOCAL_DEVELOPMENT

SESSION_COOKIE_SECURE = not LOCAL_DEVELOPMENT
CSRF_COOKIE_SECURE = not LOCAL_DEVELOPMENT

# Only set HSTS if not in local development and not in DEBUG mode
if not LOCAL_DEVELOPMENT and not DEBUG:
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
else:
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

# Supabase settings
# You MUST set these environment variables for authentication to work
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://***REMOVED***.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '***REMOVED***')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', '')

# Default to bypassing Supabase if service key is not set
BYPASS_SUPABASE = False
if not SUPABASE_SERVICE_KEY:
    print("WARNING: SUPABASE_SERVICE_KEY not set, some auth functions will not work!")
    if DEBUG:
        print("DEBUG mode enabled, will create local users only")

# Log Supabase configuration status
print(f"PRODUCTION SETTINGS: Supabase is {'ACTIVE' if not BYPASS_SUPABASE else 'BYPASSED'}. Using URL: {SUPABASE_URL}")

# Additional settings needed in production
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '465'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'False').lower() == 'true'
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'True').lower() == 'true'
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', EMAIL_HOST_USER)

# Log when production settings are loaded
print("PRODUCTION SETTINGS LOADED: BYPASS_SUPABASE is set to", BYPASS_SUPABASE)

# Enable Supabase in production
BYPASS_SUPABASE_RATE_LIMITS = False  # Use rate limits for security

# Email verification settings 
AUTO_VERIFY_USERS = os.environ.get('AUTO_VERIFY_USERS', 'False').lower() in ('true', '1', 't', 'yes')

# Override the get_supabase_admin_client function from settings.py
def get_supabase_admin_client():
    """Get or initialize a Supabase client with admin privileges for production"""
    # Import inside the function to avoid circular imports
    try:
        from supabase import create_client
        
        # Only bypass if explicitly set to True
        if BYPASS_SUPABASE:
            print("Supabase admin client is BYPASSED via settings.BYPASS_SUPABASE")
            return None
            
        # Check if credentials are available
        if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
            print("Missing Supabase admin credentials")
            return None
            
        # Create a new client each time to ensure we have the latest settings
        admin_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        return admin_client
    except Exception as e:
        print(f"Error creating Supabase admin client: {e}")
        return None

# Mistral AI API key for production
MISTRAL_API_KEY = os.environ.get('MISTRAL_API_KEY', '')

# Configure Supabase credentials from environment
SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY', SUPABASE_KEY)

# WhiteNoise for static files
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')  # Add after SecurityMiddleware
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Static files configuration (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [] # Updated to remove os.path.join(BASE_DIR, 'static')

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO', # Adjust as needed
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO', # Adjust as needed
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    }
}

# Ensure log directory exists - PythonAnywhere might need different permissions
os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)

# Set sender name and email
SENDER_NAME = os.environ.get('SENDER_NAME', 'Task Manager')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', EMAIL_HOST_USER)

# Proper format for email with sender name
DEFAULT_FROM_EMAIL = f"{SENDER_NAME} <{SENDER_EMAIL}>" if SENDER_NAME and SENDER_EMAIL else os.environ.get('DEFAULT_FROM_EMAIL_PRODUCTION', 'Task Manager <noreply@nexuss-baf9e168e5c4.herokuapp.com>')
SERVER_EMAIL = os.environ.get('SERVER_EMAIL_PRODUCTION', DEFAULT_FROM_EMAIL)

# Supabase site URL for production
SUPABASE_SITE_URL = os.environ.get('SUPABASE_SITE_URL', 'https://taskmanager-mztm.onrender.com')

# Site configuration
SITE_DOMAIN = os.environ.get('SITE_DOMAIN', 'https://nexuss-baf9e168e5c4.herokuapp.com')
SITE_PROTOCOL = os.environ.get('SITE_PROTOCOL', 'https')
SITE_URL = f"{SITE_PROTOCOL}://{SITE_DOMAIN}"

print(f"PRODUCTION SETTINGS LOADED: BYPASS_SUPABASE is set to {BYPASS_SUPABASE}") 
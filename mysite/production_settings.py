"""
Production settings for Task Manager project.
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
    'taskmanager-mztm.onrender.com', # Your Render app domain
    '.onrender.com', # Allow any Render subdomain for flexibility
] 
# Add other production hosts if needed

# Force Supabase bypass in production
BYPASS_SUPABASE = True  # Always bypass in production, regardless of environment variables
BYPASS_SUPABASE_RATE_LIMITS = True

# Email verification settings 
AUTO_VERIFY_USERS = os.environ.get('AUTO_VERIFY_USERS', 'False').lower() in ('true', '1', 't', 'yes')

# Mistral AI API key for production
MISTRAL_API_KEY = os.environ.get('MISTRAL_API_KEY', '')

# Nullify Supabase credentials if bypassed to prevent accidental use
# The client functions in settings.py will already return None if BYPASS_SUPABASE is True
if BYPASS_SUPABASE:
    SUPABASE_URL = None
    SUPABASE_KEY = None
    SUPABASE_ANON_KEY = None
    SUPABASE_SERVICE_KEY = None
    print("PRODUCTION SETTINGS: Supabase is FULLY BYPASSED. Client functions will return None.")
else:
    # This block should ideally not be hit in production if BYPASS_SUPABASE is True
    print("PRODUCTION SETTINGS: Supabase is ACTIVE. Ensure SUPABASE_URL and keys are set in environment.")
    # SUPABASE_URL = os.environ.get('SUPABASE_URL') # Example if not bypassing
    # SUPABASE_KEY = os.environ.get('SUPABASE_KEY') # Example if not bypassing

# Stronger security settings
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True # Set to True if your Render setup enforces HTTPS
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_REFERRER_POLICY = 'same-origin'

# WhiteNoise for static files
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')  # Add after SecurityMiddleware
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Static files configuration (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
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

# Use SQLite in Render's persistent storage location
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL')
    )
}

# MySQL configuration example (for reference):
"""
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'yourusername$taskmanager',
        'USER': 'yourusername',
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': 'yourusername.mysql.pythonanywhere-services.com',
        'PORT': '',
    }
}
"""

# Email configuration for production
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND_PRODUCTION', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('SMTP_PORT', '465'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'False').lower() == 'true'
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'True').lower() == 'true'
EMAIL_TIMEOUT = 30  # Set timeout to 30 seconds to avoid hanging

# Set sender name and email
SENDER_NAME = os.environ.get('SENDER_NAME', 'Task Manager')
SENDER_EMAIL = os.environ.get('SENDER_EMAIL', EMAIL_HOST_USER)

# Proper format for email with sender name
DEFAULT_FROM_EMAIL = f"{SENDER_NAME} <{SENDER_EMAIL}>" if SENDER_NAME and SENDER_EMAIL else os.environ.get('DEFAULT_FROM_EMAIL_PRODUCTION', 'Task Manager <noreply@taskmanager-mztm.onrender.com>')
SERVER_EMAIL = os.environ.get('SERVER_EMAIL_PRODUCTION', DEFAULT_FROM_EMAIL)

# Supabase site URL for production
SUPABASE_SITE_URL = os.environ.get('SUPABASE_SITE_URL', 'https://taskmanager-mztm.onrender.com')

# Site configuration
SITE_DOMAIN = os.environ.get('SITE_DOMAIN', 'taskmanager-mztm.onrender.com')
SITE_PROTOCOL = os.environ.get('SITE_PROTOCOL', 'https')
SITE_URL = f"{SITE_PROTOCOL}://{SITE_DOMAIN}"

# Cache for storing supabase client
# These are now defined in the base settings.py
# _supabase_client = None
# _supabase_admin_client = None 

print(f"PRODUCTION SETTINGS LOADED: BYPASS_SUPABASE is set to {BYPASS_SUPABASE}") 
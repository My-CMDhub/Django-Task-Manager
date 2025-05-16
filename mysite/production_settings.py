"""
Production settings for Task Manager project.
This file imports all base settings and overrides them for production.
"""

import os
from .settings import *  # Import base settings

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
    '127.0.0.1',
    'localhost',
    '.pythonanywhere.com',  # Allow any subdomain
    'taskmanager-mztm.onrender.com'
]

# Stronger security settings
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = False  # Set to True if your PythonAnywhere account supports HTTPS
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_REFERRER_POLICY = 'same-origin'

# WhiteNoise for static files
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')  # Add after SecurityMiddleware
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Static files configuration (CSS, JavaScript, Images)
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'django.log'),
            'formatter': 'verbose',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['file', 'console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['file', 'console'],
            'level': os.getenv('DJANGO_LOG_LEVEL', 'WARNING'),
            'propagate': False,
        },
        'auth_app': {
            'handlers': ['file', 'console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'tasks': {
            'handlers': ['file', 'console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'chatbot_integration': {
            'handlers': ['file', 'console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}

# Ensure log directory exists - PythonAnywhere might need different permissions
os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)

# Use SQLite in Render's persistent storage location
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join('/opt/render/project/src/', 'db.sqlite3'),
    }
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

# Email configuration - for production you may want to configure mailgun or another service

# Supabase site URL for production
SUPABASE_SITE_URL = os.environ.get('SUPABASE_SITE_URL', 'https://yourusername.pythonanywhere.com')

# Site configuration
SITE_DOMAIN = os.environ.get('SITE_DOMAIN', 'yourusername.pythonanywhere.com')
SITE_PROTOCOL = os.environ.get('SITE_PROTOCOL', 'https')
SITE_URL = f"{SITE_PROTOCOL}://{SITE_DOMAIN}"

# Cache for storing supabase client
# These are now defined in the base settings.py
# _supabase_client = None
# _supabase_admin_client = None 

# Option to completely bypass Supabase in production
# This overrides the default from settings.py
BYPASS_SUPABASE = os.environ.get('BYPASS_SUPABASE_PRODUCTION', 'True').lower() in ('true', '1', 't', 'yes')
BYPASS_SUPABASE_RATE_LIMITS = True  # Usually True for production when bypassing Supabase

# The get_supabase_client and get_supabase_admin_client functions are now in base settings.py
# and will respect the BYPASS_SUPABASE value set here.
# No need to redefine the functions themselves in this file.

# Default Email backend to console if not specified, to prevent NoneType errors
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_HOST = os.environ.get('EMAIL_HOST', '')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'False').lower() == 'true'
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'noreply@example.com')
SERVER_EMAIL = os.environ.get('SERVER_EMAIL', DEFAULT_FROM_EMAIL)

if BYPASS_SUPABASE:
    print("PRODUCTION SETTINGS: Supabase is BYPASSED.")
else:
    print("PRODUCTION SETTINGS: Supabase is ACTIVE.") 
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
_supabase_client = None
_supabase_admin_client = None  # For admin operations

# Option to completely bypass Supabase in production
BYPASS_SUPABASE = os.environ.get('BYPASS_SUPABASE', 'True').lower() in ('true', '1', 't', 'yes')
BYPASS_SUPABASE_RATE_LIMITS = True  # Set to True for production mode when Supabase is problematic

# Define client functions based on BYPASS_SUPABASE setting
if BYPASS_SUPABASE:
    # Bypass functions that return None when Supabase is disabled
    def get_supabase_client():
        """Bypass function that returns None when Supabase is disabled"""
        print("Supabase is bypassed in production, returning None")
        return None
        
    def get_supabase_admin_client():
        """Bypass function that returns None when Supabase is disabled"""
        print("Supabase admin is bypassed in production, returning None")
        return None
else:
    # Standard client functions with compatibility fixes
    def get_supabase_admin_client():
        """Get or initialize a Supabase client with admin privileges, compatible with Render"""
        global _supabase_admin_client
        
        try:
            if _supabase_admin_client is None:
                if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
                    print("Missing Supabase admin credentials")
                    return None
                    
                print(f"Creating new Supabase admin client with URL: {SUPABASE_URL}")
                # Directly create the client without proxy
                from supabase import Client
                _supabase_admin_client = Client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
                print("Supabase admin client created successfully")
                
            return _supabase_admin_client
        except Exception as e:
            print(f"Error creating Supabase admin client: {e}")
            return None

    def get_supabase_client():
        """Get or initialize a Supabase client instance, compatible with Render"""
        global _supabase_client
        try:
            if _supabase_client is None:
                if not SUPABASE_URL:
                    print("Missing Supabase URL")
                    return None
                
                # Use SUPABASE_ANON_KEY first, then fall back to SUPABASE_KEY if needed
                anon_key = SUPABASE_ANON_KEY or SUPABASE_KEY
                if not anon_key:
                    print("Missing Supabase API key")
                    return None
                    
                print(f"Creating new Supabase client with URL: {SUPABASE_URL}")
                # Directly create the client without proxy
                from supabase import Client
                _supabase_client = Client(SUPABASE_URL, anon_key)
                print("Supabase client created successfully")
                
            return _supabase_client
        except Exception as e:
            print(f"Error initializing Supabase client: {str(e)}")
            # Fall back to None, which will cause the code to use Django-only mode
            return None 
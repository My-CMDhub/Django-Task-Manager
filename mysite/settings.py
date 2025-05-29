import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Attempt to import Supabase client, but don't fail if it's not critical for base setup
try:
    from supabase import Client as SupabaseClient # Renamed to avoid conflict if create_client is also imported
except ImportError:
    SupabaseClient = None
    print("WARNING: supabase.Client could not be imported. Supabase features will be unavailable.")

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-!@#your-secret-key-here!@#'

DEBUG = True

ALLOWED_HOSTS = [
    '127.0.0.1',
    'localhost',
    '.ngrok-free.app',  # Allow any ngrok domain
    '01ad-2403-4800-3223-6f01-38bd-c9b9-6243-50d2.ngrok-free.app',  # Add your specific ngrok domain
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',  # Required for Site model
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'auth_app',  # Custom auth app
    'mysite',
    'tasks',  # New tasks app
    # 'django_ratelimit', # Temporarily disabled due to installation issues
    'rest_framework',
    'rest_framework_simplejwt',
    # 'chatbot_app',  # Original chatbot integration - commented out to avoid conflicts
    'chatbot_integration.apps.ChatbotIntegrationConfig',  # Chatbot integration package
    'chatbot_integration.chatbot_app',  # Chatbot app module with app config
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # For serving static files efficiently
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    # 'django_ratelimit.middleware.RateLimitMiddleware', # Temporarily disabled
]


# Allauth settings
ACCOUNT_SIGNUP_FIELDS = ['email', 'password1', 'password2']
ACCOUNT_LOGIN_METHODS = ['email']
ACCOUNT_EMAIL_VERIFICATION = 'none'
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_LOGOUT_ON_PASSWORD_CHANGE = True
ACCOUNT_PREVENT_ENUMERATION = True
ACCOUNT_RATE_LIMITS = {
    'login_failed': '5/5m',
    'signup': '20/1h',
}

# Supabase configuration
from supabase import create_client

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://***REMOVED***.supabase.co')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '***REMOVED***')
SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY', SUPABASE_KEY)  # Use SUPABASE_KEY as fallback
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', '***REMOVED***')
SUPABASE_WEBHOOK_SECRET = os.environ.get('SUPABASE_WEBHOOK_SECRET', '***REMOVED***')
SUPABASE_SYNC_ENABLED = os.environ.get('SUPABASE_SYNC_ENABLED', 'True').lower() in ('true', '1', 't', 'yes')

# Define BYPASS_SUPABASE and BYPASS_SUPABASE_RATE_LIMITS here with defaults
# These can be overridden by production_settings.py or environment variables
BYPASS_SUPABASE = os.environ.get('BYPASS_SUPABASE', 'False').lower() in ('true', '1', 't', 'yes')
BYPASS_SUPABASE_RATE_LIMITS = os.environ.get('BYPASS_SUPABASE_RATE_LIMITS', 'False').lower() in ('true', '1', 't', 'yes')

WEBHOOK_MAX_RETRIES = int(os.environ.get('WEBHOOK_MAX_RETRIES', '3'))

# OpenAI API key
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')

# Supabase Site URL configuration (critical for email verification)
# This tells Supabase where to redirect after verification
SUPABASE_SITE_URL = os.environ.get('SUPABASE_SITE_URL')

# If not set in environment, use the development server URL
if not SUPABASE_SITE_URL:
    SUPABASE_SITE_URL = 'http://127.0.0.1:8000'

# Supabase SMTP Configuration
# These settings will be used when configuring Supabase's email service
# through the admin API (when available)
SUPABASE_SMTP_CONFIG = {
    "SENDER_EMAIL": os.environ.get('SUPABASE_SENDER_EMAIL', 'noreply@yourdomain.com'),
    "SENDER_NAME": os.environ.get('SUPABASE_SENDER_NAME', 'Nexus'),
    "SMTP_HOST": os.environ.get('SMTP_HOST', 'smtp.gmail.com'),
    "SMTP_PORT": int(os.environ.get('SMTP_PORT', '465')),
    "SMTP_USER": os.environ.get('EMAIL_HOST_USER', ''),
    "SMTP_PASS": os.environ.get('EMAIL_HOST_PASSWORD', ''),
    "SMTP_ADMIN_EMAIL": os.environ.get('ADMIN_EMAIL', 'admin@yourdomain.com'),
}

# Cache for storing supabase client
_supabase_client = None
_supabase_admin_client = None  # For admin operations

def get_supabase_client():
    """Get or initialize a Supabase client instance"""
    global _supabase_client
    if BYPASS_SUPABASE:
        print("Supabase client is BYPASSED via settings.BYPASS_SUPABASE")
        return None
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
            _supabase_client = create_client(SUPABASE_URL, anon_key)
            print("Supabase client created successfully")
            
        return _supabase_client
    except Exception as e:
        print(f"Error initializing Supabase client: {str(e)}")
        # Fall back to None, which will cause the code to use Django-only mode
        return None

def get_supabase_admin_client():
    """Get or initialize a Supabase client with admin privileges"""
    global _supabase_admin_client
    if BYPASS_SUPABASE:
        print("Supabase admin client is BYPASSED via settings.BYPASS_SUPABASE")
        return None
    try:
        if _supabase_admin_client is None:
            if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
                print("Missing Supabase admin credentials")
                return None
                
            print(f"Creating new Supabase admin client with URL: {SUPABASE_URL}")
            _supabase_admin_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
            print("Supabase admin client created successfully")
            
        return _supabase_admin_client
    except Exception as e:
        print(f"Error initializing Supabase admin client: {str(e)}")
        return None

# Authentication settings
AUTHENTICATION_BACKENDS = [
    'auth_app.admin_backend.AdminBackend',  # Admin-specific backend first (with higher priority)
    'auth_app.backends.EmailBackend',
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Session settings
SESSION_COOKIE_AGE = 1209600  # 2 weeks
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_SAVE_EVERY_REQUEST = True
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# CSRF protection
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True

# Security headers
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# JWT settings
from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

# Custom User Model
AUTH_USER_MODEL = 'auth_app.User'

# Login URL for @login_required decorator
LOGIN_URL = '/auth/login/'

ROOT_URLCONF = 'mysite.urls'

TEMPLATES = [
       {
           'BACKEND': 'django.template.backends.django.DjangoTemplates',
           'DIRS': [os.path.join(BASE_DIR, 'templates')],
           'APP_DIRS': True,
           'OPTIONS': {
               'context_processors': [
                   'django.template.context_processors.debug',
                   'django.template.context_processors.request',
                   'django.contrib.auth.context_processors.auth',
                   'django.contrib.messages.context_processors.messages',
               ],
           },
       },
   ]

WSGI_APPLICATION = 'mysite.wsgi.application'

# Add/modify this in your production_settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),  # Use local path for development
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),
]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Email settings
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.environ.get('SMTP_PORT', '465'))
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'False').lower() == 'true'
EMAIL_USE_SSL = os.environ.get('EMAIL_USE_SSL', 'True').lower() == 'true'
DEFAULT_FROM_EMAIL = os.environ.get('SENDER_EMAIL', EMAIL_HOST_USER) or f"Nexus <{EMAIL_HOST_USER}>"
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Additional email headers to improve deliverability
EMAIL_EXTRA_HEADERS = {
    'X-Auto-Response-Suppress': 'OOF, DR, RN, NRN, AutoReply',
    'X-Priority': '1',
    'X-MSMail-Priority': 'High',
    'Importance': 'High',
    'Precedence': 'bulk',
    'Auto-Submitted': 'auto-generated',
}

# Only log email configuration if not suppressed
if not os.environ.get('SUPPRESS_EMAIL_WARNINGS') == 'true':
    print(f"Email configuration: Backend={EMAIL_BACKEND}, Host={EMAIL_HOST}, Port={EMAIL_PORT}")
    print(f"Using from email: {DEFAULT_FROM_EMAIL}")
    print("WARNING: Using Gmail SMTP. Please set EMAIL_HOST_PASSWORD environment variable.")
    print("For Gmail, you may need to create an App Password: https://myaccount.google.com/apppasswords")
    print("NOTE: To avoid spam filtering, add SPF and DKIM records for your domain.")
    print("Gmail has built-in SPF/DKIM support, but deliverability to some providers may be limited.")

# Instructions for improving email deliverability (for reference)
"""
IMPORTANT EMAIL DELIVERABILITY TIPS:
1. Set up SPF record for your domain:
   Add a TXT record: v=spf1 include:_spf.google.com ~all

2. Set up DKIM for your domain:
   Follow Gmail's instructions at https://support.google.com/a/answer/174124

3. Set up DMARC for your domain:
   Add a TXT record: v=DMARC1; p=none; rua=mailto:your-email@your-domain.com

4. Use consistent FROM addresses that match your domain

5. For custom domain emails, consider using a dedicated email service like:
   - Amazon SES
   - SendGrid
   - Mailgun
   
Gmail may work for development, but for production, a dedicated email service
with proper authentication setup is strongly recommended.
"""

# Domain settings for verification links
SITE_DOMAIN = os.environ.get('SITE_DOMAIN', '127.0.0.1:8000')
SITE_PROTOCOL = os.environ.get('SITE_PROTOCOL', 'http')
SITE_URL = f"{SITE_PROTOCOL}://{SITE_DOMAIN}"

# Supabase Project Site URL - CRITICAL for email verification
# This should be set to your Django site URL
if not os.environ.get('SUPABASE_SITE_URL'):
    os.environ['SUPABASE_SITE_URL'] = SITE_URL
    print(f"Setting SUPABASE_SITE_URL to {SITE_URL}")

# Django Allauth settings (if you choose to use it later)
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_VERIFICATION = 'mandatory' # Can be 'optional' or 'none'
LOGIN_REDIRECT_URL = '/'
ACCOUNT_LOGOUT_REDIRECT_URL = '/'

# Default token timeout for password resets (and potentially other tokens)
# Django's default is 3 days (259200 seconds)
PASSWORD_RESET_TIMEOUT_DAYS = int(os.environ.get('PASSWORD_RESET_TIMEOUT_DAYS', 3))
# The actual timeout in seconds is derived from this in Django's token generator.

# Control whether to attempt sending verification email via Supabase
SUPABASE_SEND_VERIFICATION_EMAIL = os.environ.get('SUPABASE_SEND_VERIFICATION_EMAIL', 'True').lower() in ('true', '1', 't')

# Enhance logging for webhook events
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
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'webhook.log'),
            'formatter': 'verbose',
        },
        'chatbot_file': {
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'logs', 'chatbot.log'),
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
        },
        'auth_app.webhooks': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'chatbot_integration': {
            'handlers': ['console', 'chatbot_file'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}

# Ensure log directory exists
os.makedirs(os.path.join(BASE_DIR, 'logs'), exist_ok=True)

# Mistral AI API key for chatbot
CHATBOT_SETTINGS = {
    'MISTRAL_API_KEY': os.environ.get('MISTRAL_API_KEY'), # Changed from OPENAI_API_KEY
    'VECTOR_DB_PATH': os.path.join(BASE_DIR, 'PKL_file'),
    'TRAINING_DATA_PATH': os.path.join(BASE_DIR, 'data'),
}

# Site ID for django.contrib.sites
SITE_ID = 1

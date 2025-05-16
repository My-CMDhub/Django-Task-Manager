"""
WSGI config for PythonAnywhere deployment.

This module contains the WSGI application used by PythonAnywhere's servers.
"""

import os
import sys

# Add your project directory to the sys.path
path = '/home/yourusername/Task_Manager'  # IMPORTANT: Replace 'yourusername' with your PythonAnywhere username
if path not in sys.path:
    sys.path.append(path)

# Set environment variables for sensitive settings
os.environ['DJANGO_SETTINGS_MODULE'] = 'mysite.production_settings'
os.environ['SECRET_KEY'] = 'replace-with-your-secret-key-here'  # Generate a secure key for production

# Set database configuration if using MySQL
# os.environ['DB_PASSWORD'] = 'your-mysql-password'

# Set Supabase configuration
os.environ['SUPABASE_URL'] = 'https://***REMOVED***.supabase.co'  # Replace with your Supabase URL
os.environ['SUPABASE_KEY'] = 'your-supabase-key'  # Replace with your Supabase key
os.environ['SUPABASE_ANON_KEY'] = 'your-supabase-anon-key'  # Replace with your Supabase anon key
os.environ['SUPABASE_SERVICE_KEY'] = 'your-supabase-service-key'  # Replace with your Supabase service key

# Set site domain for verification links
os.environ['SITE_DOMAIN'] = 'yourusername.pythonanywhere.com'  # Replace with your PythonAnywhere domain
os.environ['SITE_PROTOCOL'] = 'https'
os.environ['SUPABASE_SITE_URL'] = 'https://yourusername.pythonanywhere.com'  # Replace with your PythonAnywhere domain

# Set OpenAI API key if using chatbot
os.environ['OPENAI_API_KEY'] = 'your-openai-api-key'  # Replace with your OpenAI API key

# Import Django WSGI application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application() 
"""
ASGI config for mysite project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

# Use production settings when running on Render or other production environments
PRODUCTION_ENVS = ['render', 'herokuapp.com', 'pythonanywhere']

# Check if we're in a production environment
is_production = any(env in os.environ.get('SITE_DOMAIN', '') for env in PRODUCTION_ENVS) or \
               os.environ.get('DJANGO_ENV') == 'production'

if is_production:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.production_settings')
    print("Using production settings")
else:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
    print("Using development settings")

application = get_asgi_application()

# Example Django integration for Nexus project

"""
This file shows how to integrate the chatbot URLs into your Django project's urls.py file.
"""

# In your project's main urls.py file, add:

"""
from django.urls import path, include

urlpatterns = [
    # ... existing URL patterns
    path('api/chatbot/', include('chatbot_app.urls')),
]
"""

# In your settings.py file, add:

"""
INSTALLED_APPS = [
    # ... existing apps
    'chatbot_app',
]

# Chatbot settings
CHATBOT_SETTINGS = {
    'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
    'VECTOR_DB_PATH': os.path.join(BASE_DIR, 'PKL_file'),
    'TRAINING_DATA_PATH': os.path.join(BASE_DIR, 'data'),
}
"""

# Integration with Auth middleware:

"""
from django.contrib.auth.middleware import AuthenticationMiddleware
from rest_framework.authentication import SessionAuthentication, TokenAuthentication

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}
"""

# Post-installation steps:

"""
1. Run migrations to create chatbot tables:
   python manage.py makemigrations chatbot_app
   python manage.py migrate

2. Initialize the chatbot:
   python manage.py init_chatbot

3. Copy the React components to your frontend project:
   - ChatbotButton.jsx and ChatbotButton.css
   - ChatbotModal.jsx and ChatbotModal.css
""" 
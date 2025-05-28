#!/usr/bin/env python
"""
Chatbot Integration Checker Script

This script checks if the chatbot is properly integrated with a Django project.
Run it after installing the chatbot components to verify everything is working.
"""

import os
import sys
import importlib
from importlib.util import find_spec

GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'

def success(message):
    print(f"{GREEN}✓ {message}{RESET}")

def warning(message):
    print(f"{YELLOW}⚠ {message}{RESET}")

def error(message):
    print(f"{RED}✗ {message}{RESET}")

def check_django_settings():
    """Check if Django settings can be imported and chatbot app is installed."""
    try:
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'task_manager.settings')
        from django.conf import settings
        
        if hasattr(settings, 'INSTALLED_APPS') and 'chatbot_app' in settings.INSTALLED_APPS:
            success("chatbot_app is in INSTALLED_APPS")
        else:
            error("chatbot_app is not in INSTALLED_APPS")
            print("   Add 'chatbot_app' to INSTALLED_APPS in your settings.py file")
        
        if hasattr(settings, 'CHATBOT_SETTINGS'):
            success("CHATBOT_SETTINGS is defined in settings.py")
        else:
            warning("CHATBOT_SETTINGS is not defined in settings.py")
            print("   Consider adding CHATBOT_SETTINGS to your settings.py for additional configuration")
        
        return True
    except ImportError:
        error("Could not import Django settings")
        print("   Make sure you're running this script from your Django project directory")
        return False

def check_dependencies():
    """Check if required dependencies are installed."""
    dependencies = {
        'llama_index': 'llama-index',
        'openai': 'openai',
        'dotenv': 'python-dotenv',
        'nltk': 'nltk',
        'dateutil': 'python-dateutil',
    }
    
    all_installed = True
    for module, package in dependencies.items():
        if find_spec(module):
            success(f"{package} is installed")
        else:
            error(f"{package} is not installed")
            print(f"   Install it with: pip install {package}")
            all_installed = False
    
    return all_installed

def check_directories():
    """Check if required directories exist."""
    directories = {
        'PKL_file': 'Vector database',
        'data': 'Training data',
    }
    
    all_exist = True
    for dir_name, description in directories.items():
        if os.path.isdir(dir_name):
            success(f"{dir_name}/ directory exists ({description})")
        else:
            error(f"{dir_name}/ directory does not exist ({description})")
            print(f"   Create it with: mkdir -p {dir_name}")
            all_exist = False
    
    return all_exist

def check_env_variables():
    """Check if required environment variables are set."""
    if 'OPENAI_API_KEY' in os.environ:
        success("OPENAI_API_KEY environment variable is set")
    else:
        from dotenv import load_dotenv
        load_dotenv()
        if 'OPENAI_API_KEY' in os.environ:
            success("OPENAI_API_KEY is set in .env file")
        else:
            error("OPENAI_API_KEY environment variable is not set")
            print("   Set it in your .env file or export it in your shell")
            return False
    
    return True

def check_chatbot_app():
    """Check if chatbot_app is properly installed."""
    try:
        import chatbot_app
        success("chatbot_app can be imported")
        
        from chatbot_app.models import ChatbotConversation, ChatMessage
        success("chatbot_app models can be imported")
        
        return True
    except ImportError as e:
        error(f"Error importing chatbot_app: {str(e)}")
        print("   Make sure chatbot_app is in your Python path")
        return False

def check_urls():
    """Check if chatbot URLs are defined."""
    try:
        from django.urls import reverse, NoReverseMatch
        try:
            reverse('chatbot_app:message')
            success("chatbot_app:message URL is defined")
        except NoReverseMatch:
            error("chatbot_app:message URL is not defined")
            print("   Add chatbot_app URLs to your urls.py")
        
        return True
    except ImportError:
        error("Could not import Django URL module")
        return False

def main():
    print("\n===== Nexus Chatbot Integration Checker =====\n")
    
    django_ok = check_django_settings()
    if not django_ok:
        return
    
    dependencies_ok = check_dependencies()
    directories_ok = check_directories()
    env_ok = check_env_variables()
    chatbot_app_ok = check_chatbot_app()
    urls_ok = check_urls()
    
    print("\n===== Summary =====\n")
    
    if all([dependencies_ok, directories_ok, env_ok, chatbot_app_ok, urls_ok]):
        success("All checks passed! The chatbot integration looks good.")
        print("\nNext steps:")
        print("1. Run migrations:")
        print("   python manage.py makemigrations chatbot_app")
        print("   python manage.py migrate")
        print("2. Initialize the chatbot:")
        print("   python manage.py init_chatbot")
        print("3. Add the React components to your frontend")
    else:
        warning("Some checks failed. Please fix the issues above.")

if __name__ == "__main__":
    main() 
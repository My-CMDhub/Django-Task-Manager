#!/usr/bin/env python
import os
import django
import sys

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

# Import required models after Django is set up
from django.contrib.auth import get_user_model
from chatbot_integration.chatbot_app.models import Conversation
from chatbot_integration.chatbot_app.views import generate_bot_response

User = get_user_model()

def test_chatbot_response(query):
    """Test the chatbot's response to a given query"""
    # Get the first user (or create one if none exists)
    user = User.objects.first()
    if not user:
        print("No users found in the database. Please create a user first.")
        return
    
    # Get or create a conversation for this user
    conversation, created = Conversation.objects.get_or_create(user=user)
    
    # Generate response
    print(f"\nUser: {query}")
    response = generate_bot_response(user, conversation, query)
    print(f"Chatbot: {response}\n")
    
    return response

def run_test_category(category_name, queries):
    """Run tests for a specific category of queries"""
    print(f"\n{'=' * 30}")
    print(f"Testing {category_name} queries")
    print(f"{'=' * 30}")
    
    for query in queries:
        test_chatbot_response(query)

if __name__ == "__main__":
    # Test a specific query if provided
    if len(sys.argv) > 1:
        test_chatbot_response(sys.argv[1])
    else:
        # Define test categories with specific queries
        test_categories = {
            "Greetings": [
                "Hello",
                "Good morning",
                "Hey there",
                "Hi assistant"
            ],
            "Task Inventory": [
                "what I have?",
                "What do I have?",
                "Show me what I have",
                "Tell me what I have",
                "My stuff"
            ],
            "Task Management": [
                "show me my tasks",
                "list my tasks",
                "show me my pending tasks",
                "show me my completed tasks",
                "mark completed",
                "mark all overdue tasks as completed"
            ],
            "Project Management": [
                "show me my projects",
                "list my projects",
                "project status"
            ],
            "Completed Tasks": [
                "show me my completed tasks",
                "what completed tasks do I have",
                "list completed tasks",
                "any completed tasks",
                "what are my completed tasks"
            ],
            "Thank You Responses": [
                "thanks",
                "thank you",
                "thanks buddy",
                "ty",
                "thx",
                "I appreciate your help",
                "thank you so much"
            ],
            "Unclear Queries": [
                "test",
                "???",
                "hmm",
                "xyz",
                "abc def"
            ],
            "Farewell": [
                "Thanks, goodbye!",
                "See you later",
                "I have to go now",
                "bye"
            ]
        }
        
        # Run tests for each category
        for category, queries in test_categories.items():
            run_test_category(category, queries) 
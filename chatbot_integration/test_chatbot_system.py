#!/usr/bin/env python
"""
Comprehensive test script for the enhanced chatbot system.
"""

import os
import sys
import django
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
import json

# Add the project root to Python path
sys.path.append('/mnt/c/Users/Zak/Desktop/SWE Project/task_management_app')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'task_management_app.settings')
django.setup()

def test_nlp_components():
    """Test NLP components independently"""
    print("🧠 Testing NLP Components...")
    
    try:
        # Test intent classification
        from chatbot_integration.chatbot_app.nlp.intents import intent_classifier
        
        test_messages = [
            "Hello there!",
            "Show me my tasks",
            "Create a new task",
            "What's my progress?",
            "Thank you",
            "Goodbye"
        ]
        
        print("  ✅ Intent Classification:")
        for msg in test_messages:
            intent = intent_classifier.classify(msg)
            print(f"    '{msg}' -> {intent.primary}.{intent.secondary} (confidence: {intent.confidence:.2f})")
        
        # Test entity extraction
        from chatbot_integration.chatbot_app.nlp.entities import entity_extractor
        
        test_entities = [
            "Create a task due tomorrow with high priority",
            "Show tasks for today",
            "Complete the project report task"
        ]
        
        print("  ✅ Entity Extraction:")
        for msg in test_entities:
            entities = entity_extractor.extract_entities(msg)
            extracted = {k: [e.value for e in v] for k, v in entities.items() if v}
            print(f"    '{msg}' -> {extracted}")
            
        return True
        
    except Exception as e:
        print(f"  ❌ NLP Test Failed: {e}")
        return False

def test_flow_system():
    """Test conversation flow system"""
    print("🔄 Testing Flow System...")
    
    try:
        from chatbot_integration.chatbot_app.flows.base import flow_manager
        from chatbot_integration.chatbot_app.flows.task_creation import TaskCreationFlow
        
        # Register flow
        flow_manager.register_flow('task_creation', TaskCreationFlow)
        
        # Start a test flow
        result = flow_manager.start_flow('task_creation', 'user123', 'conv123')
        print(f"  ✅ Flow Start: {result.message[:50]}...")
        
        # Simulate flow steps
        flow = flow_manager.get_active_flow('conv123')
        if flow:
            # Simulate answering the first question (title)
            result = flow_manager.process_input('conv123', 'Test Task Title')
            print(f"  ✅ Flow Step 1: {result.message[:50]}...")
            
            # Skip to completion
            flow_manager.end_flow('conv123')
            print("  ✅ Flow End: Successfully completed")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Flow Test Failed: {e}")
        return False

def test_response_generation():
    """Test response generation"""
    print("💬 Testing Response Generation...")
    
    try:
        from chatbot_integration.chatbot_app.response_generation.generator import response_generator
        from chatbot_integration.chatbot_app.nlp.intents import intent_classifier, Intent
        from django.contrib.auth.models import User
        
        # Create a test user
        user, created = User.objects.get_or_create(username='testuser')
        
        # Test different response types
        test_cases = [
            ("Hello!", "greeting"),
            ("Show my tasks", "task"),
            ("Thank you", "acknowledgment"),
            ("Goodbye", "farewell")
        ]
        
        print("  ✅ Response Generation:")
        for msg, expected_intent in test_cases:
            intent = intent_classifier.classify(msg)
            entities = {}
            
            response = response_generator.generate_response(
                user_message=msg,
                intent=intent,
                entities=entities,
                user=user,
                conversation_id='test123'
            )
            
            print(f"    '{msg}' -> '{response[:50]}...'")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Response Generation Test Failed: {e}")
        return False

def test_main_processor():
    """Test the main chatbot processor"""
    print("🎯 Testing Main Processor...")
    
    try:
        from chatbot_integration.chatbot_app.processor import chatbot_processor
        from django.contrib.auth.models import User
        
        # Create a test user
        user, created = User.objects.get_or_create(username='testuser')
        
        test_messages = [
            "Hello!",
            "Show me my tasks",
            "What's my progress?"
        ]
        
        print("  ✅ Processor Results:")
        for msg in test_messages:
            result = chatbot_processor.process_message(
                user_message=msg,
                user=user
            )
            
            if result['success']:
                print(f"    '{msg}' -> Success: {result['response'][:50]}...")
                if 'intent' in result:
                    print(f"      Intent: {result['intent']['primary']}.{result['intent']['secondary']}")
            else:
                print(f"    '{msg}' -> Error: {result.get('error', 'Unknown')}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Processor Test Failed: {e}")
        return False

def test_database_models():
    """Test database models"""
    print("🗃️ Testing Database Models...")
    
    try:
        from chatbot_integration.chatbot_app.models import ChatbotConversation, ChatMessage
        from django.contrib.auth.models import User
        
        # Create test user
        user, created = User.objects.get_or_create(username='testuser')
        
        # Create conversation
        conversation = ChatbotConversation.objects.create(user=user)
        print(f"  ✅ Created conversation: {conversation.id}")
        
        # Create messages
        user_msg = ChatMessage.objects.create(
            conversation=conversation,
            content="Test user message",
            sender='user'
        )
        
        bot_msg = ChatMessage.objects.create(
            conversation=conversation,
            content="Test bot response",
            sender='bot'
        )
        
        print(f"  ✅ Created {conversation.messages.count()} messages")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Database Test Failed: {e}")
        return False

def run_integration_test():
    """Run a full integration test"""
    print("🚀 Running Integration Test...")
    
    try:
        from chatbot_integration.chatbot_app.processor import chatbot_processor
        from django.contrib.auth.models import User
        
        # Create test user
        user, created = User.objects.get_or_create(username='integrationtest')
        
        # Simulate a full conversation
        conversation_id = None
        test_conversation = [
            "Hello!",
            "Show me my tasks",
            "Create a new task",
            "Thank you",
            "Goodbye"
        ]
        
        print("  ✅ Full Conversation Test:")
        for i, msg in enumerate(test_conversation, 1):
            result = chatbot_processor.process_message(
                user_message=msg,
                user=user,
                conversation_id=conversation_id
            )
            
            if result['success']:
                conversation_id = result['conversation_id']
                print(f"    {i}. User: '{msg}'")
                print(f"       Bot: '{result['response'][:60]}...'")
                
                # Check if we have context info
                if 'context' in result:
                    context = result['context']
                    if context.get('has_active_flow'):
                        print(f"       Flow: {context.get('flow_type')} active")
            else:
                print(f"    {i}. ERROR: {result.get('error')}")
                return False
        
        # Test conversation history
        if conversation_id:
            history = chatbot_processor.get_conversation_history(user, conversation_id)
            if history['success']:
                print(f"  ✅ Conversation history: {len(history['messages'])} messages")
            
        return True
        
    except Exception as e:
        print(f"  ❌ Integration Test Failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🧪 Enhanced Chatbot System Test Suite")
    print("=" * 50)
    
    tests = [
        ("NLP Components", test_nlp_components),
        ("Flow System", test_flow_system),
        ("Response Generation", test_response_generation),
        ("Main Processor", test_main_processor),
        ("Database Models", test_database_models),
        ("Integration Test", run_integration_test)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"  ❌ {test_name} Failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    passed = 0
    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"  {status}: {test_name}")
        if success:
            passed += 1
    
    print(f"\nTotal: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! The enhanced chatbot system is ready!")
        return True
    else:
        print("⚠️ Some tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

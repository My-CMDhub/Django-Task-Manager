#!/usr/bin/env python3
"""
Comprehensive Chatbot Testing Suite
Tests all specified query types for task and project retrieval, automation, and actions
"""

import os
import sys
import django
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'nexus.settings')
django.setup()

from django.contrib.auth.models import User
from chatbot_app.models import Conversation
from chatbot_app.views import generate_bot_response
import time

def create_test_user():
    """Create or get test user"""
    try:
        user = User.objects.get(username='testuser')
    except User.DoesNotExist:
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
    return user

def create_test_conversation(user):
    """Create or get test conversation"""
    conversation, _ = Conversation.objects.get_or_create(
        user=user,
        defaults={'title': 'Test Conversation'}
    )
    return conversation

def test_query(user, conversation, query, expected_keywords=None, should_work=True):
    """Test a single query and analyze the response"""
    print(f"\n🔍 Testing: '{query}'")
    print("-" * 50)
    
    try:
        start_time = time.time()
        response = generate_bot_response(user, conversation, query)
        end_time = time.time()
        
        print(f"Response ({end_time - start_time:.2f}s): {response}")
        
        if expected_keywords:
            found_keywords = []
            missing_keywords = []
            for keyword in expected_keywords:
                if keyword.lower() in response.lower():
                    found_keywords.append(keyword)
                else:
                    missing_keywords.append(keyword)
            
            if found_keywords:
                print(f"✅ Found keywords: {', '.join(found_keywords)}")
            if missing_keywords:
                print(f"⚠️  Missing keywords: {', '.join(missing_keywords)}")
        
        # Check for error indicators
        error_indicators = ['error', 'issue', 'problem', 'trouble', 'cannot access', 'failed']
        has_errors = any(indicator in response.lower() for indicator in error_indicators)
        
        if has_errors and should_work:
            print("❌ ISSUE: Response contains error indicators")
            return False
        elif not has_errors and should_work:
            print("✅ SUCCESS: Response looks good")
            return True
        else:
            print("ℹ️  Response as expected")
            return True
            
    except Exception as e:
        print(f"❌ EXCEPTION: {str(e)}")
        return False

def main():
    print("🧪 COMPREHENSIVE CHATBOT TESTING SUITE")
    print("=" * 60)
    
    # Setup
    user = create_test_user()
    conversation = create_test_conversation(user)
    
    # Test Categories
    test_results = {
        'passed': 0,
        'failed': 0,
        'total': 0
    }
    
    # A. TASK/PROJECT RETRIEVAL TESTS
    print("\n🔸 A. TASK/PROJECT RETRIEVAL TESTS")
    print("=" * 60)
    
    # Task Retrieval Tests
    task_retrieval_tests = [
        # Basic task queries
        ("what are my tasks", ["tasks", "here are"]),
        ("show my tasks", ["tasks"]),
        ("my tasks", ["tasks"]),
        ("what tasks do I have", ["tasks", "have"]),
        ("list my tasks", ["tasks"]),
        
        # Filtered task queries
        ("show completed tasks", ["completed", "tasks"]),
        ("what tasks are completed", ["completed"]),
        ("show overdue tasks", ["overdue"]),
        ("show tasks due today", ["today", "due"]),
        ("show high priority tasks", ["priority", "high"]),
        ("show tasks for this week", ["week", "tasks"]),
        ("show tasks for tomorrow", ["tomorrow"]),
        
        # Search and specific queries
        ("show tasks assigned to me", ["assigned", "tasks"]),
        ("show tasks I created", ["created", "tasks"]),
        ("show tasks by status", ["status", "tasks"]),
        ("show tasks by priority", ["priority", "tasks"]),
        ("show tasks with report", ["report", "tasks"]),
        ("find tasks about meeting", ["meeting", "tasks"]),
        ("search tasks for design", ["design", "tasks"]),
        
        # Existence queries
        ("do I have any tasks", ["tasks"]),
        ("do I have any completed tasks", ["completed", "tasks"]),
        ("how many tasks do I have", ["tasks"]),
        ("how many completed tasks", ["completed"]),
    ]
    
    print("\n📋 Testing Task Retrieval Queries...")
    for query, keywords in task_retrieval_tests:
        result = test_query(user, conversation, query, keywords)
        test_results['total'] += 1
        if result:
            test_results['passed'] += 1
        else:
            test_results['failed'] += 1
    
    # Project Retrieval Tests
    project_retrieval_tests = [
        ("what are my projects", ["projects"]),
        ("show my projects", ["projects"]),
        ("my projects", ["projects"]),
        ("what projects do I have", ["projects"]),
        ("list my projects", ["projects"]),
        ("show active projects", ["active", "projects"]),
        ("show completed projects", ["completed", "projects"]),
        ("show recent projects", ["recent", "projects"]),
        ("show projects with website", ["website", "projects"]),
        ("find projects about marketing", ["marketing", "projects"]),
        ("do I have any projects", ["projects"]),
        ("how many projects do I have", ["projects"]),
    ]
    
    print("\n📂 Testing Project Retrieval Queries...")
    for query, keywords in project_retrieval_tests:
        result = test_query(user, conversation, query, keywords)
        test_results['total'] += 1
        if result:
            test_results['passed'] += 1
        else:
            test_results['failed'] += 1
    
    # Statistics/Summary Tests
    statistics_tests = [
        ("show statistics", ["statistics", "summary"]),
        ("show my statistics", ["statistics"]),
        ("show my task statistics", ["task", "statistics"]),
        ("show my project statistics", ["project", "statistics"]),
        ("show my dashboard", ["dashboard", "summary"]),
        ("show my summary", ["summary"]),
        ("show my progress", ["progress"]),
        ("give me a summary", ["summary"]),
        ("how am I doing", ["doing", "tasks"]),
        ("what's my progress", ["progress"]),
    ]
    
    print("\n📊 Testing Statistics/Summary Queries...")
    for query, keywords in statistics_tests:
        result = test_query(user, conversation, query, keywords)
        test_results['total'] += 1
        if result:
            test_results['passed'] += 1
        else:
            test_results['failed'] += 1
    
    # B. AUTOMATION/ACTION TESTS
    print("\n🔸 B. AUTOMATION/ACTION TESTS")
    print("=" * 60)
    
    # Task Completion Tests
    task_completion_tests = [
        ("mark as complete", ["complete", "which", "task"]),
        ("mark as completed", ["completed"]),
        ("complete my task", ["complete"]),
        ("complete my tasks", ["complete"]),
        ("complete task", ["complete"]),
        ("complete tasks", ["complete"]),
        ("finish my task", ["finish"]),
        ("finish my tasks", ["finish"]),
        ("mark it as complete", ["complete"]),
        ("mark this as complete", ["complete"]),
        ("mark this task as complete", ["complete"]),
        ("mark all as complete", ["all", "complete"]),
        ("mark all tasks as complete", ["all", "tasks", "complete"]),
        ("mark all overdue tasks as complete", ["overdue", "complete"]),
    ]
    
    print("\n✅ Testing Task Completion Commands...")
    for query, keywords in task_completion_tests:
        result = test_query(user, conversation, query, keywords)
        test_results['total'] += 1
        if result:
            test_results['passed'] += 1
        else:
            test_results['failed'] += 1
    
    # Task Deletion Tests  
    task_deletion_tests = [
        ("delete task", ["delete", "task"]),
        ("delete my task", ["delete"]),
        ("remove task", ["remove", "task"]),
        ("delete this task", ["delete"]),
        ("delete all tasks", ["delete", "all"]),
        ("delete overdue tasks", ["delete", "overdue"]),
    ]
    
    print("\n🗑️  Testing Task Deletion Commands...")
    for query, keywords in task_deletion_tests:
        result = test_query(user, conversation, query, keywords)
        test_results['total'] += 1
        if result:
            test_results['passed'] += 1
        else:
            test_results['failed'] += 1
    
    # Project Deletion Tests
    project_deletion_tests = [
        ("delete project", ["delete", "project"]),
        ("delete my project", ["delete", "project"]),
        ("remove project", ["remove", "project"]),
        ("delete this project", ["delete", "project"]),
        ("delete all projects", ["delete", "all", "projects"]),
    ]
    
    print("\n🗂️  Testing Project Deletion Commands...")
    for query, keywords in project_deletion_tests:
        result = test_query(user, conversation, query, keywords)
        test_results['total'] += 1
        if result:
            test_results['passed'] += 1
        else:
            test_results['failed'] += 1
    
    # EDGE CASES AND ERROR HANDLING
    print("\n🔸 C. EDGE CASES AND ERROR HANDLING")
    print("=" * 60)
    
    edge_case_tests = [
        # Ambiguous queries
        ("complete", ["complete"]),
        ("delete", ["delete"]),
        ("tasks", ["tasks"]),
        ("show", ["show"]),
        
        # Nonsensical queries
        ("purple monkey dishwasher", ["understand", "help", "rephrase"]),
        ("asdfghjkl", ["understand", "help"]),
        ("123456", ["understand", "help"]),
        
        # Empty/minimal queries
        ("?", ["understand", "help"]),
        ("help", ["help"]),
        ("what", ["help", "understand"]),
    ]
    
    print("\n🔍 Testing Edge Cases and Error Handling...")
    for query, keywords in edge_case_tests:
        result = test_query(user, conversation, query, keywords, should_work=True)
        test_results['total'] += 1
        if result:
            test_results['passed'] += 1
        else:
            test_results['failed'] += 1
    
    # CONVERSATION FLOW TESTS
    print("\n🔸 D. CONVERSATION FLOW TESTS")
    print("=" * 60)
    
    print("\n💬 Testing Multi-Turn Conversations...")
    
    # Test conversation flow
    flow_tests = [
        ("hello", ["hello", "hi", "tasks"]),
        ("show my tasks", ["tasks"]),
        ("mark the first one as complete", ["complete"]),
        ("thank you", ["welcome", "help"]),
        ("goodbye", ["goodbye", "bye"]),
    ]
    
    for query, keywords in flow_tests:
        result = test_query(user, conversation, query, keywords)
        test_results['total'] += 1
        if result:
            test_results['passed'] += 1
        else:
            test_results['failed'] += 1
    
    # FINAL RESULTS
    print("\n" + "=" * 60)
    print("🎯 FINAL TEST RESULTS")
    print("=" * 60)
    
    print(f"✅ Tests Passed: {test_results['passed']}")
    print(f"❌ Tests Failed: {test_results['failed']}")
    print(f"📊 Total Tests: {test_results['total']}")
    
    success_rate = (test_results['passed'] / test_results['total']) * 100 if test_results['total'] > 0 else 0
    print(f"🎯 Success Rate: {success_rate:.1f}%")
    
    if success_rate >= 90:
        print("\n🎉 EXCELLENT! Chatbot is working very well!")
    elif success_rate >= 75:
        print("\n👍 GOOD! Chatbot is working well with minor issues.")
    elif success_rate >= 60:
        print("\n⚠️  FAIR! Chatbot needs some improvements.")
    else:
        print("\n❌ NEEDS WORK! Chatbot requires significant fixes.")
    
    # Recommendations
    print("\n📋 RECOMMENDATIONS:")
    if test_results['failed'] > 0:
        print("- Review failed test cases above")
        print("- Check error messages for specific issues")
        print("- Verify database has test data")
        print("- Ensure all imports are correct")
    else:
        print("- All tests passed! System is ready for production")
        print("- Consider adding more test data for comprehensive testing")
        print("- Monitor performance in real-world usage")

if __name__ == "__main__":
    main()

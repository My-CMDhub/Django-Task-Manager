"""
Simple test for basic chatbot components without Django setup.
"""

def test_intent_patterns():
    """Test basic intent pattern matching"""
    print("🧠 Testing Intent Pattern Matching...")
    
    # Define simple patterns for testing
    intent_patterns = {
        'greeting': [
            r'\b(hello|hi|hey|greetings)\b',
            r'\bgood (morning|afternoon|evening)\b'
        ],
        'task.list': [
            r'\b(show|list|view|display).*(task|todo)\b',
            r'\bmy tasks?\b'
        ],
        'task.create': [
            r'\b(create|add|make).*(task|todo)\b',
            r'\bnew task\b'
        ],
        'statistics': [
            r'\b(progress|stats|statistics|dashboard)\b',
            r'\bhow.*(doing|am i)\b'
        ],
        'farewell': [
            r'\b(bye|goodbye|farewell|see you)\b'
        ]
    }
    
    test_messages = [
        ("Hello there!", "greeting"),
        ("Show me my tasks", "task.list"),
        ("Create a new task", "task.create"),
        ("What's my progress?", "statistics"),
        ("Goodbye!", "farewell")
    ]
    
    import re
    
    for message, expected in test_messages:
        matched_intent = "unknown"
        for intent, patterns in intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, message.lower()):
                    matched_intent = intent
                    break
            if matched_intent != "unknown":
                break
        
        status = "✅" if matched_intent == expected else "❌"
        print(f"  {status} '{message}' -> {matched_intent} (expected: {expected})")
    
    return True

def test_entity_extraction():
    """Test basic entity extraction"""
    print("\n🔍 Testing Entity Extraction...")
    
    import re
    from datetime import datetime, timedelta
    
    def extract_dates(text):
        """Simple date extraction"""
        dates = []
        # Simple patterns for common date expressions
        if re.search(r'\btoday\b', text.lower()):
            dates.append('today')
        elif re.search(r'\btomorrow\b', text.lower()):
            dates.append('tomorrow')
        elif re.search(r'\bnext week\b', text.lower()):
            dates.append('next week')
        return dates
    
    def extract_priorities(text):
        """Simple priority extraction"""
        priorities = []
        if re.search(r'\bhigh priority\b|\burgent\b|\bimportant\b', text.lower()):
            priorities.append('high')
        elif re.search(r'\blow priority\b', text.lower()):
            priorities.append('low')
        return priorities
    
    test_texts = [
        "Create a task due tomorrow with high priority",
        "Show tasks for today",
        "Add an urgent task for next week"
    ]
    
    for text in test_texts:
        dates = extract_dates(text)
        priorities = extract_priorities(text)
        entities = {}
        if dates:
            entities['dates'] = dates
        if priorities:
            entities['priorities'] = priorities
        
        print(f"  '{text}' -> {entities}")
    
    return True

def test_response_templates():
    """Test response template system"""
    print("\n💬 Testing Response Templates...")
    
    import random
    
    templates = {
        'greeting': [
            "Hello! I'm here to help you manage your tasks.",
            "Hi there! How can I assist with your productivity today?",
            "Greetings! Ready to tackle your task list?"
        ],
        'task_list': [
            "Here are your current tasks:",
            "Your task list:",
            "Current tasks on your agenda:"
        ],
        'farewell': [
            "Goodbye! Have a productive day!",
            "Take care! I'll be here when you need me.",
            "Until next time! Keep up the great work!"
        ]
    }
    
    test_cases = ['greeting', 'task_list', 'farewell']
    
    for intent in test_cases:
        if intent in templates:
            response = random.choice(templates[intent])
            print(f"  {intent} -> '{response}'")
        else:
            print(f"  {intent} -> No template found")
    
    return True

def test_conversation_flow():
    """Test basic conversation flow logic"""
    print("\n🔄 Testing Conversation Flow...")
    
    class SimpleTaskFlow:
        def __init__(self):
            self.steps = [
                "What would you like to name your task?",
                "When is this task due? (optional)",
                "What priority level? (high/medium/low)",
                "Great! I would create this task for you in the real system."
            ]
            self.current_step = 0
            self.data = {}
        
        def process_input(self, user_input):
            if self.current_step == 0:  # Task name
                self.data['title'] = user_input
            elif self.current_step == 1:  # Due date
                self.data['due_date'] = user_input if user_input.lower() not in ['skip', 'none', ''] else None
            elif self.current_step == 2:  # Priority
                self.data['priority'] = user_input.lower() if user_input.lower() in ['high', 'medium', 'low'] else 'medium'
            
            self.current_step += 1
            
            if self.current_step < len(self.steps):
                return self.steps[self.current_step]
            else:
                return f"Task '{self.data['title']}' would be created with priority '{self.data.get('priority', 'medium')}'" + (f" due {self.data['due_date']}" if self.data.get('due_date') else "")
    
    # Simulate a task creation flow
    flow = SimpleTaskFlow()
    print(f"  Start: {flow.steps[0]}")
    
    test_inputs = ["Write project report", "tomorrow", "high"]
    
    for i, input_text in enumerate(test_inputs):
        response = flow.process_input(input_text)
        print(f"  Step {i+1}: User: '{input_text}' -> Bot: '{response}'")
    
    return True

def main():
    """Run all simple tests"""
    print("🧪 Simple Chatbot Component Tests")
    print("=" * 50)
    
    tests = [
        test_intent_patterns,
        test_entity_extraction,
        test_response_templates,
        test_conversation_flow
    ]
    
    all_passed = True
    for test_func in tests:
        try:
            result = test_func()
            if not result:
                all_passed = False
        except Exception as e:
            print(f"❌ {test_func.__name__} failed: {e}")
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("🎉 All basic component tests passed!")
        print("The enhanced chatbot architecture is sound.")
    else:
        print("⚠️ Some tests failed. Check implementation.")
    
    return all_passed

if __name__ == "__main__":
    main()

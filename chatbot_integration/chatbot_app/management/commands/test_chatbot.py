from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from chatbot_integration.chatbot_app.processor import chatbot_processor
from chatbot_integration.chatbot_app.nlp.intents import intent_classifier
from chatbot_integration.chatbot_app.nlp.entities import entity_extractor
from chatbot_integration.chatbot_app.flows.base import flow_manager
from chatbot_integration.chatbot_app.flows.task_creation import TaskCreationFlow

class Command(BaseCommand):
    help = 'Test the enhanced chatbot system'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🧪 Testing Enhanced Chatbot System'))
        self.stdout.write('=' * 50)
        
        # Test 1: NLP Components
        self.stdout.write('\n🧠 Testing NLP Components...')
        try:
            # Test intent classification
            test_messages = [
                "Hello there!",
                "Show me my tasks", 
                "Create a new task",
                "What's my progress?",
                "Thank you",
                "Goodbye"
            ]
            
            for msg in test_messages:
                intent = intent_classifier.classify(msg)
                self.stdout.write(f"  '{msg}' -> {intent.primary}.{intent.secondary} ({intent.confidence:.2f})")
            
            # Test entity extraction
            entities = entity_extractor.extract_entities("Create a task due tomorrow with high priority")
            extracted = {k: [e.value for e in v] for k, v in entities.items() if v}
            self.stdout.write(f"  Entity extraction: {extracted}")
            
            self.stdout.write(self.style.SUCCESS('  ✅ NLP Components: PASS'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ❌ NLP Components: FAIL - {e}'))
        
        # Test 2: Flow System
        self.stdout.write('\n🔄 Testing Flow System...')
        try:
            # Register flow
            flow_manager.register_flow('task_creation', TaskCreationFlow)
            
            # Start a test flow
            result = flow_manager.start_flow('task_creation', 'user123', 'conv123')
            self.stdout.write(f"  Flow start: {result.message[:50]}...")
            
            # Clean up
            flow_manager.end_flow('conv123')
            
            self.stdout.write(self.style.SUCCESS('  ✅ Flow System: PASS'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ❌ Flow System: FAIL - {e}'))
        
        # Test 3: Main Processor
        self.stdout.write('\n🎯 Testing Main Processor...')
        try:
            # Get or create test user
            user, created = User.objects.get_or_create(username='testuser')
            
            test_messages = [
                "Hello!",
                "Show me my tasks",
                "What's my progress?"
            ]
            
            for msg in test_messages:
                result = chatbot_processor.process_message(
                    user_message=msg,
                    user=user
                )
                
                if result['success']:
                    self.stdout.write(f"  '{msg}' -> Success: {result['response'][:50]}...")
                else:
                    self.stdout.write(f"  '{msg}' -> Error: {result.get('error', 'Unknown')}")
            
            self.stdout.write(self.style.SUCCESS('  ✅ Main Processor: PASS'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  ❌ Main Processor: FAIL - {e}'))
        
        self.stdout.write('\n' + '=' * 50)
        self.stdout.write(self.style.SUCCESS('🎉 Chatbot system test complete!'))

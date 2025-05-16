import os
import json
import re
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone

from llama_index import StorageContext, load_index_from_storage
from dotenv import load_dotenv
import time

from .models import ChatbotConversation, ChatMessage, TaskCreationRequest
from .utils import extract_task_info, create_task, get_user_tasks, format_task_list

# Load environment variables
load_dotenv()

# Set OpenAI API key
os.environ["OPENAI_API_KEY"] = os.getenv('OPENAI_API_KEY')

# Load the index from disk
def load_index_from_disk():
    try:
        storage_context = StorageContext.from_defaults(persist_dir="PKL_file")
        new_index = load_index_from_storage(storage_context)
        return new_index
    except Exception as e:
        print(f"Error loading index: {str(e)}")
        return None

# Initialize loaded_index
try:
    loaded_index = load_index_from_disk()
    if loaded_index:
        query_engine = loaded_index.as_query_engine()
    else:
        query_engine = None
except Exception as e:
    print(f"Error initializing query engine: {str(e)}")
    loaded_index = None
    query_engine = None

# Custom responses
custom_responses = {
    # Greetings
    "greeting": "Hi there! How may I assist you with your tasks today?",
    "greeting_time": {
        "morning": "Good morning! Need help organizing your day?",
        "afternoon": "Good afternoon! How can I help with your tasks?",
        "evening": "Good evening! Let's review your tasks for today.",
        "night": "Working late? Let me help you organize your tasks."
    },
    
    # Farewells
    "farewell": "Goodbye! Have a productive day!",
    "farewell_alt": "Take care! Your tasks will be waiting for you when you return.",
    
    # Identity/Introduction
    "chatbot-name": "I'm your Task Assistant, ready to help you manage your tasks efficiently.",
    "purpose": "I'm here to help you manage your tasks, set reminders, and stay organized!",
    
    # Tasks related
    "task_created": "I've created that task for you. Anything else you need help with?",
    "task_updated": "Task updated successfully!",
    "task_deleted": "Task has been deleted.",
    "task_not_found": "I couldn't find that task. Could you provide more details?",
    
    # Error Handling
    "error": "I apologize, but I'm having trouble processing your request right now. Please try again.",
    "api_error": "I'm currently experiencing some technical difficulties. Please try again in a moment.",
    "invalid_input": "I couldn't understand that input. Could you please rephrase it?",
    "empty_input": "Please type a message before sending.",
}

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chatbot_message(request):
    try:
        data = request.data
        user_input = data.get('message', '')
        
        # Input validation
        if not user_input:
            return Response({"error": custom_responses["empty_input"]}, status=status.HTTP_400_BAD_REQUEST)
        if len(user_input) > 500:
            return Response({"error": "Your message is too long. Please try a shorter message."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Get or create conversation for the user
        conversation, created = ChatbotConversation.objects.get_or_create(
            user=request.user,
            defaults={'last_interaction': timezone.now()}
        )
        
        # Create user message
        user_message = ChatMessage.objects.create(
            conversation=conversation,
            content=user_input,
            sender='user'
        )
        
        # Process message and get response
        response_text = process_user_input(user_input, request.user)
        
        # Create bot message
        bot_message = ChatMessage.objects.create(
            conversation=conversation,
            content=response_text,
            sender='bot'
        )
        
        # Check if this is a task creation request
        task_info = extract_task_info(user_input)
        if task_info:
            # Create task request
            task_request = TaskCreationRequest.objects.create(
                message=user_message,
                title=task_info.get('title', ''),
                description=task_info.get('description', ''),
                due_date=task_info.get('due_date'),
                status='pending'
            )
            
            # Attempt to create the task
            try:
                task_id = create_task(request.user, task_info)
                task_request.created_task_id = task_id
                task_request.status = 'completed'
                task_request.save()
            except Exception as e:
                task_request.status = 'failed'
                task_request.error_message = str(e)
                task_request.save()
        
        # Update conversation last interaction time
        conversation.last_interaction = timezone.now()
        conversation.save()
        
        return Response({
            "message": response_text,
            "message_id": bot_message.id
        })
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return Response({"error": custom_responses["error"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_conversation_history(request):
    try:
        conversation, created = ChatbotConversation.objects.get_or_create(
            user=request.user
        )
        
        messages = conversation.messages.order_by('timestamp')
        message_list = [
            {
                "id": msg.id,
                "content": msg.content,
                "sender": msg.sender,
                "timestamp": msg.timestamp.isoformat()
            }
            for msg in messages
        ]
        
        return Response({"messages": message_list})
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return Response({"error": "Failed to retrieve conversation history"}, 
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def process_user_input(user_input, user=None):
    input_lower = user_input.lower()
    
    # Task list queries
    if any(phrase in input_lower for phrase in [
            'show my tasks', 'list my tasks', 'what are my tasks', 
            'tasks due today', 'what do i need to do'
        ]):
        
        if 'today' in input_lower:
            today = timezone.now().date()
            from tasks.models import Task
            today_tasks = Task.objects.filter(
                assignees=user, 
                due_date__date=today,
                is_archived=False
            ).exclude(status='completed')
            
            if today_tasks.exists():
                return f"Here are your tasks due today:\n\n{format_task_list(today_tasks)}"
            else:
                return "You don't have any tasks due today! Would you like to create one?"
        
        # Default to showing all incomplete tasks
        from tasks.models import Task
        tasks = Task.objects.filter(
            assignees=user,
            is_archived=False
        ).exclude(status='completed')[:5]
        
        if tasks.exists():
            return f"Here are your current tasks:\n\n{format_task_list(tasks)}"
        else:
            return "You don't have any active tasks. Would you like to create one?"
    
    # Task creation intent
    task_patterns = [
        r'add task[s]?\s*:?\s*(.+)',
        r'create task[s]?\s*:?\s*(.+)',
        r'new task[s]?\s*:?\s*(.+)',
        r'remind me to\s*(.+)',
    ]
    
    for pattern in task_patterns:
        match = re.search(pattern, input_lower)
        if match:
            task_info = extract_task_info(user_input)
            if task_info:
                try:
                    task_id = create_task(user, task_info)
                    due_date_str = ""
                    if task_info.get('due_date'):
                        due_date_str = f" due on {task_info['due_date'].strftime('%B %d, %Y')}"
                    
                    return f"I've created your task: \"{task_info['title']}\"{due_date_str}. Is there anything else you'd like to do?"
                except Exception as e:
                    return f"I couldn't create that task. Error: {str(e)}"
            return custom_responses["task_created"]
    
    # Overdue tasks query
    if any(phrase in input_lower for phrase in [
            'overdue tasks', 'late tasks', 'missed deadlines', 
            'what is overdue', 'what am i late on'
        ]):
        today = timezone.now()
        from tasks.models import Task
        overdue_tasks = Task.objects.filter(
            assignees=user,
            due_date__lt=today,
            is_archived=False
        ).exclude(status='completed')
        
        if overdue_tasks.exists():
            return f"You have {overdue_tasks.count()} overdue tasks:\n\n{format_task_list(overdue_tasks)}"
        else:
            return "Great news! You don't have any overdue tasks."
    
    # Task completion queries
    completion_patterns = [
        r'mark\s+task\s+(.+?)\s+as\s+(?:complete|completed|done)',
        r'complete\s+task\s+(.+)',
        r'finish\s+task\s+(.+)',
        r'i\s+(?:finished|completed)\s+(.+)',
    ]
    
    for pattern in completion_patterns:
        match = re.search(pattern, input_lower)
        if match:
            task_name = match.group(1).strip()
            from tasks.models import Task
            
            # Try to find the task by title (partial match)
            tasks = Task.objects.filter(
                assignees=user,
                title__icontains=task_name,
                is_archived=False
            ).exclude(status='completed')
            
            if tasks.count() == 0:
                return f"I couldn't find a task with the name '{task_name}'. Please try again with a different task name."
            elif tasks.count() == 1:
                task = tasks.first()
                task.status = 'completed'
                task.completed_at = timezone.now()
                task.save()
                
                # Log the activity
                from tasks.models import TaskActivity
                TaskActivity.objects.create(
                    task=task,
                    activity_type='status_change',
                    user=user,
                    description=f"Task marked as completed via chatbot"
                )
                
                return f"Great job! I've marked '{task.title}' as completed."
            else:
                # Multiple matching tasks
                return f"I found multiple tasks matching '{task_name}'. Please be more specific or use the task ID."
    
    # Regular intent processing
    # Greetings
    if re.search(r'\b(hello|hi|hey|howdy|hola)\b', input_lower):
        return custom_responses["greeting"]
    elif re.search(r'\b(good morning)\b', input_lower):
        return custom_responses["greeting_time"]["morning"]
    elif re.search(r'\b(good afternoon)\b', input_lower):
        return custom_responses["greeting_time"]["afternoon"]
    elif re.search(r'\b(good evening)\b', input_lower):
        return custom_responses["greeting_time"]["evening"]
    elif re.search(r'\b(good night)\b', input_lower):
        return custom_responses["greeting_time"]["night"]
    
    # Farewells
    elif any(keyword in input_lower for keyword in ['bye', 'goodbye', 'see you', 'cya', 'farewell']):
        return custom_responses["farewell"]
    
    # Identity Questions
    elif any(keyword in input_lower for keyword in ['your name', 'who are you', 'who you are', 'what are you']):
        return custom_responses["chatbot-name"]
    
    # Help request
    elif any(keyword in input_lower for keyword in ['help', 'how do you work', 'what can you do']):
        return """
I can help you manage your tasks in the following ways:

1. Create tasks: "Add task: Complete project report by Friday"
2. List tasks: "Show my tasks" or "What's due today?"
3. Mark tasks as complete: "Mark task Budget Analysis as completed"
4. Find overdue tasks: "Show my overdue tasks"

Is there something specific you'd like help with?
"""
    
    # Try using RAG for knowledge-based responses if query_engine is available
    if query_engine:
        try:
            response = query_engine.query(user_input)
            if response:
                return str(response)
        except Exception as e:
            print(f"Error querying index: {str(e)}")
    
    # Default fallback response
    return "I understand you want to discuss your tasks. Could you be more specific about what you need help with?" 
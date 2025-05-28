import os
import json
import re
import uuid
import datetime
import random
import httpx
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.conf import settings
from django.db import models

from llama_index import StorageContext, load_index_from_storage
from dotenv import load_dotenv
import time

# Import Task and Project models
from tasks.models import Task, Project

from .models import ChatbotConversation, ChatMessage, TaskCreationRequest
from .utils import (
    extract_task_info, 
    create_task, 
    get_user_tasks, 
    format_task_list, 
    analyze_conversation_context,
    custom_responses,
)

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
    "greeting": "Hi there! I'm TaskBuddy, your personal task assistant. How can I help you today? (Try asking \"What can you do?\" to see all my capabilities)",
    "greeting_time": {
        "morning": "Good morning! I'm TaskBuddy, ready to help you organize your day. What would you like to tackle first? (Type \"What can you do?\" to explore all my features)",
        "afternoon": "Good afternoon! TaskBuddy here. Need help prioritizing your tasks for the rest of the day? (Ask \"What can you do?\" to see everything I can help with)",
        "evening": "Good evening! TaskBuddy at your service. Let's review what you've accomplished today and plan for tomorrow. (Use \"What can you do?\" to see all my capabilities)",
        "night": "Working late? TaskBuddy is here to help you wrap up for the day or prepare for tomorrow. (Try \"What can you do?\" to explore all my features)"
    },
    
    # Farewells
    "farewell": "Goodbye! TaskBuddy will be here when you need me. Have a productive day!",
    "farewell_alt": "Take care! I'll keep an eye on your tasks until you return. TaskBuddy signing off!",
    
    # Identity/Introduction
    "chatbot-name": "I'm TaskBuddy, your personal task assistant! I'm here to help you stay organized, manage your workload, and never miss a deadline.",
    "purpose": "As your TaskBuddy, I'm here to help you manage tasks, set reminders, track your productivity, and keep you organized!",
    
    # Tasks related
   
    "task_updated": "Task updated successfully! Would you like me to remind you about this task later?",
    "task_deleted": "I've removed that task from your list. Your workload just got a bit lighter!",
    "task_not_found": "Hmm, I couldn't find that specific task. Could you provide more details or try a different task name?",
    
    # Productivity insights
    "productivity_insight": "Based on your completed tasks, you're most productive in the {time_of_day}. Would you like me to prioritize important tasks during this time?",
    "overdue_reminder": "Just a friendly reminder: You have {count} overdue tasks. Would you like me to help you reschedule them?",
    "accomplishment": "Great job! You've completed {count} tasks this week. That's {comparison} compared to last week!",
    
    # Suggestions
    "break_suggestion": "You've been working hard! Consider taking a short break before starting your next task.",
    "priority_suggestion": "I notice you have several high-priority tasks due soon. Would you like me to help you create a plan to complete them?",
    "recurring_task_suggestion": "You seem to create this type of task regularly. Would you like me to set it up as a recurring task?",
    
    # Error Handling
    "error": "I apologize, but I'm having trouble with that request right now. Please try again, or let me know if I can help another way.",
    "api_error": "I'm experiencing some technical difficulties at the moment. Let's try that again in a bit.",
    "invalid_input": "I didn't quite catch that. Could you rephrase your request so I can better assist you?",
    "empty_input": "Please type a message so I can help you with your tasks.",
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
        
        # Update the last interaction time
        conversation.last_interaction = timezone.now()
        conversation.save()
        
        # Get the last few messages for context (short-term memory)
        recent_messages = list(conversation.messages.order_by('-timestamp')[:5])
        recent_messages.reverse()  # Order from oldest to newest
        
        # Prepare conversation context with role and content
        conversation_context = [
            {"role": msg.sender, "content": msg.content} 
            for msg in recent_messages
        ]
        
        # Find the last bot message if there is one
        last_bot_message = None
        if recent_messages:
            for msg in reversed(recent_messages):
                if msg.sender == 'bot':
                    last_bot_message = msg.content
                    break
        
        # Debug logging
        logger = logging.getLogger(__name__)
        logger.debug(f"Last bot message: {last_bot_message}")
        logger.debug(f"User input: {user_input}")
        
        # Special handling for simple acknowledgements (thanks, thank you, etc.)
        user_input_lower = user_input.lower().strip()
        is_simple_thanks = (
            user_input_lower in ['thanks', 'thank you', 'thanks a lot', 'thank you so much', 'thx', 'ty']
            or 'thank' in user_input_lower
            or 'thanks' in user_input_lower
            or user_input_lower.startswith('thx')
            or user_input_lower.startswith('ty')
            or 'appreciate' in user_input_lower
        )
        
        # Handle simple yes/no responses directly before deeper processing
        if last_bot_message and len(user_input.split()) <= 4:
            # Handle yes/affirmative responses
            if re.search(r'\b(yes|yeah|yep|sure|ok|okay|of course|definitely|please)\b', user_input.lower()):
                logger.debug(f"Matched affirmative response pattern")
                
                # Direct match for the specific case in the logs
                if "Would you like me to show you your current tasks instead?" in last_bot_message:
                    logger.debug(f"Matched exact show tasks pattern")
                    
                    # Create user message
                    user_message = ChatMessage.objects.create(
                        conversation=conversation,
                        content=user_input,
                        sender='user'
                    )
                    
                    # Get tasks and format response
                    from tasks.models import Task
                    tasks = Task.objects.filter(
                        assignees=request.user,
                        is_archived=False
                    ).exclude(status='completed')[:5]
                    
                    # Create response
                    if tasks.exists():
                        response_text = f"Here are your current tasks:\n\n{format_task_list(tasks)}"
                    else:
                        response_text = "You don't have any active tasks. Would you like to create one?"
                    
                    # Create bot message
                    bot_message = ChatMessage.objects.create(
                        conversation=conversation,
                        content=response_text,
                        sender='bot'
                    )
                    
                    # Return response
                    return Response({
                        "message": response_text,
                        "message_id": bot_message.id
                    })
        
        # Create user message in the database
        user_message = ChatMessage.objects.create(
            conversation=conversation,
            content=user_input,
            sender='user'
        )
        
        # Add current message to context
        conversation_context.append({"role": "user", "content": user_input})
        
        # Process message with conversation context
        response_text = ""
        if is_simple_thanks:
            # Use a friendly response for simple thanks
            friendly_responses = [
                "You're welcome! Is there anything else I can help you with?",
                "Glad I could help! Feel free to ask if you need anything else.",
                "Happy to assist! Let me know if you need help with any other tasks.",
                "No problem at all! Would you like me to show you your current tasks?",
                "Anytime! I'm here to help with your tasks and projects."
            ]
            response_text = random.choice(friendly_responses)
        else:
            # Use standard pattern-based processing for other queries
        response_text = process_user_input(user_input, request.user, conversation_context)
        
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
                
                # Check if this is a high priority task or due soon to add proactive reminders
                if task_info.get('priority') == 'high' or (
                    task_info.get('due_date') and 
                    (task_info.get('due_date') - timezone.now()).total_seconds() < 86400 * 3  # 3 days
                ):
                    # Add a scheduled reminder for this task
                    from tasks.models import TaskReminder, Task
                    task = Task.objects.get(id=task_id)
                    
                    # Choose reminder time based on due date
                    if task_info.get('due_date'):
                        # Remind 24 hours before due date, or now if due date is less than 24 hours away
                        time_before_due = (task_info.get('due_date') - timezone.now()).total_seconds()
                        if time_before_due > 86400:  # More than 24 hours
                            reminder_time = task_info.get('due_date') - datetime.timedelta(days=1)
                        else:
                            # Remind in 4 hours if due date is very soon
                            reminder_time = timezone.now() + datetime.timedelta(hours=4)
                    else:
                        # No due date, remind in 24 hours
                        reminder_time = timezone.now() + datetime.timedelta(days=1)
                    
                    # Create the reminder
                    TaskReminder.objects.create(
                        task=task,
                        user=request.user,
                        reminder_time=reminder_time,
                        message=f"Don't forget about your task: {task.title}",
                        status='pending'
                    )
            except Exception as e:
                task_request.status = 'failed'
                task_request.error_message = str(e)
                task_request.save()
        
        # Check for any reminders we should send proactively
        # Only do this occasionally (based on the 10th message) to avoid being annoying
        message_count = conversation.messages.count()
        if message_count % 10 == 0:
            # Import reminder model
            from tasks.models import TaskReminder
            
            # Get pending reminders
            pending_reminders = TaskReminder.objects.filter(
                user=request.user,
                reminder_time__lte=timezone.now(),
                status='pending'
            )
            
            if pending_reminders.exists():
                reminder = pending_reminders.first()
                reminder.status = 'sent'
                reminder.save()
                
                # Create a proactive reminder message
                proactive_msg = f"By the way, I wanted to remind you: {reminder.message}"
                
                # Add the reminder to the response
                ChatMessage.objects.create(
                    conversation=conversation,
                    content=proactive_msg,
                    sender='bot'
                )
                
                # Add to response array
                response_text = [response_text, proactive_msg]
        
        # Check if we should offer a proactive suggestion
        # Do this occasionally (every 5th message) if we don't have a reminder
        elif message_count % 5 == 0 and 'remind' not in user_input.lower():
            from .utils import generate_task_suggestions
            suggestions = generate_task_suggestions(request.user)
            
            if suggestions and len(suggestions) > 0:
                suggestion = random.choice(suggestions)
                
                # Only send proactive suggestions for specific types to avoid being annoying
                proactive_types = ['overdue_reminder', 'priority_suggestion']
                if suggestion['type'] in proactive_types:
                    # Create a proactive suggestion message
                    proactive_msg = f"By the way, {suggestion['message']}"
                    
                    # Add the suggestion to the response
                    ChatMessage.objects.create(
                        conversation=conversation,
                        content=proactive_msg,
                        sender='bot'
                    )
                    
                    # Add to response array
                    response_text = [response_text, proactive_msg]
        
        # Priority-based queries (always use the priority field, not text search)
        priority_map = {
            'high priority': 'high',
            'medium priority': 'medium',
            'low priority': 'low',
        }
        for phrase, priority_value in priority_map.items():
            if phrase in user_input.lower() or (
                re.search(rf'find (tasks|task) with {phrase}', user_input.lower()) or
                re.search(rf'show (my )?{phrase} (tasks|task)', user_input.lower()) or
                re.search(rf'list (my )?{phrase} (tasks|task)', user_input.lower())
            ):
                from tasks.models import Task
                tasks = Task.objects.filter(
                    assignees=request.user,
                    priority=priority_value,
                    is_archived=False
                ).exclude(status='completed')
                if tasks.exists():
                    response = f"Here are your {phrase} tasks:\n\n{format_task_list(tasks)}"
                    # Optionally, add stats
                    total_tasks = Task.objects.filter(assignees=request.user, is_archived=False).exclude(status='completed').count()
                    response += f"\n\nYou have {tasks.count()} {phrase} tasks out of {total_tasks} total tasks ({(tasks.count()/total_tasks*100) if total_tasks else 0:.1f}%)."
                    return response
                else:
                    return f"You don't have any {phrase} tasks right now."
        
        # Handle response as single message or array of messages
        if isinstance(response_text, list):
            return Response({
                "messages": [
                    {"message": msg, "message_id": bot_message.id if i == 0 else None}
                    for i, msg in enumerate(response_text)
                ]
            })
        else:
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

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def clear_history(request):
    try:
        # Get user's conversation
        conversation = ChatbotConversation.objects.filter(user=request.user).first()
        
        if conversation:
            # Delete all messages in the conversation
            ChatMessage.objects.filter(conversation=conversation).delete()
            
            # Update last interaction time
            conversation.last_interaction = timezone.now()
            conversation.save()
        
        return Response({"success": True})
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return Response({"error": "Failed to clear conversation history"}, 
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR)

def process_user_input(user_input, user=None, conversation_context=None):
    input_lower = user_input.lower()
    
    # Get query context
    context_analysis = {}
    if conversation_context and len(conversation_context) >= 3:  # Need at least user, bot, user
        context_analysis = analyze_conversation_context(conversation_context)
    
    # Define patterns that should be handled directly without Mistral
    direct_patterns = {
        # Greetings
        r'\b(hello|hi|hey|howdy|hola)\b': custom_responses["greeting"],
        r'\b(good morning)\b': custom_responses["greeting_time"]["morning"],
        r'\b(good afternoon)\b': custom_responses["greeting_time"]["afternoon"],
        r'\b(good evening)\b': custom_responses["greeting_time"]["evening"],
        
        # Farewell patterns
        r'\b(goodbye|bye|see you|farewell)\b': custom_responses["farewell"],
        
        # Identity/Introduction patterns
        r'\b(who are you|what are you|what is your name|who am i talking to)\b': custom_responses["chatbot-name"],
        r'\b(what can you do|what do you do|help me|how can you help me)\b': custom_responses["purpose"],
    }
    
    # Check each pattern for a direct match first
    for pattern, response in direct_patterns.items():
        if re.search(pattern, input_lower):
            return response
    
    # Import Task and Project models early to ensure they're available for all patterns
    from tasks.models import Task, Project
    
    # Task list patterns with detailed response
    task_list_patterns = [
        r"(?:show|list|view|get|display|what are).*(?:my )?tasks?",
        r"(?:what|which) tasks? (?:do|have|did) I",
        r"tell me about my tasks?",
        r"tasks? information",
        r"information about (?:my )?tasks?",
        r"(?:any|all) (?:tasks?|todo|to do)",
        r"do i have (?:any )?tasks?",
        r"my tasks?",
        r"tasks? (?:list|overview)",
        r"check (?:my )?tasks?"
    ]
    
    is_task_list_request = any(re.search(pattern, input_lower) for pattern in task_list_patterns)
    
    if is_task_list_request:
        try:
            # Start with all user's tasks
            tasks = Task.objects.filter(assignees=user) | Task.objects.filter(owner=user)
            tasks = tasks.distinct()  # Remove duplicates
            total_count = tasks.count()
            filter_description = "all"
            
            # Check for filters with expanded patterns
            if re.search(r"pending|incomplete|ongoing|open|in progress|not done|to do|active|current|todo|unfinished|not complete", input_lower):
                tasks = tasks.filter(status__in=['new', 'in_progress'])
                filter_description = "pending"
            elif re.search(r"complete|finished|done|did|completed|closed|resolved", input_lower):
                tasks = tasks.filter(status='completed')
                filter_description = "completed"
            elif re.search(r"overdue|late|missed|past due|delayed|expired", input_lower):
                tasks = tasks.filter(due_date__lt=timezone.now()).exclude(status='completed')
                filter_description = "overdue"
            elif re.search(r"upcoming|future|scheduled|next|this week|tomorrow|soon|coming|advance|planned", input_lower):
                today = timezone.now()
                next_week = today + datetime.timedelta(days=7)
                tasks = tasks.filter(due_date__gte=today, due_date__lte=next_week).exclude(status='completed')
                filter_description = "upcoming (next 7 days)"
            elif re.search(r"today|due today|for today", input_lower):
            today = timezone.now().date()
                tasks = tasks.filter(due_date__date=today).exclude(status='completed')
                filter_description = "due today"
            elif re.search(r"high priority|important|urgent|critical|highest|top priority", input_lower):
                tasks = tasks.filter(priority__in=['high', 'urgent', 'critical'])
                filter_description = "high priority"
        
        if tasks.exists():
                # Format the response based on how many tasks there are
                response = f"Here are your {filter_description} tasks:\n\n"
                
                # Show 10 tasks max
                display_tasks = tasks[:10]
                for task in display_tasks:
                    due_date_str = f" (Due: {task.due_date.strftime('%Y-%m-%d')})" if task.due_date else ""
                    priority_str = f" [Priority: {task.priority.capitalize()}]" if hasattr(task, 'priority') and task.priority else ""
                    status_display = task.get_status_display() if hasattr(task, 'get_status_display') else task.status
                    response += f"• {task.title}{due_date_str}{priority_str} - Status: {status_display}\n"
                
                # Add information about how many shown vs. total
                if tasks.count() > 10:
                    response += f"\n(Showing 10 of {tasks.count()} {filter_description} tasks)"
                
                # Add overall statistics if relevant
                if filter_description != "all" and total_count > 0:
                    percentage = (tasks.count() / total_count) * 100
                    response += f"\n\nYou have {tasks.count()} {filter_description} tasks out of {total_count} total tasks ({percentage:.1f}%)."
                
                return response
                else:
                days_ago = Task.objects.filter(owner=user).count() + Task.objects.filter(assignees=user).count()
                if days_ago > 0:
                    return f"You don't have any {filter_description} tasks at the moment. You have {days_ago} tasks in total."
            else:
                    return f"You don't have any {filter_description} tasks. Would you like to create a task using the main application interface?"
        except Exception as e:
            import logging
            logging.error(f"Error in task listing: {str(e)}")
            return f"I encountered an issue retrieving your tasks. Please try another type of query or contact support if this persists."
    
    # If we reach here and haven't matched any patterns, use the Mistral AI fallback
    try:
        # Use On-Demand Data Injection with Mistral AI
        from chatbot_integration.chatbot_app.views import generate_bot_response
        
        # Import Task model early to avoid scope issues
        from tasks.models import Task, Project
        
        try:
            # Create a mock conversation object if needed
            class MockConversation:
                def __init__(self, id=None):
                    self.id = id or uuid.uuid4()
                
                def get_recent_messages(self, count=5):
                    return conversation_context[-count:] if conversation_context else []
            
            mock_conversation = MockConversation()
            
            # Use the integration's response generator
            fallback_response = generate_bot_response(user, mock_conversation, user_input)
            return fallback_response
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error using Mistral integration for fallback: {str(e)}")
            return "I'm having trouble understanding that. Could you rephrase your question about your tasks or projects?"
    except Exception as e:
        logging.error(f"Error using fallback: {str(e)}")
        return "I couldn't understand your request. Please try asking in a different way or use the application interface directly." 
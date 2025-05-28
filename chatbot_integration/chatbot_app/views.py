import os
import json
import re
import httpx
from .utils import get_user_tasks, format_task_list, process_context_with_query, get_user_context_data
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.utils import timezone
from django.db import models
import datetime
from django.conf import settings
from django.shortcuts import render
from .models import ChatbotConversation, ChatMessage, Conversation, Message
from tasks.models import Task, Project
import logging
from .task_automation import (
    check_task_statistics_request,
    check_project_statistics_request,
    check_general_statistics_request,
    get_user_statistics,
)
from dotenv import load_dotenv
import time
import random
import pytz

logger = logging.getLogger(__name__)

# Replace the problematic llama_index imports with conditional imports
try:
    # Try newer version import
    from llama_index import StorageContext, load_index_from_storage
except ImportError:
    try:
        # Try older version import
        from llama_index.core import ServiceContext, load_index_from_storage
        StorageContext = ServiceContext  # Compatibility alias
    except ImportError:
        # Fallback to avoid breaking the application
        print("Warning: llama_index library not properly installed. AI features will be limited.")
        StorageContext = None
        load_index_from_storage = None

# Load environment variables
load_dotenv()

# Add Melbourne timezone support
melbourne_timezone = pytz.timezone('Australia/Melbourne')

# Modified function to safely load the index
def load_index_from_disk():
    try:
        if StorageContext and load_index_from_storage:
            if os.path.exists("PKL_file"):
                try:
                    storage_context = StorageContext.from_defaults(persist_dir="PKL_file")
                    new_index = load_index_from_storage(storage_context)
                    return new_index
                except Exception as e:
                    print(f"Error loading index: {str(e)}")
    except Exception as e:
        print(f"Error loading index: {str(e)}")
    return None

# Initialize loaded_index safely
try:
    loaded_index = load_index_from_disk()
    query_engine = loaded_index.as_query_engine() if loaded_index else None
except Exception as e:
    print(f"Error initializing query engine: {str(e)}")
    loaded_index = None
    query_engine = None

# Custom responses
custom_responses = {
    # Greetings
    "greeting": "Hi there! How may I assist you with your tasks today?",
    "greeting_time": {
        "morning": "Good morning! ☀️ Ready to plan your day? I'm here to help you stay on top of your tasks.",
        "afternoon": "Good afternoon! 🌤️ How's your day going? I'm here to help you manage your tasks and projects.",
        "evening": "Good evening! 🌙 Let's review what you've accomplished today and plan for tomorrow.",
        "night": "Still working? 🌠 I'm here to help you wrap up for the day or plan for tomorrow."
    },
    
    # Farewells
    "farewell": "Goodbye! Have a productive day!",
    "farewell_alt": "Take care! Your tasks will be waiting for you when you return.",
    
    # Identity/Introduction
    "chatbot-name": "I'm your Task Assistant, ready to help you manage your tasks efficiently.",
    "purpose": "I'm here to help you track your tasks, manage projects, and stay organized!",
    
    # Tasks related
    "task_info": "Here's the information about your tasks that you requested.",
    "task_not_found": "I couldn't find that task. Could you provide more details or check the task name?",
    
    # Error Handling
    "error": "I apologize, but I'm having trouble processing your request right now. Please try again in a moment.",
    "api_error": "I'm currently experiencing some technical difficulties. Please try again shortly.",
    "invalid_input": "I'm not quite sure what you're asking. Could you please rephrase that?",
    "empty_input": "Please type a message before sending.",
    
    # Automation rejection responses
    "creation_not_supported": "I'd love to help you create a new task or project! However, for the best experience with all available options, please use the 'Create' button in the main interface. Is there anything else I can assist you with?",
    "update_not_supported": "I'd be happy to help you update that! For the full range of editing options, please use the edit function in the main interface. Would you like me to show you your current tasks instead?",
    "delete_not_supported": "For security reasons, deletion needs to be done through the main interface. Would you like me to help you find the item you're looking to remove instead?",
}

@login_required
def chatbot_interface(request):
    """Render the chatbot interface."""
    return render(request, 'chatbot_app/chatbot_interface.html')

@csrf_exempt
@login_required
def chatbot_message(request):
    """Process user messages and generate bot responses."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '').strip()
            if not user_message:
                return JsonResponse({'error': 'Empty message'}, status=400)
            conversation, created = Conversation.objects.get_or_create(
                user=request.user,
                defaults={'last_updated': timezone.now()}
            )
            if not created:
                conversation.last_updated = timezone.now()
                conversation.save()
            Message.objects.create(
                conversation=conversation,
                content=user_message,
                is_user=True
            )
            bot_response = generate_bot_response(request.user, conversation, user_message)
            Message.objects.create(
                conversation=conversation,
                content=bot_response if isinstance(bot_response, str) else str(bot_response),
                is_user=False
            )
            if isinstance(bot_response, dict):
                print("DEBUG: Returning JSON response:", bot_response)
                return JsonResponse(bot_response)
            else:
                print("DEBUG: Returning string response:", bot_response)
                return JsonResponse({'response': bot_response})
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return JsonResponse({'error': 'An error occurred while processing your message'}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@csrf_exempt
@login_required
def process_message(request):
    """Process a user message and return a bot response."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '').strip()
            if not user_message:
                return JsonResponse({'error': 'Message is required'}, status=400)
            logger.info(f"Processing message from user {request.user.id}: '{user_message}'")
            conversation, created = Conversation.objects.get_or_create(
                user=request.user,
                defaults={'last_updated': timezone.now()}
            )
            if created:
                logger.info(f"Created new conversation {conversation.id} for user {request.user.id}")
            else:
                logger.info(f"Using existing conversation {conversation.id} for user {request.user.id}")
                conversation.last_updated = timezone.now()
                conversation.save()
            Message.objects.create(
                conversation=conversation,
                content=user_message,
                is_user=True
            )
            bot_response = generate_bot_response(request.user, conversation, user_message)
            logger.info(f"Generated response: '{bot_response}'")
            Message.objects.create(
                conversation=conversation,
                content=bot_response if isinstance(bot_response, str) else str(bot_response),
                is_user=False
            )
            if isinstance(bot_response, dict):
                print("DEBUG: Returning JSON response:", bot_response)
                return JsonResponse(bot_response)
            else:
                print("DEBUG: Returning string response:", bot_response)
                return JsonResponse({'response': bot_response})
        except json.JSONDecodeError:
            logger.error("Invalid JSON in request body")
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
        except Exception as e:
            logger.error(f"Error in process_message: {str(e)}")
            return JsonResponse({'error': f'An error occurred: {str(e)}'}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

@login_required
def get_conversation_history(request):
    """Get the conversation history for the current user."""
    try:
        # Get the most recent conversation
        conversation = Conversation.objects.filter(user=request.user).order_by('-last_updated').first()
        
        if not conversation:
            return JsonResponse({'messages': []})
        
        # Get all messages in this conversation
        messages = Message.objects.filter(conversation=conversation).order_by('timestamp')
        
        message_list = [
            {
                'content': msg.content,
                'is_user': msg.is_user,
                'timestamp': msg.timestamp.isoformat()
            }
            for msg in messages
        ]
        
        return JsonResponse({'messages': message_list})
    
    except Exception as e:
        logger.error(f"Error getting conversation history: {str(e)}")
        return JsonResponse({'error': 'Failed to retrieve conversation history'}, status=500)

@login_required
def chat_view(request):
    """View for the chat interface"""
    return render(request, 'chatbot_app/chat.html')

def generate_bot_response(user, conversation, user_message):
    """Generate a response from the chatbot based on user input."""
    logger.info(f"Received message from user {user.id} in conversation {conversation.id}: '{user_message}'")
    try:
        # Check for simple thanks messages first
        user_message_lower = user_message.lower().strip()
        if (user_message_lower.startswith('thank') or 
            user_message_lower.startswith('thanks') or 
            user_message_lower == 'ty' or 
            user_message_lower == 'thx' or 
            'appreciate' in user_message_lower or
            user_message_lower in ['thanks', 'thank you', 'thanks a lot', 'thanks buddy', 'thank you so much']):
            
            # Return a friendly thank you response
            thanks_responses = [
                "You're welcome! Is there anything else I can help you with?",
                "Glad I could help! Feel free to ask if you need anything else.",
                "Happy to assist! Let me know if you need help with any other tasks.",
                "No problem at all! Would you like me to show you your current tasks?",
                "Anytime! I'm here to help with your tasks and projects."
            ]
            return random.choice(thanks_responses)
            
        # Get recent conversation history (last 5 exchanges) for context
        conversation_context = conversation.get_recent_messages(count=5)
        
        # Process the message with context to handle references (like "this task")
        processed_message, context_info = process_context_with_query(conversation_context, user_message)
        
        # Log if the user's message was referring to previous context
        if context_info['referencing_previous']:
            logger.info(f"User is referencing previous context. Message processed from '{user_message}' to '{processed_message}'")
            logger.info(f"Context info: {context_info}")
        
        # Use the processed message for subsequent operations
        user_message = processed_message
        processed_message = user_message.strip().lower()
        
        # Add some debug logging to help diagnose pattern issues
        logger.debug(f"Processing message: '{user_message}' (lower: '{user_message.lower()}')")
        
        # Handle various user intents
        try:
            # Special handler for "how are you" type questions
            if re.search(r"^(?:how are you|how'?s it going|how you doing|how'?s things|how'?s your day|how have you been)(?:\s|$|\?|!|\.)", user_message):
                return get_how_are_you_response()
            
            # Check for greeting patterns
            greeting_patterns = [
                r"^(?:hello|hi|hey|howdy|greetings|good\s(?:morning|afternoon|evening|day))(?:\s|$|!|\.)",
                r"^(?:hello|hi|hey|howdy|greetings)(?:\s|$|!|\.)(?:there|assistant|bot|chatbot|nexus)",
                r"^(?:morning|afternoon|evening)(?:\s|$|!|\.)",
                r"^(?:yo|sup|hiya|heya)(?:\s|$|!|\.)",
                r"^(?:what's up|how are you|how's it going|how are things|how you doing|whats up|wassup)(?:\s|$|\?|!|\.)",
                r"^(?:nice to see you|good to see you)(?:\s|$|!|\.)",
                r"^(?:hope you'?re doing well|hope you'?re good)(?:\s|$|!|\.)"
            ]
            
            for pattern in greeting_patterns:
                if re.search(pattern, user_message.lower()):
                    logger.debug(f"Greeting pattern matched: {pattern}")
                    
                    # Check if this is a casual greeting like "hey", "yo", etc.
                    is_casual = re.search(r"^(?:hey|hi|yo|sup|hiya|heya)(?:\s|$|!|\.)", user_message.lower())
                    
                    # Get appropriate greeting
                    if is_casual:
                        greeting_response = get_casual_greeting_response()
                    else:
                        greeting_response = get_greeting_response()
                    
                    # Import Task model inside the handler
                    from tasks.models import Task
                    
                    # Add task summary if user has pending tasks
                    pending_count = (Task.objects.filter(owner=user) | Task.objects.filter(assignees=user)).filter(~models.Q(status='completed')).distinct().count()
                    
                    if pending_count > 0:
                        due_today = (Task.objects.filter(owner=user) | Task.objects.filter(assignees=user)).filter(
                            ~models.Q(status='completed'),
                            due_date__date=timezone.now().date()
                        ).distinct().count()
                        
                        if due_today > 0:
                            greeting_response += f" You have {due_today} tasks due today."
                        elif pending_count == 1:
                            greeting_response += f" You have 1 pending task."
                        else:
                            greeting_response += f" You have {pending_count} pending tasks."
                    
                    return greeting_response
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            
            # Handle different types of errors more gracefully
            if "cannot access local variable 'Task'" in str(e):
                return "Hello! I'm your task management assistant. How can I help you today?"
            else:
                return "I apologize, but I'm having trouble processing your request. Please try asking in a simpler way or check with an administrator if the problem persists."
        
        # Add farewell detection after the greeting detection
        farewell_patterns = [
            r"^(?:bye|goodbye|see you|farewell|cya|talk to you later|ttyl)(?:\s|$|!|\.|,)",
            r"^(?:thanks|thank you)(?:\s|$|!|\.|,)(?:.*)(?:bye|goodbye|see you)",
            r"^(?:have to go|going now|leaving|I'm off)"
        ]

        for pattern in farewell_patterns:
            if re.search(pattern, user_message.lower()):
                # Choose from different farewell messages
                farewell_responses = [
                    custom_responses["farewell"],
                    custom_responses["farewell_alt"],
                    "Until next time! I'll be here when you need help with your tasks.",
                    "Goodbye! Remember to take breaks between tasks for better productivity.",
                    "See you soon! I'll keep an eye on your tasks while you're away."
                ]
                return random.choice(farewell_responses)
        
        # Check for task creation or automation attempts
        creation_patterns = [
            r"create (?:a )?(?:new )?task",
            r"add (?:a )?(?:new )?task",
            r"make (?:a )?(?:new )?task",
            r"start (?:a )?(?:new )?task",
            r"create (?:a )?(?:new )?project",
            r"add (?:a )?(?:new )?project", 
            r"make (?:a )?(?:new )?project",
            r"start (?:a )?(?:new )?project"
        ]
        
        for pattern in creation_patterns:
            if re.search(pattern, processed_message):
                return custom_responses["creation_not_supported"]
        
        if re.search(r"update|modify|change|edit", processed_message) and re.search(r"task|project", processed_message):
            return custom_responses["update_not_supported"]
        
        # Update the completion patterns by adding a simpler pattern
        completion_patterns = [
            r"mark (?:the )?task(?: named| called| titled)? (.*?) (?:as )?(?:complete|completed|done|finished)",
            r"mark (?:the )?task(?: )?(.*?) (?:as )?(?:complete|completed|done|finished)",
            r"mark (?:as )?(?:complete|completed|done|finished)(?: the)? task(?: named| called| titled)? (.*?)(?:$|\.|\?)",
            r"complete (?:the )?task(?: named| called| titled)? (.*?)(?:$|\.|\?)",
            r"complete (?:the )?task(?: )?(.*?)(?:$|\.|\?)",
            r"finish (?:the )?task(?: named| called| titled)? (.*?)(?:$|\.|\?)",
            r"finish (?:the )?task(?: )?(.*?)(?:$|\.|\?)",
            r"set (?:the )?task(?: named| called| titled)? (.*?) (?:as )?(?:complete|completed|done|finished)",
            r"set (?:the )?task(?: )?(.*?) (?:as )?(?:complete|completed|done|finished)",
            r"(?:i'?ve|i have) (?:complete|completed|finished|done)(?: the)? task(?: named| called| titled)? (.*?)(?:$|\.|\?)",
            r"(?:i'?ve|i have) (?:complete|completed|finished|done)(?: the)? task(?: )?(.*?)(?:$|\.|\?)",
            r"(?:mark|set) (.*?)(?: task)? (?:as )?(?:complete|completed|done|finished)(?:$|\.|\?)",
            r"(?:complete|finish|done with) (.*?)(?: task)?(?:$|\.|\?)",
            r"(?:i'?ve|i have) (?:complete|completed|finished|done) (.*?)(?: task)?(?:$|\.|\?)",
            r"mark all (?:my )?(?:tasks|overdue tasks) (?:as )?(?:complete|completed|done|finished)",
            r"complete all (?:my )?(?:tasks|overdue tasks)",
            r"finish all (?:my )?(?:tasks|overdue tasks)",
            r"mark (?:all|my) overdue (?:tasks )?(?:as )?(?:complete|completed|done|finished)",
            r"(?:complete|finish) (?:all|my) overdue (?:tasks)?",
            # Add simpler patterns for basic commands
            r"mark (?:it )?(?:as )?(?:complete|completed|done|finished)$",
            r"(?:complete|completed|done|finished|mark completed)$",
            # Add these new patterns at the end
            r"mark (?:it )?(?:as )?(?:complete|completed|done|finished)(?: then)?$",
            r"(?:complete|completed|done|finished|mark completed)(?: then)?$"
        ]
        
        # Check for general "mark task complete" request without specifying which task
        if (re.search(r"mark tasks? (?:as )?(?:complete|completed|done|finished)(?:\s+then)?$", processed_message) or 
            re.search(r"complete tasks?(?:\s+then)?$", processed_message) or 
            re.search(r"finish tasks?(?:\s+then)?$", processed_message) or 
            processed_message in ["mark complete", "complete", "mark as complete", "done", "finished", "completed", "mark completed", 
                                 "mark complete then", "mark completed then", "complete then", "mark as complete then", 
                                 "done then", "finished then", "completed then"]):
            
            # Check context first - do we have a previously mentioned task?
            if context_info['referenced_tasks'] and len(context_info['referenced_tasks']) == 1:
                task_title = context_info['referenced_tasks'][0]
                success, message = mark_task_complete(user, task_title=task_title)
                # Add a personal touch for successful completions
                if success:
                    return f"{message} 🎉 Great job on completing this task!"
                return message
            
            # No specific task mentioned, ask user which task
            # First, get incomplete tasks to show user options
            incomplete_tasks = (Task.objects.filter(owner=user) | Task.objects.filter(assignees=user)).filter(~models.Q(status='completed')).distinct()
            
            if incomplete_tasks.count() == 0:
                return "You don't have any incomplete tasks to mark as completed. Would you like to create a new task instead?"
            elif incomplete_tasks.count() == 1:
                # Only one task, let's complete it
                task = incomplete_tasks.first()
                success, message = mark_task_complete(user, task_id=task.id)
                if success:
                    return f"{message} 🎉 Well done!"
                return message
            else:
                # Multiple tasks, show options with a friendly tone
                task_list = [f"• {task.title}" for task in incomplete_tasks[:7]]
                return f"I'd be happy to mark a task as completed! Which one did you finish? Please specify by saying 'mark [task name] as completed', or just reply with the task name or number.\n\nHere are your incomplete tasks:\n\n" + "\n".join(task_list) + (f"\n\n(Showing 7 of {incomplete_tasks.count()} tasks)" if incomplete_tasks.count() > 7 else "")
        
        # Check for task deletion requests
        deletion_patterns = [
            r"delete (?:the )?task(?: named| called| titled)? (.*?)(?:$|\.|\?)",
            r"delete (?:the )?task(?: )?(.*?)(?:$|\.|\?)",
            r"remove (?:the )?task(?: named| called| titled)? (.*?)(?:$|\.|\?)",
            r"remove (?:the )?task(?: )?(.*?)(?:$|\.|\?)",
            r"(?:get rid of|trash|discard|eliminate) (?:the )?task(?: named| called| titled)? (.*?)(?:$|\.|\?)",
            r"(?:get rid of|trash|discard|eliminate) (?:the )?task(?: )?(.*?)(?:$|\.|\?)",
            r"(?:erase|cancel) (?:the )?task(?: named| called| titled)? (.*?)(?:$|\.|\?)",
            r"(?:erase|cancel) (?:the )?task(?: )?(.*?)(?:$|\.|\?)",
            r"(?:delete|remove|get rid of|trash|discard|eliminate|erase|cancel) (.*?)(?: task)?(?:$|\.|\?)"
        ]
        
        if re.search(r"delete|remove|get rid of|trash|discard|eliminate|erase|cancel", processed_message) and re.search(r"task", processed_message):
            # Check context first - do we have a previously mentioned task?
            if context_info['referenced_tasks'] and len(context_info['referenced_tasks']) == 1:
                task_title = context_info['referenced_tasks'][0]
                success, message = delete_task(user, task_title=task_title)
                return message
                
            # Try to extract task name from the message
            task_title = None
            for pattern in deletion_patterns:
                match = re.search(pattern, processed_message)
                if match and match.groups() and match.group(1) and match.group(1).strip():
                    task_title = match.group(1).strip()
                    break
                    
            if task_title:
                success, message = delete_task(user, task_title=task_title)
                return message
            else:
                # No specific task mentioned, ask user which task
                tasks = (Task.objects.filter(owner=user) | Task.objects.filter(assignees=user)).distinct()
                
                if tasks.count() == 0:
                    return "You don't have any tasks to delete."
                elif tasks.count() == 1:
                    # Only one task, confirm deletion
                    task = tasks.first()
                    return f"You only have one task: '{task.title}'. To delete it, please say 'delete task {task.title}' or simply 'delete this task'."
                else:
                    # Multiple tasks, show options
                    task_list = [f"• {task.title}" for task in tasks[:7]]
                    return f"Which task would you like to delete? Please specify by saying 'delete [task name]' or simply reply with 'this one' after the task name. Here are your tasks:\n\n" + "\n".join(task_list) + (f"\n\n(Showing 7 of {tasks.count()} tasks)" if tasks.count() > 7 else "")
        
        # Check for project deletion requests
        project_deletion_patterns = [
            r"delete (?:the )?project(?: named| called| titled)? (.*?)(?:$|\.|\?)",
            r"delete (?:the )?project(?: )?(.*?)(?:$|\.|\?)",
            r"remove (?:the )?project(?: named| called| titled)? (.*?)(?:$|\.|\?)",
            r"remove (?:the )?project(?: )?(.*?)(?:$|\.|\?)",
            r"(?:get rid of|trash|discard|eliminate) (?:the )?project(?: named| called| titled)? (.*?)(?:$|\.|\?)",
            r"(?:get rid of|trash|discard|eliminate) (?:the )?project(?: )?(.*?)(?:$|\.|\?)",
            r"(?:erase|cancel) (?:the )?project(?: named| called| titled)? (.*?)(?:$|\.|\?)",
            r"(?:erase|cancel) (?:the )?project(?: )?(.*?)(?:$|\.|\?)"
        ]
        
        if re.search(r"delete|remove|get rid of|trash|discard|eliminate|erase|cancel", processed_message) and re.search(r"project", processed_message):
            # Check context first - do we have a previously mentioned project?
            if context_info['referenced_projects'] and len(context_info['referenced_projects']) == 1:
                project_name = context_info['referenced_projects'][0]
                success, message = delete_project(user, project_name=project_name)
                return message
            
            # Try to extract project name from the message
            project_name = None
            for pattern in project_deletion_patterns:
                match = re.search(pattern, processed_message)
                if match and match.groups() and match.group(1) and match.group(1).strip():
                    project_name = match.group(1).strip()
                    break
                    
            if project_name:
                success, message = delete_project(user, project_name=project_name)
                return message
            else:
                # No specific project mentioned, ask user which project
                projects = Project.objects.filter(members=user)
                
                if projects.count() == 0:
                    return "You don't have any projects to delete."
                elif projects.count() == 1:
                    # Only one project, confirm deletion
                    project = projects.first()
                    # Check ownership
                    if hasattr(project, 'owner') and project.owner != user:
                        return f"You're a member of project '{project.name}', but only the owner can delete it."
                    return f"You have one project: '{project.name}'. To delete it, please say 'delete project {project.name}' or simply 'delete this project'."
                else:
                    # Multiple projects, show options
                    project_list = [f"• {project.name}" for project in projects[:7]]
                    return f"Which project would you like to delete? Please specify by saying 'delete [project name]' or reply with 'this one' after seeing the list. Here are your projects:\n\n" + "\n".join(project_list) + (f"\n\n(Showing 7 of {projects.count()} projects)" if projects.count() > 7 else "")
        
        # First check if this is a statistics request
        if check_general_statistics_request(user_message):
            stats_response = get_user_statistics(user)
            return stats_response
        elif check_task_statistics_request(user_message):
            task_counts = get_user_statistics(user)
            return task_counts
        elif check_project_statistics_request(user_message):
            project_counts = get_user_statistics(user)
            return project_counts
        
        # --- ENHANCED TASK QUERIES ---
        
        # Check for task list requests (more comprehensive patterns)
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
        
        is_task_list_request = any(re.search(pattern, processed_message) for pattern in task_list_patterns)
        
        if is_task_list_request:
            try:
                # Start with all user's tasks - NOTE: Task model uses 'assignees' not 'assigned_to'
                tasks = Task.objects.filter(assignees=user) | Task.objects.filter(owner=user)
                tasks = tasks.distinct()  # Remove duplicates
                total_count = tasks.count()
                filter_description = "all"
                
                # Check for filters with expanded patterns
                if re.search(r"pending|incomplete|ongoing|open|in progress|not done|to do|active|current|todo|unfinished|not complete", processed_message):
                    tasks = tasks.filter(status__in=['new', 'in_progress'])
                    filter_description = "pending"
                elif re.search(r"complete|finished|done|did|completed|closed|resolved", processed_message):
                    tasks = tasks.filter(status='completed')
                    filter_description = "completed"
                elif re.search(r"overdue|late|missed|past due|delayed|expired", processed_message):
                    tasks = tasks.filter(due_date__lt=timezone.now()).exclude(status='completed')
                    filter_description = "overdue"
                elif re.search(r"upcoming|future|scheduled|next|this week|tomorrow|soon|coming|advance|planned", processed_message):
                    today = timezone.now()
                    next_week = today + datetime.timedelta(days=7)
                    tasks = tasks.filter(due_date__gte=today, due_date__lte=next_week).exclude(status='completed')
                    filter_description = "upcoming (next 7 days)"
                elif re.search(r"today|due today|for today", processed_message):
                    today = timezone.now().date()
                    tasks = tasks.filter(due_date__date=today).exclude(status='completed')
                    filter_description = "due today"
                elif re.search(r"high priority|important|urgent|critical|highest|top priority", processed_message):
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
                logger.error(f"Error in task listing: {str(e)}")
                return f"I encountered an issue retrieving your tasks. Please try another type of query or contact support if this persists."
        
        # Project information requests - with expanded patterns
        project_list_patterns = [
            r"(?:show|list|view|get|display|what are).*(?:my )?projects?",
            r"(?:what|which) projects? (?:do|have|did) I",
            r"tell me about my projects?",
            r"projects? information",
            r"information about (?:my )?projects?",
            r"(?:all|any) (?:of )?(?:my )?projects?",
            r"do i have (?:any )?projects?",
            r"my projects?",
            r"projects? (?:list|overview)",
            r"check (?:my )?projects?",
            r"projects? (?:status|progress)"
        ]
        
        is_project_list_request = any(re.search(pattern, processed_message) for pattern in project_list_patterns)
        
        if is_project_list_request:
            try:
                # Get all user's projects
                projects = Project.objects.filter(members=user)
                
                # Check for specific filters with expanded patterns
                project_filter = "all"
                if re.search(r"active|ongoing|current|in progress|open|not done|in development|running|live", processed_message):
                    projects = projects.filter(status='active')
                    project_filter = "active"
                elif re.search(r"complete|finished|done|completed|closed|ended|delivered|finalized", processed_message):
                    projects = projects.filter(status='completed') 
                    project_filter = "completed"
                elif re.search(r"recent|latest|newest|new|just added|last|current", processed_message):
                    projects = projects.order_by('-created_at')[:5]
                    project_filter = "recent"
                    
                if projects.exists():
                    response = f"Here are your {project_filter} projects:\n\n"
                    
                    # Show up to 10 projects
                    display_projects = projects[:10]
                    for project in display_projects:
                        created_date = project.created_at.strftime('%Y-%m-%d') if hasattr(project, 'created_at') else "N/A"
                        status_str = f" - Status: {project.get_status_display()}" if hasattr(project, 'get_status_display') else ""
                        
                        # Count tasks in this project
                        try:
                            task_count = Task.objects.filter(project=project).count()
                            completed_count = Task.objects.filter(project=project, status='completed').count()
                            progress = "0%" if task_count == 0 else f"{(completed_count/task_count)*100:.1f}%"
                            
                            response += f"• {project.name}{status_str} - Progress: {progress} ({completed_count}/{task_count} tasks)\n"
                        except Exception as e:
                            # Fallback if task counting fails
                            response += f"• {project.name}{status_str}\n"
                    
                    if projects.count() > 10:
                        response += f"\n(Showing 10 of {projects.count()} {project_filter} projects)"
                    
                    return response
                else:
                    return f"You don't have any {project_filter} projects at the moment."
            except Exception as e:
                logger.error(f"Error in project listing: {str(e)}")
                return f"I encountered an issue retrieving your projects. Please try another type of query or contact support if this persists."
        
        # Task summary/dashboard-like query - with expanded patterns
        dashboard_patterns = [
            r"dashboard|summary|overview|snapshot",
            r"(?:task|project)s? summary",
            r"(?:give|show) me (?:a )?summary",
            r"status report",
            r"(?:how am i|how are my tasks) doing",
            r"progress report",
            r"(?:my )?task(?: manager)? status",
            r"quick overview",
            r"current status"
        ]
        
        is_dashboard_request = any(re.search(pattern, processed_message) for pattern in dashboard_patterns)
        
        if is_dashboard_request:
            try:
                # Task statistics - using both owner and assignees
                total_tasks = (Task.objects.filter(owner=user) | Task.objects.filter(assignees=user)).distinct().count()
                completed_tasks = (Task.objects.filter(owner=user, status='completed') | Task.objects.filter(assignees=user, status='completed')).distinct().count()
                pending_tasks = total_tasks - completed_tasks
                
                # Get overdue tasks
                now = timezone.now()
                overdue_query = models.Q(due_date__lt=now) & ~models.Q(status='completed')
                overdue_tasks = (Task.objects.filter(owner=user).filter(overdue_query) | 
                                Task.objects.filter(assignees=user).filter(overdue_query)).distinct().count()
                
                # Projects statistics
                total_projects = Project.objects.filter(members=user).count()
                
                # Create a dashboard-like response
                response = "📊 **Your Nexus Dashboard**\n\n"
                response += "**Tasks Summary:**\n"
                response += f"• Total Tasks: {total_tasks}\n"
                response += f"• Completed: {completed_tasks}\n"
                response += f"• Pending: {pending_tasks}\n"
                response += f"• Overdue: {overdue_tasks}\n\n"
                
                # Add upcoming tasks if any
                today = timezone.now()
                next_week = today + datetime.timedelta(days=7)
                upcoming_query = models.Q(due_date__gte=today, due_date__lte=next_week) & ~models.Q(status='completed')
                
                upcoming_tasks = (Task.objects.filter(owner=user).filter(upcoming_query) | 
                                 Task.objects.filter(assignees=user).filter(upcoming_query)
                                ).distinct().order_by('due_date')
                
                if upcoming_tasks.exists():
                    response += "**Upcoming Tasks (Next 7 Days):**\n"
                    for task in upcoming_tasks[:5]:  # Show max 5
                        due_date_str = task.due_date.strftime('%Y-%m-%d') if task.due_date else "No due date"
                        response += f"• {task.title} - Due: {due_date_str}\n"
                    
                    if upcoming_tasks.count() > 5:
                        response += f"• ... and {upcoming_tasks.count() - 5} more\n"
                
                # Project info if exists
                if total_projects > 0:
                    response += f"\n**Projects:** {total_projects} total projects\n"
                
                return response
            except Exception as e:
                logger.error(f"Error generating dashboard: {str(e)}")
                return f"I encountered an issue generating your dashboard. Please try another type of query or contact support if this persists."
        
        # Search for tasks by keyword in title/description - with expanded patterns
        task_search_patterns = [
            r"(?:search|find|look for).*task(?:s)? (?:with|containing|about|related to) (.*)",
            r"(?:search|find|look for) (.*) in (?:my )?tasks",
            r"tasks? (?:with|containing|about|related to) (.*)",
            r"(?:find|show|get|are there) (?:any )?tasks? (?:with|about|containing|related to) (.*)",
            r"(?:tasks?|anything) (?:on|about|regarding|concerning|involving) (.*)",
            r"search(?:ing)? for (.*) (?:in|among) tasks?"
        ]
        
        for pattern in task_search_patterns:
            match = re.search(pattern, processed_message)
            if match:
                try:
                    search_term = match.group(1).strip()
                    if search_term:
                        # Search in both owner and assignees
                        matching_tasks = (
                            Task.objects.filter(owner=user).filter(
                                models.Q(title__icontains=search_term) | 
                                models.Q(description__icontains=search_term)
                            ) | 
                            Task.objects.filter(assignees=user).filter(
                                models.Q(title__icontains=search_term) | 
                                models.Q(description__icontains=search_term)
                            )
                        ).distinct()
                        
                        if matching_tasks.exists():
                            response = f"Here are tasks matching '{search_term}':\n\n"
                            for task in matching_tasks[:10]:
                                status_str = task.get_status_display() if hasattr(task, 'get_status_display') else task.status
                                response += f"• {task.title} - Status: {status_str}\n"
                            
                            if matching_tasks.count() > 10:
                                response += f"\n(Showing 10 of {matching_tasks.count()} matching tasks)"
                            
                            return response
                        else:
                            return f"I couldn't find any tasks containing '{search_term}'. Would you like to try a different search term?"
                except Exception as e:
                    logger.error(f"Error in task search: {str(e)}")
                    return f"I encountered an issue searching your tasks. Please try another search term or contact support if this persists."
        
        # Check for task list requests - check context for "this task" references
        if context_info['referencing_previous'] and context_info['action_context'] == 'completion':
            # User is trying to complete a task referenced in conversation
            if context_info['referenced_tasks'] and len(context_info['referenced_tasks']) == 1:
                task_title = context_info['referenced_tasks'][0]
                success, message = mark_task_complete(user, task_title=task_title)
                return message
        
        # Check for the case where user simply responds with "this task" or "this one"
        if re.search(r'^(?:this|that|the) (?:task|one)$', processed_message) or processed_message == 'this' or processed_message == 'that':
            # User is likely responding to a previous message that listed tasks
            bot_messages = [msg for msg in conversation_context if msg['role'] == 'assistant']
            if bot_messages:
                last_bot_message = bot_messages[-1]['content'].lower()
                
                # If last message was asking which task to complete/delete/view
                if 'which task' in last_bot_message:
                    # Extract the first task in the list (most likely what user is referring to)
                    tasks_in_message = re.findall(r'• (.*?)(?:\n|$)', bot_messages[-1]['content'])
                    if tasks_in_message:
                        task_title = tasks_in_message[0]
                        
                        # Determine what action to take based on context
                        if 'mark' in last_bot_message and 'complete' in last_bot_message:
                            success, message = mark_task_complete(user, task_title=task_title)
                            return message
                        elif 'delete' in last_bot_message:
                            success, message = delete_task(user, task_title=task_title)
                            return message
                        else:
                            # Default to showing task details
                            return f"I'll show you details about '{task_title}'. However, my task detail viewing functionality is limited. Please use the main interface for more detailed information."
            
            # If we can't determine context, ask for clarification
            return "I'm not sure which task you're referring to. Could you please specify the task name or what you'd like to do?"
        
        # Add back the handling for overdue tasks
        # Check if this is about completing all overdue tasks
        if re.search(r"(?:mark|complete|finish) (?:all|my) overdue", processed_message) or re.search(r"(?:mark|complete|finish) all (?:my )?(?:tasks|overdue tasks)", processed_message):
            success, message, count = mark_overdue_tasks_complete(user, all_overdue=True)
            if success and count > 0:
                return f"{message} 🎉 That's a great way to clear your task list!"
            return message
        
        # Add a pattern handler for "What I have?" after the greeting and farewell patterns
        # This handler should show tasks and projects information
        inventory_patterns = [
            r"^(?:what|which|show) (?:do )?i have(?:\?|$)",
            r"^(?:show|tell) me what i have(?:\?|$)",
            r"^(?:list|display) (?:all )?(?:my )?(?:stuff|items|things)(?:\?|$)",
            r"^(?:what are|what's) (?:my|all my)(?:\s|\?|$)",
            r"^my (?:stuff|tasks and projects)(?:\?|$)"
        ]

        for pattern in inventory_patterns:
            if re.search(pattern, user_message.lower()):
                # Create a comprehensive summary of all user's items
                response = "📋 **Here's what you have:**\n\n"
                
                # Get task information
                all_tasks = (Task.objects.filter(owner=user) | Task.objects.filter(assignees=user)).distinct()
                completed_tasks = all_tasks.filter(status='completed')
                pending_tasks = all_tasks.exclude(status='completed')
                
                # Get project information
                all_projects = Project.objects.filter(members=user)
                
                # Add task statistics
                response += f"**Tasks:** {all_tasks.count()} total\n"
                response += f"• {pending_tasks.count()} pending tasks\n"
                response += f"• {completed_tasks.count()} completed tasks\n"
                
                # Add due today information
                today = timezone.now().date()
                due_today = pending_tasks.filter(due_date__date=today).count()
                if due_today > 0:
                    response += f"• {due_today} tasks due today\n"
                
                # Add overdue information
                overdue = pending_tasks.filter(due_date__lt=timezone.now()).count()
                if overdue > 0:
                    response += f"• {overdue} overdue tasks\n"
                
                # Add high priority information
                high_priority = pending_tasks.filter(priority__in=['high', 'urgent', 'critical']).count()
                if high_priority > 0:
                    response += f"• {high_priority} high priority tasks\n"
                
                # Add project statistics if any projects exist
                if all_projects.exists():
                    response += f"\n**Projects:** {all_projects.count()} total\n"
                    
                    # Get active vs completed projects if status field exists
                    if hasattr(Project.objects.first(), 'status'):
                        active_projects = all_projects.filter(status='active').count()
                        completed_projects = all_projects.filter(status='completed').count()
                        response += f"• {active_projects} active projects\n"
                        if completed_projects > 0:
                            response += f"• {completed_projects} completed projects\n"
                
                # Add recent activity
                if all_tasks.exists():
                    last_created = all_tasks.order_by('-created_at').first()
                    if last_created:
                        response += f"\n**Recent Activity:**\n"
                        created_time = last_created.created_at
                        time_diff = timezone.now() - created_time
                        days_ago = time_diff.days
                        if days_ago == 0:
                            time_str = "today"
                        elif days_ago == 1:
                            time_str = "yesterday"
                        else:
                            time_str = f"{days_ago} days ago"
                        response += f"• Last task created: '{last_created.title}' ({time_str})\n"
                    
                    last_completed = completed_tasks.order_by('-completed_at').first() if hasattr(Task, 'completed_at') else completed_tasks.order_by('-updated_at').first()
                    if last_completed:
                        # Use the appropriate timestamp field
                        completion_time = getattr(last_completed, 'completed_at', None) or last_completed.updated_at
                        time_diff = timezone.now() - completion_time
                        days_ago = time_diff.days
                        if days_ago == 0:
                            time_str = "today"
                        elif days_ago == 1:
                            time_str = "yesterday"
                        else:
                            time_str = f"{days_ago} days ago"
                        response += f"• Last task completed: '{last_completed.title}' ({time_str})\n"
                
                # Add a suggestion for next steps
                response += "\nWhat would you like to do with these items?"
                
                return response
        
        # Also update the final fallback for unclear queries to be more personalized
        # Add the following before the MistralAI call
        unclear_patterns = [
            r"^(\w+)$",  # Single word queries
            r"^\w+\s\w+$",  # Two word queries that didn't match any patterns
            r"^(?:umm|hmm|err|uh|well|so|like)(?:\s|$)",  # Thinking sounds
            r"^\?+$",  # Just question marks
            r"^test$",  # Test queries
            r"^[^\w\s]+$"  # Just symbols
        ]

        for pattern in unclear_patterns:
            if re.search(pattern, processed_message):
                suggestions = [
                    f"I'm not sure I understand. Would you like to:\n\n• See your tasks?\n• View project progress?\n• Get statistics on your work?",
                    f"I'm sorry, but I didn't quite catch that. Here are some things I can help with:\n\n• Showing your tasks and projects\n• Marking tasks as completed\n• Providing productivity statistics",
                    f"I'm not sure what you're asking for. I can help you with task management, like listing your tasks, showing project details, or marking tasks as completed. What would you like to do?",
                    f"I didn't understand your request. Could you try rephrasing it? For example, you can ask me to 'show my tasks' or 'list my projects'."
                ]
                return random.choice(suggestions)
        
        # For other inquiries, use the conversational AI but with a more structured system prompt
        try:
            # Get relevant user context data for this query
            from .utils import get_user_context_data
            
            # Add specific handling for completed tasks queries
            user_message_lower = user_message.lower()
            try:
                if any(phrase in user_message_lower for phrase in ['completed task', 'completed tasks', 'finished task', 'finished tasks', 'done tasks']):
                    # Import models here to avoid scope issues
                    from tasks.models import Task
                    
                    # Force include all completed tasks in the context
                    completed_tasks = Task.objects.filter(
                        assignees=user,
                        status='completed',
                        is_archived=False
                    ).order_by('-completed_at')[:10]
                    
                    completed_tasks_context = "RECENTLY COMPLETED TASKS:\n"
                    if completed_tasks.exists():
                        for i, task in enumerate(completed_tasks, 1):
                            completed_info = f", completed {task.completed_at.strftime('%b %d')}" if task.completed_at else ""
                            completed_tasks_context += f"{i}. {task.title}{completed_info}\n"
                    else:
                        completed_tasks_context += "You don't have any completed tasks yet.\n"
                    
                    # Get regular context data
                    user_context_data = get_user_context_data(user=user, query=user_message)
                    
                    # Ensure completed tasks are always included
                    if "RECENTLY COMPLETED TASKS:" not in user_context_data:
                        user_context_data = completed_tasks_context + "\n" + user_context_data
                else:
                    # Regular query, get standard context
                    user_context_data = get_user_context_data(user=user, query=user_message)
            except Exception as e:
                logger.error(f"Error in task listing: {str(e)}")
                # Fall back to standard context data
                user_context_data = get_user_context_data(user=user, query=user_message)
            
            # Create a more comprehensive system message with user data
            system_message = {
                "role": "system",
                "content": f"""You are a helpful, friendly task management assistant called TaskBuddy. Your goal is to be supportive, positive, and solution-oriented.

Your capabilities:
1. Providing statistics and insights about the user's tasks and projects
2. Showing lists of tasks and projects with different filters
3. Helping the user mark tasks as completed
4. Answering questions about task management best practices

IMPORTANT RULES:
1. You CANNOT create new tasks - always inform the user that they need to use the "Add Task" button
2. You CANNOT update tasks - always inform the user that they need to edit the task directly
3. For ANY acknowledgment like "thank you" or "thanks", respond positively (e.g., "You're welcome! How else can I help?")
4. NEVER say you don't have access to task data - all the user's data is provided below
5. ALWAYS give the SPECIFIC information the user asks for, referencing the context below
6. ALWAYS be friendly and personable, but primarily focused on the task at hand
7. For any ambiguous queries, ask clarifying questions instead of saying you cannot help

===== USER CONTEXT DATA =====
{user_context_data}
===== END USER CONTEXT DATA =====

Communication style:
- Professional but warm and conversational
- Celebrate accomplishments when tasks are completed
- Provide clear, actionable information
- Be encouraging and supportive of productivity goals

When responding:
- Start with a brief acknowledgment of the user's request
- Provide the requested information clearly and concisely using the context data
- Add a small personal or encouraging touch when appropriate
- For simple acknowledgments or thanks, respond warmly and ask how else you can help
- If you can't perform an action due to the rules, suggest appropriate alternatives

You are the user's trusted productivity partner!
"""
            }
            
            # Get recent conversation history (last 10 messages)
            recent_messages = Message.objects.filter(conversation=conversation).order_by('timestamp')[:10]
            conversation_history = []
            
            for msg in recent_messages:
                conversation_history.append({
                    "role": "user" if msg.is_user else "assistant",
                    "content": msg.content
                })
            
            # Add the latest user message if not already in history
            # First get all messages to check the last one
            all_msgs = list(recent_messages)
            latest_is_user = False if not all_msgs else all_msgs[-1].is_user
            
            if not all_msgs or not latest_is_user:
                conversation_history.append({
                    "role": "user",
                    "content": user_message
                })
            
            # Complete conversation history with system message
            complete_messages = [system_message] + conversation_history
            
            # Call Mistral AI API
            mistral_api_key = getattr(settings, 'MISTRAL_API_KEY', os.environ.get("MISTRAL_API_KEY"))
            if not mistral_api_key:
                logger.error("MISTRAL_API_KEY not configured.")
                return "I'm currently having trouble connecting to my knowledge base due to a configuration issue. Please contact an administrator."

            headers = {
                "Authorization": f"Bearer {mistral_api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            payload = {
                "model": "mistral-small-latest",  # Or other preferred Mistral model
                "messages": complete_messages,
                "max_tokens": 400,  # Increased to allow for more detailed responses
                "temperature": 0.7,  # Slightly increased for more varied responses
            }
            
            # Log the query and context (without complete history to avoid too much logging)
            log_payload = payload.copy()
            log_payload["messages"] = [system_message] + [{"role": "user", "content": user_message}]
            logger.debug(f"Sending to Mistral AI: {json.dumps(log_payload)}")
            
            try:
                with httpx.Client(timeout=30.0) as client: # Added timeout
                    api_response = client.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload)
                
                api_response.raise_for_status() # Will raise an exception for 4XX/5XX_STATUS_CODES status codes
                
                response_data = api_response.json()
                bot_response = response_data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
                
                if not bot_response:
                    logger.error(f"Mistral API returned empty content. Response: {response_data}")
                    return "I received an empty response from the AI. Please try again."
                    
                # Special handling for acknowledgements/thanks
                if user_message.lower() in ['thanks', 'thank you', 'thanks a lot', 'thank you so much', 'thx', 'ty']:
                    # If the response seems generic, use a friendlier version
                    if "don't have" in bot_response.lower() or "cannot" in bot_response.lower() or "unable" in bot_response.lower():
                        return "You're welcome! Is there anything else I can help you with regarding your tasks or projects?"
                
                return bot_response
            
            except httpx.HTTPStatusError as e:
                logger.error(f"Mistral API HTTPStatusError: {e.response.status_code} - {e.response.text}")
                return "I'm currently having trouble connecting to my knowledge base (API error). Please try again later."
            except httpx.RequestError as e:
                logger.error(f"Mistral API RequestError: {str(e)}")
                return "I'm currently having trouble connecting to my knowledge base (network error). Please try again later."
            except Exception as e: # Catch other potential errors like JSONDecodeError
                logger.error(f"Error processing Mistral API response: {str(e)}")
                return "I encountered an unexpected issue with the AI service. Please try again."

        except Exception as e:
            logger.error(f"Error with Mistral AI: {str(e)}")
            return "I'm currently having trouble connecting to my knowledge base. Please try asking about your tasks or projects in a different way."
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        return "I apologize, but I'm having trouble processing your request. Please try asking in a simpler way or check with an administrator if the problem persists."

@login_required
def get_conversations(request):
    """Get all conversations for a user"""
    try:
        conversations = Conversation.objects.filter(user=request.user).order_by('-last_updated')
        conversations_data = [{
            'id': conv.id,
            'title': conv.title,
            'updated_at': conv.last_updated.strftime("%Y-%m-%d %H:%M:%S")
        } for conv in conversations]
        
        return JsonResponse({'conversations': conversations_data})
    except Exception as e:
        logger.error(f"Error retrieving conversations: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_conversation_messages(request, conversation_id):
    """Get all messages for a specific conversation"""
    try:
        conversation = Conversation.objects.get(id=conversation_id, user=request.user)
        messages = Message.objects.filter(conversation=conversation).order_by('timestamp')
        
        messages_data = [{
            'id': msg.id,
            'content': msg.content,
            'role': msg.role,
            'created_at': msg.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        } for msg in messages]
        
        return JsonResponse({
            'conversation_id': conversation.id,
            'title': conversation.title,
            'messages': messages_data
        })
    except Conversation.DoesNotExist:
        return JsonResponse({'error': 'Conversation not found'}, status=404)
    except Exception as e:
        logger.error(f"Error retrieving conversation messages: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

# Function to delete a task
def delete_task(user, task_title=None, task_id=None):
    """
    Delete a task based on title or ID.
    Returns tuple of (success_bool, message)
    """
    try:
        if task_id:
            # Try to find the exact task by ID
            task = Task.objects.filter(
                models.Q(assignees=user) | models.Q(owner=user),
                id=task_id
            ).first()
            
            if task:
                task_title = task.title
                task.delete()
                return True, f"Task '{task_title}' has been successfully deleted."
            else:
                return False, f"Task with ID '{task_id}' not found or you don't have permission to delete it."
        
        elif task_title:
            # Try to find tasks containing this title text
            matching_tasks = Task.objects.filter(
                models.Q(assignees=user) | models.Q(owner=user)
            ).filter(
                models.Q(title__icontains=task_title)
            )
            
            if matching_tasks.count() == 0:
                return False, f"No tasks found containing '{task_title}' in the title."
            elif matching_tasks.count() == 1:
                # Only one match, let's delete it
                task = matching_tasks.first()
                task_name = task.title
                task.delete()
                return True, f"Task '{task_name}' has been successfully deleted."
            else:
                # Multiple matches, provide a list
                task_list = [f"• {task.title}" for task in matching_tasks[:5]]
                additional = f" and {matching_tasks.count() - 5} more" if matching_tasks.count() > 5 else ""
                return False, f"I found {matching_tasks.count()} tasks containing '{task_title}'. Please be more specific:\n\n" + "\n".join(task_list[:5]) + additional
        else:
            return False, "No task title or ID provided."
    except Exception as e:
        logger.error(f"Error deleting task: {str(e)}")
        return False, f"An error occurred while trying to delete the task. Please try again."

# Function to delete a project
def delete_project(user, project_name=None, project_id=None):
    """
    Delete a project based on name or ID.
    Returns tuple of (success_bool, message)
    """
    try:
        if project_id:
            # Try to find the exact project by ID
            project = Project.objects.filter(
                members=user,
                id=project_id
            ).first()
            
            if project:
                # Check if user is project owner
                if hasattr(project, 'owner') and project.owner != user:
                    return False, "You don't have permission to delete this project. Only the project owner can delete it."
                
                project_name = project.name
                project.delete()
                return True, f"Project '{project_name}' has been successfully deleted."
            else:
                return False, f"Project with ID '{project_id}' not found or you don't have permission to delete it."
        
        elif project_name:
            # Try to find projects containing this name text
            matching_projects = Project.objects.filter(
                members=user
            ).filter(
                name__icontains=project_name
            )
            
            if matching_projects.count() == 0:
                return False, f"No projects found containing '{project_name}' in the name."
            elif matching_projects.count() == 1:
                # Only one match, check permission and delete
                project = matching_projects.first()
                
                # Check if user is project owner
                if hasattr(project, 'owner') and project.owner != user:
                    return False, "You don't have permission to delete this project. Only the project owner can delete it."
                
                project_title = project.name
                project.delete()
                return True, f"Project '{project_title}' has been successfully deleted."
            else:
                # Multiple matches, provide a list
                project_list = [f"• {project.name}" for project in matching_projects[:5]]
                additional = f" and {matching_projects.count() - 5} more" if matching_projects.count() > 5 else ""
                return False, f"I found {matching_projects.count()} projects containing '{project_name}'. Please be more specific:\n\n" + "\n".join(project_list[:5]) + additional
        else:
            return False, "No project name or ID provided."
    except Exception as e:
        logger.error(f"Error deleting project: {str(e)}")
        return False, f"An error occurred while trying to delete the project. Please try again."

# Function to mark a task as completed
def mark_task_complete(user, task_title=None, task_id=None):
    """
    Mark a task as completed based on title or ID.
    Returns tuple of (success_bool, message)
    """
    try:
        # Get total and completed tasks counts
        all_tasks = (Task.objects.filter(owner=user) | Task.objects.filter(assignees=user)).distinct()
        completed_tasks = all_tasks.filter(status='completed')
        
        # If all tasks are already completed, return specific message
        if all_tasks.count() > 0 and all_tasks.count() == completed_tasks.count():
            return False, "You don't have any incomplete tasks to mark as completed. All your tasks are already marked as complete! 🎉"
        
        if task_id:
            # Try to find the exact task by ID
            task = Task.objects.filter(
                models.Q(assignees=user) | models.Q(owner=user),
                id=task_id
            ).first()
            
            if task:
                if task.status == 'completed':
                    return False, f"The task '{task.title}' is already marked as completed."
                task.status = 'completed'
                if hasattr(task, 'completed_at'):
                    task.completed_at = timezone.now()
                task.save()
                return True, f"✅ Task '{task.title}' has been marked as completed."
            else:
                return False, f"I couldn't find that task. It may have been deleted or you might not have permission to modify it."
        
        elif task_title:
            # Try to find tasks containing this title text
            matching_tasks = Task.objects.filter(
                models.Q(assignees=user) | models.Q(owner=user)
            ).filter(
                models.Q(title__icontains=task_title)
            ).exclude(status='completed')
            
            if matching_tasks.count() == 0:
                return False, f"I couldn't find any incomplete tasks matching '{task_title}'. It might already be completed or have a different name."
            elif matching_tasks.count() == 1:
                # Only one match, let's complete it
                task = matching_tasks.first()
                task.status = 'completed'
                if hasattr(task, 'completed_at'):
                    task.completed_at = timezone.now()
                task.save()
                return True, f"✅ Task '{task.title}' has been marked as completed."
            else:
                # Multiple matches, provide a list with friendly tone
                task_list = [f"• {task.title}" for task in matching_tasks[:5]]
                additional = f" and {matching_tasks.count() - 5} more" if matching_tasks.count() > 5 else ""
                return False, f"I found several tasks matching '{task_title}'. Which one would you like to complete?\n\n" + "\n".join(task_list[:5]) + additional
        else:
            # If no specific task is mentioned, check if there's only one incomplete task
            incomplete_tasks = all_tasks.exclude(status='completed')
            
            if incomplete_tasks.count() == 0:
                return False, "You don't have any incomplete tasks to mark as completed. Would you like to create a new task instead?"
            elif incomplete_tasks.count() == 1:
                # If there's only one incomplete task, mark it complete
                task = incomplete_tasks.first()
                task.status = 'completed'
                if hasattr(task, 'completed_at'):
                    task.completed_at = timezone.now()
                task.save()
                return True, f"✅ I've marked your only incomplete task '{task.title}' as completed. Great job!"
            else:
                # Multiple tasks, show options with a friendly tone
                task_list = [f"• {task.title}" for task in incomplete_tasks[:7]]
                return False, f"I'd be happy to mark a task as completed! Which one did you finish? Please specify by saying 'mark [task name] as completed', or just reply with the task name or number.\n\nHere are your incomplete tasks:\n\n" + "\n".join(task_list) + (f"\n\n(Showing 7 of {incomplete_tasks.count()} tasks)" if incomplete_tasks.count() > 7 else "")
    except Exception as e:
        logger.error(f"Error completing task: {str(e)}")
        return False, f"I encountered a problem while trying to mark the task as completed. Could you try again or check if the task exists?"

# Function to mark overdue tasks as completed
def mark_overdue_tasks_complete(user, all_overdue=False):
    """
    Mark user's overdue tasks as completed.
    Returns tuple of (success_bool, message, count)
    """
    try:
        # Get overdue tasks
        overdue_query = models.Q(due_date__lt=timezone.now()) & ~models.Q(status='completed')
        overdue_tasks = (Task.objects.filter(owner=user).filter(overdue_query) | 
                        Task.objects.filter(assignees=user).filter(overdue_query)).distinct()
        
        count = overdue_tasks.count()
        
        if count == 0:
            return False, "Good news! You don't have any overdue tasks to complete.", 0
        
        if not all_overdue and count > 1:
            # If multiple overdue tasks and not explicitly marking all as complete
            task_list = [f"• {task.title}" for task in overdue_tasks[:5]]
            additional = f" and {count - 5} more" if count > 5 else ""
            return False, f"You have {count} overdue tasks. Would you like me to mark them all as completed? Just say 'mark all overdue tasks as completed' or specify which task to complete:\n\n" + "\n".join(task_list[:5]) + additional, count
        
        # Mark all as completed
        for task in overdue_tasks:
            task.status = 'completed'
            if hasattr(task, 'completed_at'):
                task.completed_at = timezone.now()
            task.save()
        
        if count == 1:
            return True, f"✅ Success! Your overdue task has been marked as completed.", count
        elif count <= 3:
            return True, f"✅ Success! All {count} of your overdue tasks have been marked as completed.", count
        else:
            return True, f"✅ Well done! All {count} of your overdue tasks have been marked as completed. That's quite an achievement!", count
    except Exception as e:
        logger.error(f"Error completing overdue tasks: {str(e)}")
        return False, f"I encountered a problem while trying to mark your overdue tasks as completed. Please try again in a moment.", 0

# Update the greeting handler 
def get_greeting_response():
    """Get a varied greeting response based on time of day in Melbourne"""
    # Get current time in Melbourne
    melbourne_now = timezone.now().astimezone(melbourne_timezone)
    current_hour = melbourne_now.hour
    
    # Determine greeting time period
    if 5 <= current_hour < 12:
        greeting_time = "morning"
    elif 12 <= current_hour < 18:
        greeting_time = "afternoon"
    elif 18 <= current_hour < 22:
        greeting_time = "evening"
    else:
        greeting_time = "night"
    
    # Get base greeting
    base_greeting = custom_responses["greeting_time"][greeting_time]
    
    # Add variations for each time period
    morning_variations = [
        "Good morning! ☀️ Ready to plan your day? I'm here to help you stay on top of your tasks.",
        "Rise and shine! ☀️ Hope you're having a great morning. What can I help you with today?",
        "Morning! Ready to tackle today's tasks?",
        "Good morning! Let's make today productive."
    ]
    
    afternoon_variations = [
        "Good afternoon! 🌤️ How's your day going? I'm here to help you manage your tasks and projects.",
        "Afternoon! How's your day shaping up? Need any help with your tasks?",
        "Good afternoon! The day is still young - what would you like to accomplish?",
        "Hi there! Hope your afternoon is going well. How can I assist with your tasks today?"
    ]
    
    evening_variations = [
        "Good evening! 🌙 Let's review what you've accomplished today and plan for tomorrow.",
        "Evening! How was your day? Let me help you wrap things up or plan for tomorrow.",
        "Good evening! Time to review today's achievements. How can I help?",
        "Hi there! Hope you had a productive day. Need help organizing your evening?"
    ]
    
    night_variations = [
        "Still working? 🌠 I'm here to help you wrap up for the day or plan for tomorrow.",
        "Burning the midnight oil? I'm here to help you organize your tasks.",
        "Working late? Let's make sure your tasks are organized for tomorrow.",
        "Good evening! Getting some late work done? I'm here to help you manage your tasks."
    ]
    
    # Select appropriate variation based on time
    if greeting_time == "morning":
        greeting_response = random.choice(morning_variations)
    elif greeting_time == "afternoon":
        greeting_response = random.choice(afternoon_variations)
    elif greeting_time == "evening":
        greeting_response = random.choice(evening_variations)
    else:
        greeting_response = random.choice(night_variations)
    
    return greeting_response

# Add a function to handle "how are you" type responses
def get_how_are_you_response():
    """Return a varied response to 'how are you' type questions"""
    responses = [
        "I'm doing great, thanks for asking! Ready to help you with your tasks. What can I do for you today?",
        "I'm excellent! Always happy to help organize your day. What do you need assistance with?",
        "I'm functioning perfectly! How can I help you manage your tasks today?",
        "All systems operational and ready to assist! What tasks are you focusing on today?",
        "I'm well and ready to help! What would you like to accomplish today?",
        "Doing great and ready to assist with your task management. What can I help you with?"
    ]
    return random.choice(responses)

# Also add more casual greeting variations to the greeting response patterns
def get_casual_greeting_response():
    """Return a casual greeting response for informal greetings like 'hey', 'yo', etc."""
    casual_responses = [
        "Hey there! Ready to tackle some tasks?",
        "Hi! What can I help you with today?",
        "Hello! Ready when you are. What's on your task list?",
        "Hey! Great to see you. Need help with your tasks?",
        "Hi there! What's on your mind today?",
        "Greetings! How can I assist with your tasks?",
        "Hey! Ready to be productive today?",
        "Hello! What task management help do you need?"
    ]
    return random.choice(casual_responses)
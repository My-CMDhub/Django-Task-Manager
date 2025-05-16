import os
import json
import re
import httpx
from .utils import get_user_tasks, format_task_list
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
        "morning": "Good morning! Need help looking up information about your tasks?",
        "afternoon": "Good afternoon! How can I help with task information?",
        "evening": "Good evening! Let's review your tasks for today.",
        "night": "Working late? Let me help you find information about your tasks."
    },
    
    # Farewells
    "farewell": "Goodbye! Have a productive day!",
    "farewell_alt": "Take care! Your tasks will be waiting for you when you return.",
    
    # Identity/Introduction
    "chatbot-name": "I'm your Task Assistant, ready to help you find information about your tasks.",
    "purpose": "I'm here to help you view your tasks, check statistics, and stay organized!",
    
    # Tasks related
    "task_info": "Here's the information about your tasks that you requested.",
    "task_not_found": "I couldn't find that task. Could you provide more details?",
    
    # Error Handling
    "error": "I apologize, but I'm having trouble processing your request right now. Please try again.",
    "api_error": "I'm currently experiencing some technical difficulties. Please try again in a moment.",
    "invalid_input": "I couldn't understand that input. Could you please rephrase it?",
    "empty_input": "Please type a message before sending.",
    
    # Automation rejection responses
    "creation_not_supported": "I'm sorry, I can only provide information about your existing tasks and projects. To create a new task or project, please use the main application interface.",
    "update_not_supported": "I apologize, but I can only view information. To update tasks or projects, please use the main application interface.",
    "delete_not_supported": "I can't delete tasks or projects. Please use the main application interface for these actions.",
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
        processed_message = user_message.strip().lower()
        
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
        
        # Check for task completion requests
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
            r"(?:complete|finish) (?:all|my) overdue (?:tasks)?"
        ]
        
        # Check if this is about completing all overdue tasks
        if re.search(r"(?:mark|complete|finish) (?:all|my) overdue", processed_message) or re.search(r"(?:mark|complete|finish) all (?:my )?(?:tasks|overdue tasks)", processed_message):
            success, message, count = mark_overdue_tasks_complete(user, all_overdue=True)
            return message
        
        # Check for general "mark task complete" request without specifying which task
        if re.search(r"mark tasks? (?:as )?(?:complete|completed|done|finished)$", processed_message) or re.search(r"complete tasks?$", processed_message) or re.search(r"finish tasks?$", processed_message):
            # No specific task mentioned, ask user which task
            # First, get incomplete tasks to show user options
            incomplete_tasks = (Task.objects.filter(owner=user) | Task.objects.filter(assignees=user)).filter(~models.Q(status='completed')).distinct()
            
            if incomplete_tasks.count() == 0:
                return "You don't have any incomplete tasks to mark as completed."
            elif incomplete_tasks.count() == 1:
                # Only one task, let's complete it
                task = incomplete_tasks.first()
                success, message = mark_task_complete(user, task_id=task.id)
                return message
            else:
                # Multiple tasks, show options
                task_list = [f"• {task.title}" for task in incomplete_tasks[:7]]
                return f"Which task would you like to mark as completed? Please specify by saying 'mark [task name] as completed'. Here are your incomplete tasks:\n\n" + "\n".join(task_list) + (f"\n\n(Showing 7 of {incomplete_tasks.count()} tasks)" if incomplete_tasks.count() > 7 else "")
        
        # Check for specific task completion request
        for pattern in completion_patterns:
            match = re.search(pattern, processed_message)
            if match and match.groups() and match.group(1) and match.group(1).strip():
                task_title = match.group(1).strip()
                success, message = mark_task_complete(user, task_title=task_title)
                return message
        
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
                    return f"You only have one task: '{task.title}'. To delete it, please say 'delete task {task.title}'."
                else:
                    # Multiple tasks, show options
                    task_list = [f"• {task.title}" for task in tasks[:7]]
                    return f"Which task would you like to delete? Please specify by saying 'delete [task name]'. Here are your tasks:\n\n" + "\n".join(task_list) + (f"\n\n(Showing 7 of {tasks.count()} tasks)" if tasks.count() > 7 else "")
        
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
                    return f"You have one project: '{project.name}'. To delete it, please say 'delete project {project.name}'."
                else:
                    # Multiple projects, show options
                    project_list = [f"• {project.name}" for project in projects[:7]]
                    return f"Which project would you like to delete? Please specify by saying 'delete [project name]'. Here are your projects:\n\n" + "\n".join(project_list) + (f"\n\n(Showing 7 of {projects.count()} projects)" if projects.count() > 7 else "")
        
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
                response = "📊 **Your Task Manager Dashboard**\n\n"
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
        
        # For other inquiries, use the conversational AI but with a more structured system prompt
        try:
            system_message = {
                "role": "system",
                "content": """You are a helpful task management information assistant. You can only provide information about existing tasks and projects, not create, update, or delete them.

I can help with information about tasks and projects, including:
1. Providing statistics about tasks and projects
2. Showing lists of tasks and projects
3. Answering questions about task management

Importantly:
- Always start your response with "Based on your request, here's what I can tell you:"
- For creating, updating or deleting tasks/projects, politely explain you can only provide information but not perform actions.
- Keep responses concise, professional, and helpful.
- If you don't know the answer to something specific, suggest what kinds of information about tasks you CAN provide.
- Never make up information not available in the user's data.
- Instead of giving a generic answer, suggest specific task-related information that could be requested.
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
                "max_tokens": 300,
                "temperature": 0.5,
            }
            
            try:
                with httpx.Client(timeout=30.0) as client: # Added timeout
                    api_response = client.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload)
                
                api_response.raise_for_status() # Will raise an exception for 4XX/5XX_STATUS_CODES status codes
                
                response_data = api_response.json()
                bot_response = response_data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
                
                if not bot_response:
                    logger.error(f"Mistral API returned empty content. Response: {response_data}")
                    return "I received an empty response from the AI. Please try again."
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
        if task_id:
            # Try to find the exact task by ID
            task = Task.objects.filter(
                models.Q(assignees=user) | models.Q(owner=user),
                id=task_id
            ).first()
            
            if task:
                task.status = 'completed'
                if hasattr(task, 'completed_at'):
                    task.completed_at = timezone.now()
                task.save()
                return True, f"✅ Task '{task.title}' has been marked as completed."
            else:
                return False, f"Task with ID '{task_id}' not found or you don't have permission to modify it."
        
        elif task_title:
            # Try to find tasks containing this title text
            matching_tasks = Task.objects.filter(
                models.Q(assignees=user) | models.Q(owner=user)
            ).filter(
                models.Q(title__icontains=task_title)
            ).exclude(status='completed')
            
            if matching_tasks.count() == 0:
                return False, f"No incomplete tasks found containing '{task_title}' in the title."
            elif matching_tasks.count() == 1:
                # Only one match, let's complete it
                task = matching_tasks.first()
                task.status = 'completed'
                if hasattr(task, 'completed_at'):
                    task.completed_at = timezone.now()
                task.save()
                return True, f"✅ Task '{task.title}' has been marked as completed."
            else:
                # Multiple matches, provide a list
                task_list = [f"• {task.title}" for task in matching_tasks[:5]]
                additional = f" and {matching_tasks.count() - 5} more" if matching_tasks.count() > 5 else ""
                return False, f"I found {matching_tasks.count()} tasks containing '{task_title}'. Please be more specific or use the exact task name:\n\n" + "\n".join(task_list[:5]) + additional
        else:
            return False, "No task title or ID provided."
    except Exception as e:
        logger.error(f"Error completing task: {str(e)}")
        return False, f"An error occurred while trying to mark the task as completed. Please try again."

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
            return False, "You don't have any overdue tasks to complete.", 0
        
        if not all_overdue and count > 1:
            # If multiple overdue tasks and not explicitly marking all as complete
            task_list = [f"• {task.title}" for task in overdue_tasks[:5]]
            additional = f" and {count - 5} more" if count > 5 else ""
            return False, f"You have {count} overdue tasks. To mark them all as completed, please say 'mark all overdue tasks as completed' or specify which task to complete:\n\n" + "\n".join(task_list[:5]) + additional, count
        
        # Mark all as completed
        for task in overdue_tasks:
            task.status = 'completed'
            if hasattr(task, 'completed_at'):
                task.completed_at = timezone.now()
            task.save()
        
        return True, f"✅ Success! {count} overdue {'task has' if count == 1 else 'tasks have'} been marked as completed.", count
    except Exception as e:
        logger.error(f"Error completing overdue tasks: {str(e)}")
        return False, f"An error occurred while trying to mark overdue tasks as completed. Please try again.", 0
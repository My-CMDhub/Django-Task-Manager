import re
import datetime
from dateutil import parser
from django.utils import timezone
from django.db import models
import logging
import time
from django.db.models import Q
from tasks.models import Task, Project

logger = logging.getLogger(__name__)

def extract_task_info(message):
    """
    Extract task information from a user's message using pattern matching
    """
    # Check for common task creation patterns
    task_patterns = [
        r'add task[s]?\s*:?\s*(.+)',
        r'create task[s]?\s*:?\s*(.+)',
        r'new task[s]?\s*:?\s*(.+)',
        r'remind me to\s*(.+)',
    ]
    
    task_content = None
    for pattern in task_patterns:
        match = re.search(pattern, message.lower())
        if match:
            task_content = match.group(1).strip()
            break
    
    if not task_content:
        return None
    
    # Now extract details from the content
    task_info = {
        'title': task_content,
        'description': '',
        'due_date': None,
        'priority': 'medium',
    }
    
    # Extract due date if present
    date_patterns = [
        r'by\s+(.+?)(?:\s+at\s+|$)',
        r'due\s+(.+?)(?:\s+at\s+|$)', 
        r'on\s+(.+?)(?:\s+at\s+|$)',
        r'for\s+(.+?)(?:\s+at\s+|$)',
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, task_content)
        if match:
            date_str = match.group(1).strip()
            try:
                due_date = parser.parse(date_str, fuzzy=True)
                # If only date is provided (no time), set default time to end of day
                if due_date.hour == 0 and due_date.minute == 0 and due_date.second == 0:
                    due_date = due_date.replace(hour=23, minute=59, second=59)
                
                task_info['due_date'] = due_date
                # Remove date part from title
                task_info['title'] = re.sub(pattern, '', task_info['title']).strip()
                break
            except ValueError:
                pass
    
    # Check for priority indicators
    priority_mapping = {
        'high': ['urgent', 'important', 'critical', 'high priority', 'asap'],
        'medium': ['medium priority', 'normal priority'],
        'low': ['low priority', 'whenever', 'not urgent']
    }
    
    for priority, keywords in priority_mapping.items():
        for keyword in keywords:
            if keyword in task_content.lower():
                task_info['priority'] = priority
                # Remove priority keyword from title
                task_info['title'] = task_info['title'].replace(keyword, '').strip()
                break
    
    # If title contains more than 10 words, extract description
    title_words = task_info['title'].split()
    if len(title_words) > 10:
        task_info['title'] = ' '.join(title_words[:10])
        task_info['description'] = ' '.join(title_words[10:])
    
    return task_info

def create_task(user, task_info):
    """
    Create a task in the database and return (task_id, response_message)
    """
    from tasks.models import Task
    # Validate required fields
    title = task_info.get('title', '').strip()
    if not title:
        return None, "I need a task title to create your task. Please provide a title."
    priority = task_info.get('priority', 'medium')
    try:
        task = Task.objects.create(
            owner=user,
            title=title,
            description=task_info.get('description', ''),
            due_date=task_info.get('due_date'),
            priority=priority,
            status='todo'
        )
        task.assignees.add(user)
        from tasks.models import TaskActivity
        TaskActivity.objects.create(
            task=task,
            activity_type='create',
            user=user,
            description=f"Task '{task.title}' created via chatbot"
        )
        # Format a professional, smooth confirmation
        summary = format_task_creation_response(task)
        return task.id, summary
    except Exception as e:
        return None, f"Sorry, I couldn't create the task due to an error: {str(e)}"

def format_task_creation_response(task):
    """
    Return a professional, smooth summary of the created task for the bot response.
    """
    due = f"Due: {task.due_date.strftime('%b %d, %Y %I:%M %p')}" if task.due_date else "No due date set"
    return (
        f"✅ Task created successfully!\n"
        f"Title: {task.title}\n"
        f"Priority: {task.get_priority_display() if hasattr(task, 'get_priority_display') else task.priority.capitalize()}\n"
        f"{due}"
    )

def get_user_tasks(user, status=None, limit=5):
    """
    Get tasks for a user with optional filtering by status
    """
    from tasks.models import Task
    
    tasks = Task.objects.filter(assignees=user)
    
    if status:
        tasks = tasks.filter(status=status)
    
    # Order by due date (if set) with null dates last
    tasks = tasks.order_by(
        models.F('due_date').asc(nulls_last=True),
        '-priority',
        'created_at'
    )
    
    return tasks[:limit]

def format_task_list(tasks):
    """
    Format a list of tasks for display in the chatbot
    """
    if not tasks:
        return "No tasks found."
    
    result = []
    for i, task in enumerate(tasks, 1):
        due_info = f", due {task.due_date.strftime('%b %d, %Y')}" if task.due_date else ""
        priority_info = f", {task.priority} priority"
        result.append(f"{i}. {task.title}{due_info}{priority_info}")
    
    return "\n".join(result)

def process_context_with_query(conversation_context, user_message):
    """
    Process the conversation context with the user's query to understand
    context-based references.
    
    Args:
        conversation_context (list): List of recent messages with role and content
        user_message (str): Current user message
        
    Returns:
        tuple: (processed_message, context_info) 
               - processed_message is the message with context applied if needed
               - context_info is a dict with additional context information
    """
    # Initialize context info dictionary
    context_info = {
        'referenced_tasks': [],
        'referenced_projects': [],
        'referencing_previous': False,
        'action_context': None
    }
    
    # Check for reference indicators
    referencing_indicators = ['it', 'this', 'that', 'these', 'those', 'the task', 'the project', 
                             'this task', 'that task', 'this project', 'that project',
                             'first', 'second', 'third', 'last one']
    
    for indicator in referencing_indicators:
        if indicator in user_message.lower():
            context_info['referencing_previous'] = True
            break
    
    # Extract task/project names from previous messages
    if context_info['referencing_previous']:
        for message in reversed(conversation_context):
            if message['role'] == 'assistant':
                # Extract task names from bullet points
                bullet_items = re.findall(r'•\s+([^•\n]+)', message['content'])
                for item in bullet_items:
                    # Clean up the task name
                    task_name = re.sub(r'\(.*?\)', '', item).strip()
                    task_name = re.sub(r'\[.*?\]', '', task_name).strip()
                    task_name = re.sub(r'-\s*Status:.*$', '', task_name).strip()
                    context_info['referenced_tasks'].append(task_name)
                
                # Look for task names in regular text
                task_mentions = re.findall(r"task ['\"]([^'\"]+)['\"]", message['content'])
                context_info['referenced_tasks'].extend(task_mentions)
                
                # Look for project mentions
                project_mentions = re.findall(r"project ['\"]([^'\"]+)['\"]", message['content'])
                context_info['referenced_projects'].extend(project_mentions)
    
    # Determine action context
    if 'mark' in user_message.lower() or 'complete' in user_message.lower() or 'done' in user_message.lower() or 'finish' in user_message.lower():
        context_info['action_context'] = 'complete'
    elif 'delete' in user_message.lower() or 'remove' in user_message.lower():
        context_info['action_context'] = 'delete'
    
    return (user_message, context_info) 
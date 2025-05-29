import re
import datetime
from dateutil import parser
from django.utils import timezone
from django.db import models

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
    Create a task in the database
    """
    # Import here to avoid circular imports
    from tasks.models import Task
    
    # Default priority if not specified
    priority = task_info.get('priority', 'medium')
    
    # Create the task
    task = Task.objects.create(
        owner=user,
        title=task_info['title'],
        description=task_info.get('description', ''),
        due_date=task_info.get('due_date'),
        priority=priority,
        status='todo'
    )
    
    # Add the user as an assignee
    task.assignees.add(user)
    
    # Log the activity
    from tasks.models import TaskActivity
    TaskActivity.objects.create(
        task=task,
        activity_type='create',
        user=user,
        description=f"Task '{task.title}' created via chatbot"
    )
    
    return task.id

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
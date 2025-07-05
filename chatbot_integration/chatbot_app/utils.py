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

def get_user_context_data(user):
    """
    Retrieve all relevant tasks and projects for the user, format concisely for prompt injection.
    Returns a dictionary with 'tasks', 'projects', and 'summary'.
    """
    from tasks.models import Task, Project
    from django.utils import timezone
    import datetime

    # Get all tasks (owned or assigned)
    tasks_qs = (Task.objects.filter(owner=user) | Task.objects.filter(assignees=user)).distinct()
    tasks = []
    for t in tasks_qs:
        tasks.append({
            'id': str(t.id),
            'title': t.title,
            'status': t.status,
            'due_date': t.due_date.strftime('%Y-%m-%d') if t.due_date else None,
            'priority': getattr(t, 'priority', None),
            'project': t.project.name if hasattr(t, 'project') and t.project else None,
        })

    # Get all projects (where user is a member)
    projects_qs = Project.objects.filter(members=user).distinct()
    projects = []
    for p in projects_qs:
        project_tasks = Task.objects.filter(project=p)
        completed_count = project_tasks.filter(status='completed').count()
        projects.append({
            'id': str(p.id),
            'name': p.name,
            'status': getattr(p, 'status', None),
            'created_at': p.created_at.strftime('%Y-%m-%d') if hasattr(p, 'created_at') and p.created_at else None,
            'task_count': project_tasks.count(),
            'completed_task_count': completed_count,
        })

    # Summary statistics
    now = timezone.now()
    overdue_count = tasks_qs.filter(due_date__lt=now).exclude(status='completed').count()
    completed_count = tasks_qs.filter(status='completed').count()
    pending_count = tasks_qs.exclude(status='completed').count()
    total_tasks = tasks_qs.count()
    total_projects = projects_qs.count()

    summary = {
        'total_tasks': total_tasks,
        'completed_tasks': completed_count,
        'pending_tasks': pending_count,
        'overdue_tasks': overdue_count,
        'total_projects': total_projects,
    }

    return {
        'tasks': tasks,
        'projects': projects,
        'summary': summary,
    } 
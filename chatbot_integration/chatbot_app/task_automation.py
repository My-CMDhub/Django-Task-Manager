import re
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q, Count
from tasks.models import Task, Project, TaskActivity
from .models import Conversation, Message
import logging

logger = logging.getLogger(__name__)

# Regex patterns for task creation
task_patterns = [
    r'create\s+task[s]?',
    r'add\s+task[s]?', 
    r'new\s+task[s]?',
    r'make\s+task[s]?',
    r'set\s+up\s+task[s]?',
    r'let\'s\s+create\s+a\s+task',
    r'let\'s\s+add\s+a\s+task',
    r'i\s+want\s+to\s+create\s+a\s+task',
    r'i\s+need\s+to\s+add\s+a\s+task',
    r'could\s+you\s+create\s+a\s+task',
    r'please\s+create\s+a\s+task',
    r'please\s+add\s+a\s+task'
]

# Regex patterns for project creation
project_patterns = [
    r'create\s+project[s]?',
    r'add\s+project[s]?',
    r'new\s+project[s]?',
    r'make\s+project[s]?',
    r'set\s+up\s+project[s]?',
    r'let\'s\s+create\s+a\s+project',
    r'let\'s\s+add\s+a\s+project',
    r'i\s+want\s+to\s+create\s+a\s+project',
    r'i\s+need\s+to\s+add\s+a\s+project',
    r'could\s+you\s+create\s+a\s+project',
    r'please\s+create\s+a\s+project',
    r'please\s+add\s+a\s+project'
]

# Regex patterns for statistics requests
task_stats_patterns = [
    r'how\s+many\s+tasks',
    r'my\s+tasks\s+count',
    r'task\s+statistics',
    r'task\s+stats',
    r'show\s+my\s+tasks',
    r'list\s+my\s+tasks',
    r'task\s+status',
    r'task\s+summary',
    r'my\s+todo\s+list',
    r'my\s+task\s+list'
]

project_stats_patterns = [
    r'how\s+many\s+projects',
    r'my\s+projects\s+count',
    r'project\s+statistics',
    r'project\s+stats',
    r'show\s+my\s+projects',
    r'list\s+my\s+projects',
    r'project\s+status',
    r'project\s+summary'
]

general_stats_patterns = [
    r'statistics',
    r'stats',
    r'dashboard',
    r'overview',
    r'summary',
    r'my\s+progress',
    r'productivity\s+report',
    r'show\s+me\s+my\s+data',
    r'how\s+am\s+i\s+doing'
]

def check_task_statistics_request(message):
    """Check if the message is asking for task statistics."""
    message = message.lower().strip()
    return any(re.search(pattern, message) for pattern in task_stats_patterns)

def check_project_statistics_request(message):
    """Check if the message is asking for project statistics."""
    message = message.lower().strip()
    return any(re.search(pattern, message) for pattern in project_stats_patterns)

def check_general_statistics_request(message):
    """Check if the message is asking for general statistics."""
    message = message.lower().strip()
    return any(re.search(pattern, message) for pattern in general_stats_patterns)

def get_user_task_count(user):
    """Get count of user's tasks by status."""
    now = timezone.now()
    
    # Get all tasks for the user
    user_tasks = Task.objects.filter(owner=user)
    
    # Get counts by status
    total = user_tasks.count()
    todo = user_tasks.filter(status='todo').count()
    in_progress = user_tasks.filter(status='in_progress').count()
    completed = user_tasks.filter(status='completed').count()
    overdue = user_tasks.filter(
        Q(status__in=['todo', 'in_progress']),
        Q(due_date__lt=now)
    ).count()
    
    return {
        'total': total,
        'todo': todo,
        'in_progress': in_progress,
        'completed': completed,
        'overdue': overdue
    }

def get_user_project_count(user):
    """Get count of user's projects by status."""
    # Get all projects for the user
    user_projects = Project.objects.filter(owner=user)
    
    # Get counts by status
    total = user_projects.count()
    active = user_projects.filter(is_archived=False).count()
    archived = user_projects.filter(is_archived=True).count()
    
    return {
        'total': total,
        'active': active,
        'archived': archived
    }

def get_user_statistics(user):
    """Get comprehensive statistics for the user."""
    task_counts = get_user_task_count(user)
    project_counts = get_user_project_count(user)
    
    # Create a formatted response
    response = "📊 **Your Nexus Statistics**\n\n"
    
    # Task statistics
    response += "**Tasks:**\n"
    response += f"• Total tasks: {task_counts['total']}\n"
    response += f"• To Do: {task_counts['todo']}\n"
    response += f"• In Progress: {task_counts['in_progress']}\n"
    response += f"• Completed: {task_counts['completed']}\n"
    if task_counts['overdue'] > 0:
        response += f"• Overdue: {task_counts['overdue']}\n"
    
    # Project statistics
    response += "\n**Projects:**\n"
    response += f"• Total projects: {project_counts['total']}\n"
    response += f"• Active projects: {project_counts['active']}\n"
    if project_counts['archived'] > 0:
        response += f"• Archived projects: {project_counts['archived']}\n"
    
    # Task distribution by project
    if project_counts['total'] > 0 and task_counts['total'] > 0:
        response += "\n**Tasks by Project:**\n"
        projects_with_tasks = Project.objects.filter(
            owner=user,
            task__isnull=False
        ).annotate(task_count=Count('task')).order_by('-task_count')[:5]
        
        for project in projects_with_tasks:
            response += f"• {project.name}: {project.task_count} tasks\n"
    
    return response

def extract_task_info(message):
    """Extract task information from a user's message."""
    message = message.lower().strip()
    
    # Check if message contains task creation pattern
    contains_task_pattern = any(re.search(pattern, message) for pattern in task_patterns)
    
    if not contains_task_pattern:
        return None
    
    # Check if the message only contains the task creation pattern without content
    simple_task_request = all(
        re.match(f"^{pattern}$", message) or 
        re.match(f"^{pattern}\s*[.!?]?$", message)
        for pattern in task_patterns if re.search(pattern, message)
    )
    
    if simple_task_request:
        return {
            'needs_more_info': True,
            'message': "I'd be happy to create a task for you. Please provide more details like the task title, due date (if any), and priority (if applicable)."
        }
    
    # Extract title
    title_patterns = [
        r'(?:create|add|new|make|set up)\s+task[s]?(?:\s*:)?\s*(.+?)(?:\s+(?:by|due|on|desc|description|proj|project|in|priority)|$)',
        r'(?:let\'s|i want to|i need to|could you|please)(?:\s+(?:create|add))\s+a\s+task(?:\s*:)?\s*(.+?)(?:\s+(?:by|due|on|desc|description|proj|project|in|priority)|$)'
    ]
    
    title = None
    for pattern in title_patterns:
        match = re.search(pattern, message)
        if match:
            title = match.group(1).strip()
            if title:
                break
    
    if not title:
        # If no title found with patterns, use text after task creation command
        for pattern in task_patterns:
            match = re.search(pattern + r'\s*(?::)?\s*(.+)', message)
            if match:
                title = match.group(1).strip()
                break
    
    # If still no title found, look for the first sentence after a task pattern
    if not title:
        for pattern in task_patterns:
            match_pos = re.search(pattern, message)
            if match_pos:
                start_pos = match_pos.end()
                text_after = message[start_pos:].strip()
                if text_after:
                    # Use the text until the next sentence or end of string
                    sentence_end = re.search(r'[.!?]', text_after)
                    if sentence_end:
                        title = text_after[:sentence_end.start()].strip()
                    else:
                        title = text_after.strip()
                    break
    
    if not title:
        return {
            'needs_more_info': True,
            'message': "I'd be happy to create a task for you, but I need a title for the task. Please provide a title and any other details like due date or priority."
        }
    
    # Extract description
    description = None
    description_patterns = [
        r'desc(?:ription)?(?:\s*:)?\s*(.+?)(?:\s+(?:by|due|on|proj|project|in|priority)|$)',
        r'description\s+is\s+(.+?)(?:\s+(?:by|due|on|proj|project|in|priority)|$)',
        r'(?:with|that|which|it)?\s+(?:is about|is|has details?)\s+(.+?)(?:\s+(?:by|due|on|proj|project|in|priority)|$)'
    ]
    
    for pattern in description_patterns:
        match = re.search(pattern, message)
        if match:
            description = match.group(1).strip()
            if description:
                break
    
    # Extract due date
    due_date = None
    date_patterns = [
        r'by\s+(.+?)(?:\s+(?:desc|description|proj|project|in|priority)|$)',
        r'due\s+(?:date|on)?(?:\s*:)?\s*(.+?)(?:\s+(?:desc|description|proj|project|in|priority)|$)',
        r'on\s+(.+?)(?:\s+(?:desc|description|proj|project|in|priority)|$)'
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, message)
        if match:
            date_text = match.group(1).strip().lower()
            
            # Process common date terms
            if date_text in ['today', 'now']:
                due_date = timezone.now().date()
            elif date_text in ['tomorrow', 'tmrw', 'tmr']:
                due_date = (timezone.now() + timedelta(days=1)).date()
            elif date_text in ['next week', 'next wk']:
                due_date = (timezone.now() + timedelta(days=7)).date()
            elif date_text.startswith(('mon', 'tues', 'wed', 'thur', 'fri', 'sat', 'sun')):
                # Simple day of week handling (would need to be enhanced)
                today = timezone.now().date()
                day_map = {
                    'mon': 0, 'tues': 1, 'wed': 2, 'thur': 3, 'fri': 4, 'sat': 5, 'sun': 6
                }
                
                for day_name, day_number in day_map.items():
                    if date_text.startswith(day_name):
                        days_ahead = (day_number - today.weekday()) % 7
                        if days_ahead == 0:  # Today
                            days_ahead = 7  # Next week's occurrence
                        due_date = today + timedelta(days=days_ahead)
                        break
            else:
                # Try standard date format parsing (would need further refinement)
                try:
                    due_date = datetime.strptime(date_text, '%Y-%m-%d').date()
                except ValueError:
                    try:
                        due_date = datetime.strptime(date_text, '%m/%d/%Y').date()
                    except ValueError:
                        try:
                            due_date = datetime.strptime(date_text, '%d/%m/%Y').date()
                        except ValueError:
                            # Could add more date formats if needed
                            pass
            
            if due_date:
                break
    
    # Extract priority
    priority = None
    if re.search(r'urgent|highest|critical', message):
        priority = 'high'
    elif re.search(r'high\s+priority|important', message):
        priority = 'high'
    elif re.search(r'medium\s+priority|normal\s+priority', message):
        priority = 'medium'
    elif re.search(r'low\s+priority|lowest', message):
        priority = 'low'
    
    # Extract project name
    project = None
    project_patterns = [
        r'(?:in|for|to|under|within)\s+project\s+(.+?)(?:\s+(?:by|due|on|desc|description|priority)|$)',
        r'project(?:\s*:)?\s*(.+?)(?:\s+(?:by|due|on|desc|description|priority)|$)',
        r'in\s+(.+?)(?:\s+(?:project|by|due|on|desc|description|priority)|$)'
    ]
    
    for pattern in project_patterns:
        match = re.search(pattern, message)
        if match:
            project = match.group(1).strip()
            if project:
                break
    
    return {
        'title': title,
        'description': description,
        'due_date': due_date,
        'priority': priority,
        'project': project
    }

def extract_project_info(message):
    """Extract project information from a user's message."""
    message = message.lower().strip()
    
    # Check if message contains project creation pattern
    contains_project_pattern = any(re.search(pattern, message) for pattern in project_patterns)
    
    if not contains_project_pattern:
        return None
    
    # Check if the message only contains the project creation pattern without content
    simple_project_request = all(
        re.match(f"^{pattern}$", message) or 
        re.match(f"^{pattern}\s*[.!?]?$", message)
        for pattern in project_patterns if re.search(pattern, message)
    )
    
    if simple_project_request:
        return {
            'needs_more_info': True,
            'message': "I'd be happy to create a project for you. Please provide a name for the project and an optional description."
        }
    
    # Extract project name
    name_patterns = [
        r'(?:create|add|new|make|set up)\s+project[s]?(?:\s*:)?\s*(.+?)(?:\s+(?:desc|description)|$)',
        r'(?:let\'s|i want to|i need to|could you|please)(?:\s+(?:create|add))\s+a\s+project(?:\s*:)?\s*(.+?)(?:\s+(?:desc|description)|$)'
    ]
    
    name = None
    for pattern in name_patterns:
        match = re.search(pattern, message)
        if match:
            name = match.group(1).strip()
            if name:
                break
    
    if not name:
        # If no name found with patterns, use text after project creation command
        for pattern in project_patterns:
            match = re.search(pattern + r'\s*(?::)?\s*(.+)', message)
            if match:
                name = match.group(1).strip()
                break
    
    # If still no name found, look for the first sentence after a project pattern
    if not name:
        for pattern in project_patterns:
            match_pos = re.search(pattern, message)
            if match_pos:
                start_pos = match_pos.end()
                text_after = message[start_pos:].strip()
                if text_after:
                    # Use the text until the next sentence or end of string
                    sentence_end = re.search(r'[.!?]', text_after)
                    if sentence_end:
                        name = text_after[:sentence_end.start()].strip()
                    else:
                        name = text_after.strip()
                    break
    
    if not name:
        return {
            'needs_more_info': True,
            'message': "I'd be happy to create a project for you, but I need a name for the project. Please provide a name and an optional description."
        }
    
    # Extract description
    description = None
    description_patterns = [
        r'desc(?:ription)?(?:\s*:)?\s*(.+?)(?:\s+|$)',
        r'description\s+is\s+(.+?)(?:\s+|$)',
        r'(?:with|that|which|it)?\s+(?:is about|is|has details?)\s+(.+?)(?:\s+|$)'
    ]
    
    for pattern in description_patterns:
        match = re.search(pattern, message)
        if match:
            description = match.group(1).strip()
            if description:
                break
    
    return {
        'name': name,
        'description': description
    }

def create_task(user, task_info):
    """Create a task from extracted information."""
    try:
        # Check if we need to ask for more information
        if isinstance(task_info, dict) and task_info.get('needs_more_info', False):
            return None, task_info['message']
        
        # Ensure task_info is not None
        if task_info is None:
            return None, "I couldn't extract task information from your message. Please try again with a clearer task description."
        
        title = task_info['title']
        description = task_info.get('description', '')
        due_date = task_info.get('due_date', None)
        priority = task_info.get('priority', 'medium')
        project_name = task_info.get('project', None)
        
        # Map the priority to the Task model's choices
        priority_mapping = {
            'low': 'low',
            'medium': 'medium',
            'high': 'high',
            'urgent': 'high'  # Map 'critical' to 'high' for compatibility
        }
        
        # Default to medium if not found
        mapped_priority = priority_mapping.get(priority.lower(), 'medium')
        
        project = None
        if project_name:
            # Check if the project exists
            try:
                project = Project.objects.get(owner=user, name__iexact=project_name)
            except Project.DoesNotExist:
                # Project doesn't exist, create it
                project = Project.objects.create(
                    owner=user,
                    name=project_name,
                    description=f"Project created via chat for task: {title}"
                )
                
                # Create a task activity for the project
                TaskActivity.objects.create(
                    task=None,
                    activity_type='create',
                    user=user,
                    description=f"Created project '{project_name}' via chatbot"
                )
        
        # Create the task
        task = Task.objects.create(
            owner=user,
            title=title,
            description=description,
            due_date=due_date,
            priority=mapped_priority,
            project=project,
            status='todo'  # Set default status
        )
        
        # Add the current user as an assignee
        task.assignees.add(user)
        
        # Create a task activity
        TaskActivity.objects.create(
            task=task,
            activity_type='create',
            user=user,
            description=f"Created task '{title}' via chatbot"
        )
        
        # Prepare response message
        response = f"✅ Task created successfully!\n\n"
        response += f"**Title:** {title}\n"
        
        if description:
            response += f"**Description:** {description}\n"
        
        if due_date:
            response += f"**Due Date:** {due_date.strftime('%Y-%m-%d')}\n"
        
        response += f"**Priority:** {mapped_priority.capitalize()}\n"
        
        if project:
            response += f"**Project:** {project.name}\n"
        
        response += "\nYou can view and manage this task in your task dashboard."
        
        # Return the UUID as a string instead of an integer
        return str(task.id), response
    
    except Exception as e:
        logger.error(f"Error creating task: {str(e)}")
        return None, f"I'm sorry, there was an error creating your task: {str(e)}. Please try again."

def create_project(user, project_info):
    """Create a project from extracted information."""
    try:
        # Check if we need to ask for more information
        if 'needs_more_info' in project_info and project_info['needs_more_info']:
            return None, project_info['message']
        
        name = project_info['name']
        description = project_info.get('description', '')
        
        # Check if a project with this name already exists
        existing_project = Project.objects.filter(owner=user, name__iexact=name).first()
        if existing_project:
            return existing_project.id, f"A project named '{name}' already exists. You can add tasks to this project."
        
        # Create the project
        project = Project.objects.create(
            owner=user,
            name=name,
            description=description
        )
        
        # Log project creation activity
        TaskActivity.objects.create(
            user=user,
            activity_type='create',
            object_type='project',
            object_id=project.id,
            description=f"Created project '{name}'"
        )
        
        # Prepare response message
        response = f"✅ Project created successfully!\n\n"
        response += f"**Name:** {name}\n"
        
        if description:
            response += f"**Description:** {description}\n"
        
        return project.id, response
    
    except Exception as e:
        logger.error(f"Error creating project: {str(e)}")
        return None, "I'm sorry, there was an error creating your project. Please try again." 
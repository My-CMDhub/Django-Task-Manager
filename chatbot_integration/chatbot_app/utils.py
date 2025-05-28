"""
Utility functions for the enhanced chatbot system.
"""

import logging
from typing import Dict, Any, Optional
from django.db import models
from tasks.models import Task, Project
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)

def get_user_context_data(user, query: str = None) -> str:
    """
    Get comprehensive user context data for AI responses.
    
    Args:
        user: Django User object
        query: Optional query string to focus context
        
    Returns:
        Formatted string containing user's task and project data
    """
    try:
        context_parts = []
        
        # Get user's tasks
        all_tasks = Task.objects.filter(
            models.Q(owner=user) | models.Q(assignees=user)
        ).distinct()
        
        pending_tasks = all_tasks.exclude(status='completed')
        completed_tasks = all_tasks.filter(status='completed')
        
        # Task overview
        context_parts.append(f"TASK OVERVIEW:")
        context_parts.append(f"Total tasks: {all_tasks.count()}")
        context_parts.append(f"Pending tasks: {pending_tasks.count()}")
        context_parts.append(f"Completed tasks: {completed_tasks.count()}")
        
        # Recent tasks
        if pending_tasks.exists():
            context_parts.append(f"\nRECENT PENDING TASKS:")
            for i, task in enumerate(pending_tasks.order_by('-created_at')[:5], 1):
                due_info = f", due {task.due_date.strftime('%Y-%m-%d')}" if task.due_date else ""
                priority_info = f", {task.priority} priority" if task.priority != 'medium' else ""
                context_parts.append(f"{i}. {task.title}{due_info}{priority_info}")
        
        # Overdue tasks
        now = timezone.now()
        overdue_tasks = pending_tasks.filter(due_date__lt=now)
        if overdue_tasks.exists():
            context_parts.append(f"\nOVERDUE TASKS ({overdue_tasks.count()}):")
            for i, task in enumerate(overdue_tasks[:3], 1):
                days_overdue = (now - task.due_date).days
                context_parts.append(f"{i}. {task.title} (overdue by {days_overdue} days)")
        
        # Today's tasks
        today_tasks = pending_tasks.filter(due_date__date=now.date())
        if today_tasks.exists():
            context_parts.append(f"\nTASKS DUE TODAY ({today_tasks.count()}):")
            for i, task in enumerate(today_tasks, 1):
                context_parts.append(f"{i}. {task.title}")
        
        # Recent completed tasks if relevant to query
        if query and any(word in query.lower() for word in ['completed', 'finished', 'done']):
            recent_completed = completed_tasks.order_by('-updated_at')[:3]
            if recent_completed.exists():
                context_parts.append(f"\nRECENTLY COMPLETED TASKS:")
                for i, task in enumerate(recent_completed, 1):
                    context_parts.append(f"{i}. {task.title}")
        
        # Projects
        projects = Project.objects.filter(members=user)
        if projects.exists():
            context_parts.append(f"\nPROJECTS ({projects.count()}):")
            for i, project in enumerate(projects[:5], 1):
                try:
                    project_tasks = Task.objects.filter(project=project)
                    completed_project_tasks = project_tasks.filter(status='completed')
                    progress = f"{completed_project_tasks.count()}/{project_tasks.count()}" if project_tasks.exists() else "0/0"
                    context_parts.append(f"{i}. {project.name} ({progress} tasks)")
                except:
                    context_parts.append(f"{i}. {project.name}")
        
        return "\n".join(context_parts)
        
    except Exception as e:
        logger.error(f"Error generating user context data: {e}")
        return f"USER: {user.username}\nTasks: Unable to retrieve\nProjects: Unable to retrieve"

def get_user_tasks(user, status_filter=None, limit=10):
    """
    Get user's tasks with optional filtering.
    
    Args:
        user: Django User object
        status_filter: Optional status to filter by
        limit: Maximum number of tasks to return
        
    Returns:
        QuerySet of Task objects
    """
    tasks = Task.objects.filter(
        models.Q(owner=user) | models.Q(assignees=user)
    ).distinct()
    
    if status_filter:
        tasks = tasks.filter(status=status_filter)
    
    return tasks.order_by('-created_at')[:limit]

def format_task_list(tasks, include_details=True):
    """
    Format a list of tasks for display.
    
    Args:
        tasks: QuerySet or list of Task objects
        include_details: Whether to include due dates and priorities
        
    Returns:
        Formatted string representation of tasks
    """
    if not tasks:
        return "No tasks found."
    
    formatted_lines = []
    for i, task in enumerate(tasks, 1):
        line = f"{i}. {task.title}"
        
        if include_details:
            details = []
            if task.due_date:
                details.append(f"Due: {task.due_date.strftime('%Y-%m-%d')}")
            if task.priority and task.priority != 'medium':
                details.append(f"Priority: {task.priority}")
            if hasattr(task, 'get_status_display'):
                details.append(f"Status: {task.get_status_display()}")
            
            if details:
                line += f" ({', '.join(details)})"
        
        formatted_lines.append(line)
    
    return "\n".join(formatted_lines)

def process_context_with_query(conversation_context, user_message):
    """
    Process user message with conversation context to resolve references.
    
    Args:
        conversation_context: List of recent conversation messages
        user_message: Current user message
        
    Returns:
        Tuple of (processed_message, context_info)
    """
    # This is a simplified version - the original was quite complex
    # For now, just return the original message and basic context info
    context_info = {
        'referencing_previous': False,
        'referenced_tasks': [],
        'referenced_projects': [],
        'action_context': None
    }
    
    return user_message, context_info

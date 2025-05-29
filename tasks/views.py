from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponseForbidden
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator
from .models import (
    Task, TaskAttachment, TaskReminder, TaskTag, TaskComment, 
    TaskActivity, Project, TimeEntry, CustomField, CustomFieldValue, ShareLink
)
from .forms import (
    TaskForm, TaskAttachmentForm, TaskReminderForm, 
    TaskTagForm, TaskCommentForm, TaskSearchForm,
    ProjectForm, TimeEntryForm
)
from auth_app.models import User
import json
import logging
from django.views.decorators.csrf import csrf_protect, csrf_exempt
from django.core.management import call_command
from django.db import transaction
import io
import uuid
from rest_framework import generics
from .models import Task
from .serializers import TaskSerializer
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.views.decorators.http import require_http_methods

logger = logging.getLogger(__name__)

@login_required
def task_list(request):
    """View to list all tasks for the logged-in user."""
    # Initialize the search form
    form = TaskSearchForm(request.GET)
    
    # Default filter for tasks where user is either owner or assignee
    tasks = Task.objects.filter(
        Q(owner=request.user) | Q(assignees=request.user)
    ).distinct()
    
    # Don't show archived tasks by default
    show_archived = request.GET.get('show_archived') == '1'
    if not show_archived:
        tasks = tasks.filter(is_archived=False)
    
    # Apply filters based on form data
    if form.is_valid():
        # Filter by project
        project = form.cleaned_data.get('project')
        if project:
            tasks = tasks.filter(project=project)
        
        # Filter by status
        status = form.cleaned_data.get('status')
        if status:
            tasks = tasks.filter(status=status)
        
        # Filter by priority
        priority = form.cleaned_data.get('priority')
        if priority:
            tasks = tasks.filter(priority=priority)
        
        # Filter by search term with advanced search options
        search = form.cleaned_data.get('search')
        search_in = form.cleaned_data.get('search_in') or ['title', 'description']
        if search:
            search_query = Q()
            if 'title' in search_in:
                search_query |= Q(title__icontains=search)
            if 'description' in search_in:
                search_query |= Q(description__icontains=search)
            if 'comments' in search_in:
                search_query |= Q(comments__content__icontains=search)
            tasks = tasks.filter(search_query).distinct()
        
        # Filter by due date range
        due_date_filter = form.cleaned_data.get('due_date')
        if due_date_filter:
            today = timezone.now().date()
            if due_date_filter == 'today':
                tasks = tasks.filter(due_date__date=today)
            elif due_date_filter == 'tomorrow':
                tomorrow = today + timezone.timedelta(days=1)
                tasks = tasks.filter(due_date__date=tomorrow)
            elif due_date_filter == 'week':
                end_of_week = today + timezone.timedelta(days=7)
                tasks = tasks.filter(due_date__date__range=[today, end_of_week])
            elif due_date_filter == 'month':
                end_of_month = today + timezone.timedelta(days=30)
                tasks = tasks.filter(due_date__date__range=[today, end_of_month])
            elif due_date_filter == 'overdue':
                tasks = tasks.filter(due_date__lt=timezone.now(), status__in=['todo', 'in_progress'])
            elif due_date_filter == 'none':
                tasks = tasks.filter(due_date__isnull=True)
        
        # Filter by creation date
        created_date_filter = form.cleaned_data.get('created_date')
        if created_date_filter:
            today = timezone.now().date()
            if created_date_filter == 'today':
                tasks = tasks.filter(created_at__date=today)
            elif created_date_filter == 'yesterday':
                yesterday = today - timezone.timedelta(days=1)
                tasks = tasks.filter(created_at__date=yesterday)
            elif created_date_filter == 'week':
                start_of_week = today - timezone.timedelta(days=today.weekday())
                tasks = tasks.filter(created_at__date__gte=start_of_week)
            elif created_date_filter == 'month':
                start_of_month = today.replace(day=1)
                tasks = tasks.filter(created_at__date__gte=start_of_month)
        
        # Filter by assignee
        assignee = form.cleaned_data.get('assignee')
        if assignee:
            tasks = tasks.filter(assignees=assignee)
        
        # Filter by creator
        created_by = form.cleaned_data.get('created_by')
        if created_by:
            tasks = tasks.filter(owner=created_by)
        
        # Filter by tags
        tags = form.cleaned_data.get('tags')
        if tags:
            for tag in tags:
                tasks = tasks.filter(tags=tag)
        
        # Filter by AI-generated
        is_ai_generated = form.cleaned_data.get('is_ai_generated')
        if is_ai_generated:
            tasks = tasks.filter(is_ai_generated=True)
        
        # Filter by has attachments
        has_attachments = form.cleaned_data.get('has_attachments')
        if has_attachments:
            tasks = tasks.filter(attachments__isnull=False).distinct()
        
        # Filter by has comments
        has_comments = form.cleaned_data.get('has_comments')
        if has_comments:
            tasks = tasks.filter(comments__isnull=False).distinct()
        
        # Filter by estimated hours range
        estimated_hours_min = form.cleaned_data.get('estimated_hours_min')
        if estimated_hours_min is not None:
            tasks = tasks.filter(estimated_hours__gte=estimated_hours_min)
        
        estimated_hours_max = form.cleaned_data.get('estimated_hours_max')
        if estimated_hours_max is not None:
            tasks = tasks.filter(estimated_hours__lte=estimated_hours_max)
        
        # Filter by subtask status
        is_subtask = form.cleaned_data.get('is_subtask')
        if is_subtask is not None:
            if is_subtask:
                tasks = tasks.filter(parent_task__isnull=False)
            else:
                tasks = tasks.filter(parent_task__isnull=True)
        
        # Sort results
        sort_by = form.cleaned_data.get('sort_by') or '-created_at'
        tasks = tasks.order_by(sort_by)
    else:
        # Default sorting if form is not valid
        tasks = tasks.order_by('-created_at')
    
    # Get available projects for filtering
    projects = Project.objects.filter(
        Q(owner=request.user) | Q(members=request.user)
    ).filter(is_archived=False).order_by('name')
    
    # Get all task tags for this user
    tags = TaskTag.objects.filter(created_by=request.user).order_by('name')
    
    # Calculate stats before pagination
    # Get all tasks before filtering for stats
    all_tasks = Task.objects.filter(
        Q(owner=request.user) | Q(assignees=request.user)
    ).distinct()
    
    if not show_archived:
        all_tasks = all_tasks.filter(is_archived=False)
    
    total_tasks = all_tasks.count()
    todo_tasks = all_tasks.filter(status='todo')
    in_progress_tasks = all_tasks.filter(status='in_progress')
    completed_tasks = all_tasks.filter(status='completed')
    
    todo_count = todo_tasks.count()
    in_progress_count = in_progress_tasks.count()
    completed_count = completed_tasks.count()
    
    # Calculate overdue tasks
    now = timezone.now()
    overdue_count = all_tasks.filter(
        due_date__lt=now,
        status__in=['todo', 'in_progress']
    ).count()
    
    # Calculate completion percentage
    if total_tasks > 0:
        completion_percentage = (completed_count / total_tasks) * 100
    else:
        completion_percentage = 0
    
    # Get choices for dropdown filters
    status_choices = Task.STATUS_CHOICES
    priority_choices = Task.PRIORITY_CHOICES
    
    # Pagination
    paginator = Paginator(tasks, 10)  # Show 10 tasks per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Preserve filter parameters for pagination links
    query_params = request.GET.copy()
    if 'page' in query_params:
        del query_params['page']
    
    # Kanban columns: filter from the filtered/paginated queryset, not all_tasks
    kanban_todo_tasks = tasks.filter(status='todo')
    kanban_in_progress_tasks = tasks.filter(status='in_progress')
    kanban_completed_tasks = tasks.filter(status='completed')

    # Determine if any advanced filters are active for template JS
    has_advanced_filters = any([
        form.cleaned_data.get('project'),
        form.cleaned_data.get('assignee'),
        form.cleaned_data.get('created_by'),
        form.cleaned_data.get('created_date'),
        form.cleaned_data.get('estimated_hours_min'),
        form.cleaned_data.get('estimated_hours_max'),
        form.cleaned_data.get('tags'),
        form.cleaned_data.get('is_ai_generated'),
        form.cleaned_data.get('has_attachments'),
        form.cleaned_data.get('has_comments'),
        form.cleaned_data.get('is_subtask'),
    ]) if form.is_valid() else False

    context = {
        'tasks': page_obj,
        'form': form,
        'projects': projects,
        'tags': tags,
        'status_choices': status_choices,
        'priority_choices': priority_choices,
        'total_tasks': total_tasks,
        'todo_count': todo_count,
        'in_progress_count': in_progress_count,
        'completed_count': completed_count,
        'overdue_count': overdue_count,
        'completion_percentage': completion_percentage,
        'show_archived': show_archived,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'query_params': query_params.urlencode(),
        # Add Kanban columns for filtered tasks
        'todo_tasks': kanban_todo_tasks,
        'in_progress_tasks': kanban_in_progress_tasks,
        'completed_tasks': kanban_completed_tasks,
        'has_advanced_filters': has_advanced_filters,
    }
    
    return render(request, 'tasks/task_list.html', context)

@login_required
def task_detail(request, task_id):
    """View to display details of a specific task."""
    task = get_object_or_404(
        Task.objects.filter(
            Q(owner=request.user) | Q(assignees=request.user)
        ).distinct(), 
        pk=task_id
    )
    
    # Get task comments
    comments = task.comments.all().order_by('created_at')
    
    # Get task activities
    activities = task.activities.all().order_by('-created_at')[:10]
    
    # Get task attachments
    attachments = task.attachments.all().order_by('-uploaded_at')
    
    # Get task dependencies and dependent tasks
    dependencies = task.dependencies.all()
    dependent_tasks = task.dependent_tasks.all()
    
    # Get task subtasks
    subtasks = task.subtasks.all().order_by('position', '-created_at')
    
    # Get task versions
    versions = task.versions.all().order_by('-version_number')[:5]
    
    # Get time entries
    time_entries = task.time_entries.all().order_by('-start_time')
    
    # Calculate total time spent
    total_time = timezone.timedelta()
    for entry in time_entries:
        if entry.duration:
            total_time += entry.duration
    
    # Get custom field values
    custom_fields = task.custom_field_values.all().select_related('field')
    
    # Forms
    comment_form = TaskCommentForm()
    time_entry_form = TimeEntryForm()
    
    context = {
        'task': task,
        'comments': comments,
        'activities': activities,
        'attachments': attachments,
        'dependencies': dependencies,
        'dependent_tasks': dependent_tasks,
        'subtasks': subtasks,
        'versions': versions,
        'time_entries': time_entries,
        'total_time': total_time,
        'custom_fields': custom_fields,
        'comment_form': comment_form,
        'time_entry_form': time_entry_form,
    }
    return render(request, 'tasks/task_detail.html', context)

@login_required
def task_create(request):
    """View to create a new task."""
    # Pre-fill project if specified in query string
    project_id = request.GET.get('project')
    initial_data = {}
    if project_id:
        try:
            project = Project.objects.get(
                Q(owner=request.user) | Q(members=request.user),
                pk=project_id
            )
            initial_data['project'] = project
        except Project.DoesNotExist:
            pass
    
    # Pre-fill parent task if specified
    parent_id = request.GET.get('parent')
    if parent_id:
        try:
            parent_task = Task.objects.get(
                Q(owner=request.user) | Q(assignees=request.user),
                pk=parent_id
            )
            initial_data['parent_task'] = parent_task
        except Task.DoesNotExist:
            pass
    
    if request.method == 'POST':
        form = TaskForm(request.POST, user=request.user)
        if form.is_valid():
            task = form.save(commit=False)
            task.owner = request.user
            task.save()
            
            # Handle many-to-many relationships after saving
            form.save_m2m()
            
            # Create initial version
            task.create_version(request.user)
            
            # Create activity log
            TaskActivity.objects.create(
                task=task,
                activity_type='create',
                user=request.user,
                description=f'Task "{task.title}" created by {request.user.username}'
            )
            
            messages.success(request, 'Task created successfully!')
            return redirect('tasks:task_detail', task_id=task.id)
    else:
        form = TaskForm(initial=initial_data, user=request.user)
        # Ensure this is treated as a new instance
        if hasattr(form, 'instance'):
            form.instance.id = None
    
    context = {
        'form': form,
        'title': 'Create Task',
        'is_new': True  # Add a flag to indicate this is a new task
    }
    return render(request, 'tasks/task_form.html', context)

@login_required
def task_update(request, task_id):
    """View to update an existing task."""
    task = get_object_or_404(Task, pk=task_id)
    
    # Check permissions - only owner or assignees can edit
    if not (task.owner == request.user or task.assignees.filter(id=request.user.id).exists()):
        return HttpResponseForbidden("You don't have permission to edit this task.")
    
    if request.method == 'POST':
        form = TaskForm(request.POST, instance=task, user=request.user)
        if form.is_valid():
            task = form.save()
            
            # Create a new version
            task.create_version(request.user)
            
            # Create activity log
            TaskActivity.objects.create(
                task=task,
                activity_type='update',
                user=request.user,
                description=f'Task "{task.title}" updated by {request.user.username}'
            )
            
            messages.success(request, 'Task updated successfully!')
            return redirect('tasks:task_detail', task_id=task.id)
    else:
        form = TaskForm(instance=task, user=request.user)
    
    context = {
        'form': form,
        'task': task,
        'title': 'Update Task',
        'is_new': False  # Explicitly mark this as not a new task
    }
    return render(request, 'tasks/task_form.html', context)

@login_required
def task_delete(request, task_id):
    """View to delete a task."""
    task = get_object_or_404(
        Task.objects.filter(owner=request.user).distinct(),
        pk=task_id
    )
    
    if request.method == 'POST':
        task_title = task.title
        task.delete()
        
        messages.success(request, f'Task "{task_title}" deleted successfully!')
        return redirect('tasks:task_list')
    
    context = {
        'task': task
    }
    return render(request, 'tasks/task_confirm_delete.html', context)

@login_required
@require_POST
def task_mark_complete(request, task_id):
    """View to mark a task as complete."""
    task = get_object_or_404(
        Task.objects.filter(Q(owner=request.user) | Q(assignees=request.user)).distinct(), 
        pk=task_id
    )
    
    task.mark_completed()
    
    # Create activity log
    TaskActivity.objects.create(
        task=task,
        activity_type='status_change',
        user=request.user,
        description=f'Task "{task.title}" marked as completed by {request.user.username}'
    )
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'task_id': str(task.id)})
    
    messages.success(request, 'Task marked as complete!')
    return redirect('tasks:task_detail', task_id=task.id)

@login_required
@require_POST
def task_mark_in_progress(request, task_id):
    """View to mark a task as in progress."""
    task = get_object_or_404(
        Task.objects.filter(Q(owner=request.user) | Q(assignees=request.user)).distinct(), 
        pk=task_id
    )
    
    task.mark_in_progress()
    
    # Create activity log
    TaskActivity.objects.create(
        task=task,
        activity_type='status_change',
        user=request.user,
        description=f'Task "{task.title}" marked as in progress by {request.user.username}'
    )
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'task_id': str(task.id)})
    
    messages.success(request, 'Task marked as in progress!')
    return redirect('tasks:task_detail', task_id=task.id)

@login_required
@require_POST
def add_comment(request, task_id):
    """View to add a comment to a task."""
    task = get_object_or_404(
        Task.objects.filter(Q(owner=request.user) | Q(assignees=request.user)).distinct(), 
        pk=task_id
    )
    
    form = TaskCommentForm(request.POST)
    if form.is_valid():
        comment = form.save(commit=False)
        comment.task = task
        comment.user = request.user
        comment.save()
        
        # Create activity log
        TaskActivity.objects.create(
            task=task,
            activity_type='comment_add',
            user=request.user,
            description=f'Comment added by {request.user.username}'
        )
        
        messages.success(request, 'Comment added successfully!')
    else:
        messages.error(request, 'Error adding comment. Please try again.')
    
    return redirect('tasks:task_detail', task_id=task.id)

@login_required
@require_POST
def add_attachment(request, task_id):
    """View to add an attachment to a task."""
    task = get_object_or_404(
        Task.objects.filter(Q(owner=request.user) | Q(assignees=request.user)).distinct(), 
        pk=task_id
    )
    
    if 'file' in request.FILES:
        file = request.FILES['file']
        attachment = TaskAttachment(
            task=task,
            file=file,
            file_name=file.name,
            file_type=file.content_type,
            file_size=file.size,
            uploaded_by=request.user
        )
        attachment.save()
        
        # Create activity log
        TaskActivity.objects.create(
            task=task,
            activity_type='attachment_add',
            user=request.user,
            description=f'Attachment "{file.name}" added by {request.user.username}'
        )
        
        messages.success(request, 'Attachment added successfully!')
    else:
        messages.error(request, 'No file uploaded. Please try again.')
    
    return redirect('tasks:task_detail', task_id=task.id)

@login_required
@require_POST
def bulk_action(request, action):
    """Handle bulk actions on multiple tasks."""
    try:
        # Check if data is coming from JSON or form
        if request.headers.get('Content-Type') == 'application/json':
            # JSON data (for backward compatibility)
            data = json.loads(request.body)
            task_ids_raw = data.get('task_ids', [])
        else:
            # Form data
            task_ids_str = request.POST.get('task_ids', '[]')
            task_ids_raw = json.loads(task_ids_str)
        
        if not task_ids_raw:
            messages.error(request, 'No tasks selected')
            return redirect('tasks:task_list')
        
        # Get tasks that belong to the user (either as owner or assignee)
        tasks = Task.objects.filter(
            id__in=task_ids_raw
        ).filter(
            Q(owner=request.user) | Q(assignees=request.user)
        ).distinct()
        
        if not tasks:
            messages.error(request, 'No valid tasks found')
            return redirect('tasks:task_list')
        
        # Perform the requested action
        if action == 'complete':
            for task in tasks:
                task.mark_completed()
                TaskActivity.objects.create(
                    task=task,
                    activity_type='status_change',
                    user=request.user,
                    description=f'Task marked as completed by {request.user.username} (bulk action)'
                )
            messages.success(request, f'{tasks.count()} task(s) marked as complete')
            
        elif action == 'archive':
            for task in tasks:
                task.status = 'archived'
                task.save()
                TaskActivity.objects.create(
                    task=task,
                    activity_type='status_change',
                    user=request.user,
                    description=f'Task archived by {request.user.username} (bulk action)'
                )
            messages.success(request, f'{tasks.count()} task(s) archived')
            
        elif action == 'delete':
            # Only delete tasks where the user is the owner
            owner_tasks = tasks.filter(owner=request.user)
            count = owner_tasks.count()
            
            if count == 0:
                messages.error(request, 'You can only delete tasks that you own')
                return redirect('tasks:task_list')
                
            for task in owner_tasks:
                TaskActivity.objects.create(
                    task=task,
                    activity_type='delete',
                    user=request.user,
                    description=f'Task "{task.title}" deleted by {request.user.username} (bulk action)'
                )
                task.delete()
                
            messages.success(request, f'{count} task(s) deleted')
            
        else:
            messages.error(request, 'Invalid action')
        
        # For form submissions, redirect back to task list
        if request.headers.get('Content-Type') != 'application/json':
            return redirect('tasks:task_list')
            
        # For API calls, return JSON response
        return JsonResponse({'status': 'success', 'message': f'Action {action} completed successfully'})
        
    except json.JSONDecodeError:
        messages.error(request, 'Invalid task data format')
        return redirect('tasks:task_list')
    except Exception as e:
        logger.error(f"Error in bulk_action: {str(e)}")
        messages.error(request, 'An error occurred while processing your request')
        return redirect('tasks:task_list')

@login_required
def manage_tags(request):
    """Manage user's tags."""
    user_tags = TaskTag.objects.filter(created_by=request.user)
    
    if request.method == 'POST':
        form = TaskTagForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tag created successfully.')
            return redirect('tasks:manage_tags')
    else:
        form = TaskTagForm(user=request.user)
    
    context = {
        'user_tags': user_tags,
        'form': form,
    }
    return render(request, 'tasks/manage_tags.html', context)

@login_required
def delete_tag(request, pk):
    """Delete a tag."""
    tag = get_object_or_404(TaskTag, pk=pk)
    
    # Check if user has permission to delete tag
    if request.user != tag.created_by:
        return HttpResponseForbidden("You don't have permission to delete this tag.")
    
    if request.method == 'POST':
        tag_name = tag.name
        tag.delete()
        messages.success(request, f'Tag "{tag_name}" deleted successfully.')
        return redirect('tasks:manage_tags')
    
    context = {
        'tag': tag,
    }
    return render(request, 'tasks/tag_confirm_delete.html', context)

@login_required
@require_POST
def add_tag_to_task(request, task_pk):
    """Add a tag to a task."""
    task = get_object_or_404(Task, pk=task_pk)
    
    # Check if user has permission to add tag to this task
    if not (request.user == task.owner or request.user in task.assignees.all()):
        return JsonResponse({'error': "You don't have permission to add tags to this task."}, status=403)
    
    try:
        data = json.loads(request.body)
        tag_id = data.get('tag_id')
        tag = get_object_or_404(TaskTag, pk=tag_id)
        
        # Add tag to task
        task.tags.add(tag)
        
        # Create activity log
        TaskActivity.objects.create(
            task=task,
            user=request.user,
            activity_type='tag_added',
            description=f"Tag '{tag.name}' added by {request.user.username}"
        )
        
        return JsonResponse({
            'success': True, 
            'tag': {
                'id': tag.pk,
                'name': tag.name,
                'color': tag.color
            }
        })
    except Exception as e:
        logger.error(f"Error adding tag to task: {str(e)}")
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_POST
def remove_tag_from_task(request, task_pk, tag_pk):
    """Remove a tag from a task."""
    task = get_object_or_404(Task, pk=task_pk)
    tag = get_object_or_404(TaskTag, pk=tag_pk)
    
    # Check if user has permission to remove tag from this task
    if not (request.user == task.owner or request.user in task.assignees.all()):
        return JsonResponse({'error': "You don't have permission to remove tags from this task."}, status=403)
    
    # Remove tag from task
    task.tags.remove(tag)
    
    # Create activity log
    TaskActivity.objects.create(
        task=task,
        user=request.user,
        activity_type='tag_removed',
        description=f"Tag '{tag.name}' removed by {request.user.username}"
    )
    
    return JsonResponse({'success': True})

@login_required
def dashboard(request):
    """Display user's task dashboard with statistics."""
    # Get user's tasks
    user_tasks = Task.objects.filter(
        Q(owner=request.user) | Q(assignees=request.user)
    ).distinct()
    
    # Count tasks by status
    status_counts = {
        'open': user_tasks.filter(status='open').count(),
        'in_progress': user_tasks.filter(status='in_progress').count(),
        'review': user_tasks.filter(status='review').count(),
        'completed': user_tasks.filter(status='completed').count(),
    }
    
    # Get overdue tasks
    overdue_tasks = user_tasks.filter(
        due_date__lt=timezone.now(),
        status__in=['open', 'in_progress']
    ).order_by('due_date')
    
    # Get tasks due today
    today = timezone.now().date()
    tasks_due_today = user_tasks.filter(
        due_date__date=today,
        status__in=['open', 'in_progress']
    ).order_by('due_date')
    
    # Get recently completed tasks
    recently_completed = user_tasks.filter(
        status='completed'
    ).order_by('-updated_at')[:5]
    
    # Get tasks by priority
    priority_counts = {
        'low': user_tasks.filter(priority='low').count(),
        'medium': user_tasks.filter(priority='medium').count(),
        'high': user_tasks.filter(priority='high').count(),
        'urgent': user_tasks.filter(priority='urgent').count(),
    }
    
    context = {
        'status_counts': status_counts,
        'priority_counts': priority_counts,
        'overdue_tasks': overdue_tasks,
        'tasks_due_today': tasks_due_today,
        'recently_completed': recently_completed,
        'total_tasks': user_tasks.count(),
    }
    return render(request, 'tasks/dashboard.html', context)

def is_staff(user):
    return user.is_staff

@login_required
@user_passes_test(is_staff)
def user_list(request):
    """View to display all registered users (for staff only)"""
    users = User.objects.all().order_by('-date_joined')
    return render(request, 'tasks/user_list.html', {'users': users})

@login_required
@user_passes_test(is_staff)
def user_stats(request):
    """API endpoint for user statistics"""
    total_users = User.objects.count()
    active_users = User.objects.filter(is_active=True).count()
    verified_users = User.objects.filter(email_verified=True).count()
    
    return JsonResponse({
        'total_users': total_users,
        'active_users': active_users,
        'verified_users': verified_users,
    })

@login_required
@user_passes_test(is_staff)
@csrf_protect
@transaction.atomic
def sync_users(request):
    """Sync users from Supabase to Django"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
    
    try:
        # Capture command output
        output = io.StringIO()
        call_command('sync_supabase_users', stdout=output)
        
        # Parse output to get counts
        output_text = output.getvalue()
        
        return JsonResponse({
            'status': 'success',
            'message': 'Users synchronized successfully',
            'details': output_text
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
def project_list(request):
    """View to list all projects for the logged-in user."""
    # Get projects where user is owner or member
    projects = Project.objects.filter(
        Q(owner=request.user) | Q(members=request.user)
    ).distinct().order_by('-created_at')
    
    # Filter out archived projects unless specifically requested
    show_archived = request.GET.get('show_archived') == '1'
    if not show_archived:
        projects = projects.filter(is_archived=False)
    
    # Search functionality
    search = request.GET.get('search')
    if search:
        projects = projects.filter(
            Q(name__icontains=search) | 
            Q(description__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(projects, 10)  # Show 10 projects per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'projects': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'show_archived': show_archived,
        'search': search or '',
    }
    return render(request, 'tasks/project_list.html', context)

@login_required
def project_detail(request, project_id):
    """View to display details of a specific project."""
    # Get project if user is owner or member
    project = get_object_or_404(
        Project.objects.filter(
            Q(owner=request.user) | Q(members=request.user)
        ).distinct(), 
        pk=project_id
    )
    
    # Get tasks for this project
    tasks = Task.objects.filter(project=project).order_by('-created_at')
    
    # Calculate project stats
    total_tasks = tasks.count()
    completed_tasks = tasks.filter(status='completed').count()
    completion_rate = 0
    if total_tasks > 0:
        completion_rate = int((completed_tasks / total_tasks) * 100)
    
    # Group tasks by status
    todo_tasks = tasks.filter(status='todo').order_by('position', '-created_at')
    in_progress_tasks = tasks.filter(status='in_progress').order_by('position', '-created_at')
    completed_tasks = tasks.filter(status='completed').order_by('-completed_at')
    
    # Get members
    members = project.members.all()
    
    context = {
        'project': project,
        'todo_tasks': todo_tasks,
        'in_progress_tasks': in_progress_tasks,
        'completed_tasks': completed_tasks,
        'completion_rate': completion_rate,
        'total_tasks': total_tasks,
        'members': members,
        'is_owner': project.owner == request.user,
    }
    return render(request, 'tasks/project_detail.html', context)

@login_required
def project_create(request):
    """View to create a new project."""
    if request.method == 'POST':
        form = ProjectForm(request.POST, user=request.user)
        if form.is_valid():
            project = form.save()
            messages.success(request, f'Project "{project.name}" created successfully!')
            return redirect('tasks:project_detail', project_id=project.id)
    else:
        form = ProjectForm(user=request.user)
    
    context = {
        'form': form,
        'title': 'Create Project'
    }
    return render(request, 'tasks/project_form.html', context)

@login_required
def project_update(request, project_id):
    """View to update an existing project."""
    project = get_object_or_404(Project, pk=project_id, owner=request.user)
    
    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project, user=request.user)
        if form.is_valid():
            project = form.save()
            messages.success(request, f'Project "{project.name}" updated successfully!')
            return redirect('tasks:project_detail', project_id=project.id)
    else:
        form = ProjectForm(instance=project, user=request.user)
    
    context = {
        'form': form,
        'project': project,
        'title': 'Update Project'
    }
    return render(request, 'tasks/project_form.html', context)

@login_required
def project_archive(request, project_id):
    """View to archive a project."""
    project = get_object_or_404(Project, pk=project_id, owner=request.user)
    
    if request.method == 'POST':
        project.is_archived = True
        project.save()
        messages.success(request, f'Project "{project.name}" archived successfully!')
        return redirect('tasks:project_list')
    
    context = {
        'project': project
    }
    return render(request, 'tasks/project_confirm_archive.html', context)

@login_required
def project_unarchive(request, project_id):
    """View to unarchive a project."""
    project = get_object_or_404(Project, pk=project_id, owner=request.user)
    project.is_archived = False
    project.save()
    messages.success(request, f'Project "{project.name}" has been unarchived')
    return redirect('tasks:project_list')

@login_required
def project_delete(request, project_id):
    """View to delete a project."""
    project = get_object_or_404(
        Project.objects.filter(owner=request.user).distinct(),
        pk=project_id
    )
    
    if request.method == 'POST':
        project_name = project.name
        project.delete()
        
        messages.success(request, f'Project "{project_name}" deleted successfully!')
        return redirect('tasks:project_list')
    
    context = {
        'project': project
    }
    return render(request, 'tasks/project_confirm_delete.html', context)

@login_required
@require_POST
def bulk_project_action(request, action):
    """Handle bulk actions on multiple projects."""
    if request.headers.get('Content-Type') != 'application/json':
        return JsonResponse({'status': 'error', 'message': 'Invalid request format'}, status=400)
    
    try:
        data = json.loads(request.body)
        project_ids = data.get('project_ids', [])
        
        if not project_ids:
            return JsonResponse({'status': 'error', 'message': 'No projects selected'}, status=400)
        
        # Get projects that belong to the user (as owner)
        projects = Project.objects.filter(
            id__in=project_ids,
            owner=request.user
        )
        
        if not projects:
            return JsonResponse({'status': 'error', 'message': 'No valid projects found'}, status=404)
        
        # Perform the requested action
        if action == 'archive':
            for project in projects:
                project.is_archived = True
                project.save()
            message = f'{projects.count()} project(s) archived'
            
        elif action == 'unarchive':
            for project in projects:
                project.is_archived = False
                project.save()
            message = f'{projects.count()} project(s) unarchived'
            
        elif action == 'delete':
            count = projects.count()
            projects.delete()
            message = f'{count} project(s) deleted'
            
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid action'}, status=400)
        
        return JsonResponse({'status': 'success', 'message': message})
        
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error in bulk_project_action: {str(e)}")
        return JsonResponse({'status': 'error', 'message': 'An error occurred'}, status=500)

@login_required
@require_POST
def add_time_entry(request, task_id):
    """View to add a time entry to a task."""
    task = get_object_or_404(
        Task.objects.filter(Q(owner=request.user) | Q(assignees=request.user)).distinct(), 
        pk=task_id
    )
    
    form = TimeEntryForm(request.POST, task=task, user=request.user)
    if form.is_valid():
        time_entry = form.save()
        
        # Create activity log
        TaskActivity.objects.create(
            task=task,
            activity_type='time_entry_add',
            user=request.user,
            description=f'Time entry added to "{task.title}" by {request.user.username}'
        )
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'status': 'success', 
                'time_entry_id': str(time_entry.id),
                'duration': str(time_entry.duration) if time_entry.duration else None
            })
        
        messages.success(request, 'Time entry added successfully!')
        return redirect('tasks:task_detail', task_id=task.id)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'error',
            'errors': form.errors.as_json()
        }, status=400)
    
    messages.error(request, 'Error adding time entry. Please check the form.')
    return redirect('tasks:task_detail', task_id=task.id)

@login_required
def view_task_versions(request, task_id):
    """View to display all versions of a task."""
    task = get_object_or_404(
        Task.objects.filter(Q(owner=request.user) | Q(assignees=request.user)).distinct(), 
        pk=task_id
    )
    
    versions = task.versions.all().order_by('-version_number')
    
    context = {
        'task': task,
        'versions': versions,
    }
    return render(request, 'tasks/task_versions.html', context)

@login_required
def view_version_detail(request, task_id, version_number):
    """View to display a specific version of a task."""
    task = get_object_or_404(
        Task.objects.filter(Q(owner=request.user) | Q(assignees=request.user)).distinct(), 
        pk=task_id
    )
    
    version = get_object_or_404(task.versions.all(), version_number=version_number)
    
    context = {
        'task': task,
        'version': version,
    }
    return render(request, 'tasks/version_detail.html', context)

@login_required
@require_POST
def task_archive(request, task_id):
    """View to archive a task."""
    task = get_object_or_404(
        Task.objects.filter(Q(owner=request.user) | Q(assignees=request.user)).distinct(), 
        pk=task_id
    )
    
    task.archive()
    
    # Create activity log
    TaskActivity.objects.create(
        task=task,
        activity_type='status_change',
        user=request.user,
        description=f'Task "{task.title}" archived by {request.user.username}'
    )
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'task_id': str(task.id)})
    
    messages.success(request, f'Task "{task.title}" archived successfully!')
    return redirect('tasks:task_list')

@login_required
@require_POST
def task_unarchive(request, task_id):
    """View to unarchive a task."""
    task = get_object_or_404(
        Task.objects.filter(Q(owner=request.user) | Q(assignees=request.user)).distinct(), 
        pk=task_id
    )
    
    task.unarchive()
    
    # Create activity log
    TaskActivity.objects.create(
        task=task,
        activity_type='status_change',
        user=request.user,
        description=f'Task "{task.title}" unarchived by {request.user.username}'
    )
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success', 'task_id': str(task.id)})
    
    messages.success(request, f'Task "{task.title}" unarchived successfully!')
    return redirect('tasks:task_detail', task_id=task.id)

@login_required
def task_stats(request):
    """Return task statistics for the current user as JSON."""
    today = timezone.now().date()
    
    # Get all non-archived tasks for the current user
    user_tasks = Task.objects.filter(
        Q(assignees=request.user) | Q(created_by=request.user),
        is_archived=False
    ).distinct()
    
    # Count tasks by status
    total_tasks = user_tasks.count()
    completed_tasks = user_tasks.filter(status='Completed').count()
    in_progress_tasks = user_tasks.filter(status='In Progress').count()
    overdue_tasks = user_tasks.filter(
        status__in=['Todo', 'In Progress'],
        due_date__lt=today
    ).count()
    
    # Calculate completion percentage
    completion_percentage = round((completed_tasks / total_tasks) * 100) if total_tasks > 0 else 0
    
    # Return JSON response
    return JsonResponse({
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'in_progress_tasks': in_progress_tasks,
        'overdue_tasks': overdue_tasks,
        'completion_percentage': completion_percentage
    })

class TaskListView(generics.ListAPIView):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer

def shared_resource_view(request, token):
    """
    Public view for shared tasks or projects via direct link.
    Guests can view, authenticated users can edit if allowed.
    """
    try:
        share_link = ShareLink.objects.select_related('content_type').get(token=token)
    except ShareLink.DoesNotExist:
        return render(request, 'tasks/share_link_error.html', {
            'error_message': 'This share link is invalid or does not exist.'
        })
    if not share_link.is_active:
        return render(request, 'tasks/share_link_error.html', {
            'error_message': 'This share link has been revoked by the owner.'
        })
    if share_link.is_expired():
        return render(request, 'tasks/share_link_error.html', {
            'error_message': 'This share link has expired.'
        })
    resource = share_link.content_object
    is_task = isinstance(resource, Task)
    is_project = isinstance(resource, Project)
    can_edit = False
    if share_link.permission == 'edit' and request.user.is_authenticated:
        # Only allow edit if user is logged in
        can_edit = True
    context = {
        'resource': resource,
        'share_link': share_link,
        'can_edit': can_edit,
        'is_task': is_task,
        'is_project': is_project,
        'guest_banner': True,
    }
    if is_task:
        template = 'tasks/shared_task_detail.html'
    elif is_project:
        template = 'tasks/shared_project_detail.html'
    else:
        return render(request, 'tasks/share_link_error.html', {
            'error_message': 'This share link does not point to a valid resource.'
        })
    return render(request, template, context)

def get_or_create_active_share_link(resource, permission):
    """
    Utility to get or create an active share link for a resource.
    """
    content_type = ContentType.objects.get_for_model(resource)
    existing = ShareLink.objects.filter(
        content_type=content_type,
        object_id=resource.id,
        is_active=True
    ).first()
    if existing:
        return existing, False
    link = ShareLink.objects.create(
        content_type=content_type,
        object_id=resource.id,
        permission=permission,
        is_active=True
    )
    return link, True

@login_required
@require_http_methods(["POST"])
@csrf_protect
def create_share_link(request, resource_type, resource_id):
    """
    Create a share link for a task or project. Only owner can create. AJAX or normal POST.
    If 'check_only' is set in POST, only return the existing link (do not create).
    """
    logger.debug(f"[create_share_link] Called with resource_type={resource_type}, resource_id={resource_id}, POST={request.POST}")
    permission = request.POST.get('permission', 'view')
    check_only = request.POST.get('check_only')
    if resource_type == 'task':
        resource = get_object_or_404(Task, id=resource_id, owner=request.user)
    elif resource_type == 'project':
        resource = get_object_or_404(Project, id=resource_id, owner=request.user)
    else:
        logger.error(f"[create_share_link] Invalid resource type: {resource_type}")
        return JsonResponse({'error': 'Invalid resource type'}, status=400)
    content_type = ContentType.objects.get_for_model(resource)
    link = ShareLink.objects.filter(
        content_type=content_type,
        object_id=resource.id,
        is_active=True
    ).first()
    if check_only:
        logger.debug(f"[create_share_link] check_only: {check_only}, found link: {link}")
        if link:
            url = request.build_absolute_uri(
                reverse('tasks:shared_resource_view', args=[str(link.token)])
            )
            logger.debug(f"[create_share_link] Returning existing link: {url}, permission: {link.permission}")
            return JsonResponse({'url': url, 'permission': link.permission, 'created': False})
        else:
            logger.debug(f"[create_share_link] No active share link found.")
            return JsonResponse({'error': 'No active share link.'}, status=404)
    # Not check_only: create if not exists
    if not link:
        link = ShareLink.objects.create(
            content_type=content_type,
            object_id=resource.id,
            permission=permission,
            is_active=True
        )
        created = True
        logger.debug(f"[create_share_link] Created new share link: {link}")
    else:
        created = False
        logger.debug(f"[create_share_link] Found existing share link: {link}")
    url = request.build_absolute_uri(
        reverse('tasks:shared_resource_view', args=[str(link.token)])
    )
    logger.debug(f"[create_share_link] Returning link: {url}, permission: {link.permission}, created: {created}")
    return JsonResponse({'url': url, 'permission': link.permission, 'created': created})

@login_required
@require_http_methods(["POST"])
@csrf_protect
def revoke_share_link(request, resource_type, resource_id):
    """
    Revoke (deactivate) the share link for a task or project. Only owner can revoke.
    """
    if resource_type == 'task':
        resource = get_object_or_404(Task, id=resource_id, owner=request.user)
    elif resource_type == 'project':
        resource = get_object_or_404(Project, id=resource_id, owner=request.user)
    else:
        return JsonResponse({'error': 'Invalid resource type'}, status=400)
    content_type = ContentType.objects.get_for_model(resource)
    link = ShareLink.objects.filter(
        content_type=content_type,
        object_id=resource.id,
        is_active=True
    ).first()
    if link:
        link.is_active = False
        link.save()
        revoked = True
    else:
        revoked = False
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'revoked': revoked})
    messages.success(request, 'Share link revoked.' if revoked else 'No active share link to revoke.')
    return redirect(resource.get_absolute_url())
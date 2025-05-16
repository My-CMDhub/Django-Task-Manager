"""
URL configuration for mysite project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Q
from tasks.models import Task, Project
from django.utils import timezone

def home(request):
    return render(request, 'home.html')

@login_required
def dashboard(request):
    context = {}
    
    # If user is authenticated, get their tasks
    if request.user.is_authenticated:
        # Get user's tasks
        user_tasks = Task.objects.filter(
            Q(owner=request.user) | Q(assignees=request.user)
        ).distinct().order_by('-created_at')
        
        # Don't show archived tasks
        user_tasks = user_tasks.filter(is_archived=False)
        
        # Count tasks by status
        todo_count = user_tasks.filter(status='todo').count()
        in_progress_count = user_tasks.filter(status='in_progress').count()
        completed_count = user_tasks.filter(status='completed').count()
        total_count = user_tasks.count()
        
        # Calculate completion rate
        completion_rate = 0
        if total_count > 0:
            completion_rate = int((completed_count / total_count) * 100)
        
        # Get tasks due today
        today = timezone.now().date()
        tasks_due_today = user_tasks.filter(
            due_date__date=today,
            status__in=['todo', 'in_progress']
        ).order_by('due_date')
        
        # Get tasks due this week (next 7 days)
        week_end = today + timezone.timedelta(days=7)
        tasks_due_soon = user_tasks.filter(
            due_date__date__range=[today + timezone.timedelta(days=1), week_end],
            status__in=['todo', 'in_progress']
        ).order_by('due_date')
        
        # Get overdue tasks
        overdue_tasks = user_tasks.filter(
            due_date__lt=timezone.now(),
            status__in=['todo', 'in_progress']
        ).order_by('due_date')
        
        # Get user's projects
        user_projects = Project.objects.filter(
            Q(owner=request.user) | Q(members=request.user)
        ).filter(is_archived=False).order_by('-created_at')[:5]
        
        # Calculate project completion rates
        project_stats = []
        for project in user_projects:
            project_tasks = Task.objects.filter(project=project).filter(is_archived=False)
            project_total = project_tasks.count()
            project_completed = project_tasks.filter(status='completed').count()
            project_completion = 0
            if project_total > 0:
                project_completion = int((project_completed / project_total) * 100)
            
            project_stats.append({
                'project': project,
                'total_tasks': project_total,
                'completed_tasks': project_completed,
                'completion_rate': project_completion,
                'todo_tasks': project_tasks.filter(status='todo').count(),
                'in_progress_tasks': project_tasks.filter(status='in_progress').count(),
            })
        
        # Add to context
        context.update({
            'total_tasks': total_count,
            'todo_count': todo_count,
            'in_progress_count': in_progress_count,
            'completed_count': completed_count,
            'completion_rate': completion_rate,
            'tasks_due_today': tasks_due_today,
            'tasks_due_soon': tasks_due_soon,
            'overdue_tasks': overdue_tasks,
            'projects': user_projects,
            'project_stats': project_stats,
        })
    
    return render(request, 'dashboard.html', context)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/', include('auth_app.urls')),
    path('', home, name='home'),
    path('dashboard/', login_required(dashboard), name='dashboard'),
    path('tasks/', include('tasks.urls')),
    path('api/', include('tasks.urls', namespace='api_tasks')),
    # path('api/chatbot/', include('chatbot_app.urls')),  # Original chatbot integration - commented out
    # Updated chatbot integration - with unique app_name
    path('chatbot/', include('chatbot_integration.chatbot_app.urls')),
]

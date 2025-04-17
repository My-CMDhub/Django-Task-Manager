from django.urls import path
from . import views

app_name = 'tasks'

urlpatterns = [
    # Task CRUD operations
    path('', views.task_list, name='task_list'),
    path('create/', views.task_create, name='task_create'),
    path('<uuid:task_id>/', views.task_detail, name='task_detail'),
    path('<uuid:task_id>/update/', views.task_update, name='task_update'),
    path('<uuid:task_id>/delete/', views.task_delete, name='task_delete'),
    
    # Task actions
    path('<uuid:task_id>/complete/', views.task_mark_complete, name='task_mark_complete'),
    path('<uuid:task_id>/in-progress/', views.task_mark_in_progress, name='task_mark_in_progress'),
    path('<uuid:task_id>/archive/', views.task_archive, name='task_archive'),
    path('<uuid:task_id>/unarchive/', views.task_unarchive, name='task_unarchive'),
    
    # Task versions
    path('<uuid:task_id>/versions/', views.view_task_versions, name='view_task_versions'),
    path('<uuid:task_id>/versions/<int:version_number>/', views.view_version_detail, name='view_version_detail'),
    
    # Time tracking
    path('<uuid:task_id>/time-entry/', views.add_time_entry, name='add_time_entry'),
    
    # Comments and attachments
    path('<uuid:task_id>/comment/', views.add_comment, name='add_comment'),
    path('<uuid:task_id>/attachment/', views.add_attachment, name='add_attachment'),
    
    # Projects
    path('projects/', views.project_list, name='project_list'),
    path('projects/create/', views.project_create, name='project_create'),
    path('projects/<uuid:project_id>/', views.project_detail, name='project_detail'),
    path('projects/<uuid:project_id>/update/', views.project_update, name='project_update'),
    path('projects/<uuid:project_id>/archive/', views.project_archive, name='project_archive'),
    path('projects/<uuid:project_id>/unarchive/', views.project_unarchive, name='project_unarchive'),
    path('projects/<uuid:project_id>/delete/', views.project_delete, name='project_delete'),
    
    # Bulk actions
    path('bulk/<str:action>/', views.bulk_action, name='bulk_action'),
    path('projects/bulk/<str:action>/', views.bulk_project_action, name='bulk_project_action'),
    
    # Tags
    path('tags/', views.manage_tags, name='manage_tags'),
    path('tags/<uuid:pk>/delete/', views.delete_tag, name='delete_tag'),
    path('<uuid:task_pk>/tags/add/', views.add_tag_to_task, name='add_tag_to_task'),
    path('<uuid:task_pk>/tags/<uuid:tag_pk>/remove/', views.remove_tag_from_task, name='remove_tag_from_task'),
    
    # Task stats
    path('tasks/stats/', views.task_stats, name='task_stats'),
] 
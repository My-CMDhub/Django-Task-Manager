from django.contrib import admin
from .models import (
    Task, TaskComment, TaskTag, TaskAttachment, 
    TaskActivity, TaskReminder, Project, TaskVersion,
    TimeEntry, CustomField, CustomFieldValue
)

# Register your models here.
class TaskActivityInline(admin.TabularInline):
    model = TaskActivity
    extra = 0
    readonly_fields = ['activity_type', 'user', 'description', 'created_at']
    can_delete = False

class TaskCommentInline(admin.TabularInline):
    model = TaskComment
    extra = 0

class TaskAttachmentInline(admin.TabularInline):
    model = TaskAttachment
    extra = 0

class TaskReminderInline(admin.TabularInline):
    model = TaskReminder
    extra = 0

class TaskVersionInline(admin.TabularInline):
    model = TaskVersion
    extra = 0
    readonly_fields = ['version_number', 'title', 'status', 'priority', 'modified_by', 'created_at']
    can_delete = False

class TimeEntryInline(admin.TabularInline):
    model = TimeEntry
    extra = 0

class CustomFieldValueInline(admin.TabularInline):
    model = CustomFieldValue
    extra = 0

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'priority', 'due_date', 'owner', 'created_at']
    list_filter = ['status', 'priority', 'created_at', 'is_archived']
    search_fields = ['title', 'description']
    date_hierarchy = 'created_at'
    inlines = [
        TaskActivityInline, TaskCommentInline, TaskAttachmentInline, 
        TaskReminderInline, TaskVersionInline, TimeEntryInline,
        CustomFieldValueInline
    ]
    readonly_fields = ['created_at', 'updated_at', 'completed_at', 'archived_at']
    filter_horizontal = ['assignees', 'tags', 'dependencies']
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'owner', 'assignees')
        }),
        ('Status & Priority', {
            'fields': ('status', 'priority', 'project', 'parent_task', 'position')
        }),
        ('Dates', {
            'fields': ('due_date', 'created_at', 'updated_at', 'completed_at')
        }),
        ('Archive Status', {
            'fields': ('is_archived', 'archived_at')
        }),
        ('Time Tracking', {
            'fields': ('estimated_hours', 'actual_hours')
        }),
        ('Relations', {
            'fields': ('tags', 'dependencies')
        }),
        ('AI Fields', {
            'fields': ('ai_summary', 'ai_suggestions', 'is_ai_generated')
        }),
        ('Supabase Sync', {
            'fields': ('supabase_id', 'is_synced', 'last_synced_at')
        })
    )

@admin.register(TaskComment)
class TaskCommentAdmin(admin.ModelAdmin):
    list_display = ['task', 'user', 'created_at', 'is_ai_generated']
    list_filter = ['created_at', 'is_ai_generated']
    search_fields = ['content', 'task__title']
    date_hierarchy = 'created_at'

@admin.register(TaskTag)
class TaskTagAdmin(admin.ModelAdmin):
    list_display = ['name', 'color', 'created_by', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name']

@admin.register(TaskAttachment)
class TaskAttachmentAdmin(admin.ModelAdmin):
    list_display = ['file_name', 'task', 'file_type', 'file_size', 'uploaded_by', 'uploaded_at']
    list_filter = ['file_type', 'uploaded_at']
    search_fields = ['file_name', 'task__title']
    date_hierarchy = 'uploaded_at'

@admin.register(TaskActivity)
class TaskActivityAdmin(admin.ModelAdmin):
    list_display = ['task', 'activity_type', 'user', 'created_at']
    list_filter = ['activity_type', 'created_at']
    search_fields = ['description', 'task__title']
    date_hierarchy = 'created_at'

@admin.register(TaskReminder)
class TaskReminderAdmin(admin.ModelAdmin):
    list_display = ['task', 'reminder_time', 'reminder_type', 'is_sent', 'created_by']
    list_filter = ['reminder_type', 'is_sent', 'created_at']
    search_fields = ['task__title']
    date_hierarchy = 'reminder_time'

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'owner', 'created_at', 'is_archived']
    list_filter = ['created_at', 'is_archived']
    search_fields = ['name', 'description']
    date_hierarchy = 'created_at'
    filter_horizontal = ['members']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'owner', 'members')
        }),
        ('Status', {
            'fields': ('is_archived',)
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at')
        }),
        ('Supabase Sync', {
            'fields': ('supabase_id', 'is_synced', 'last_synced_at')
        })
    )

@admin.register(TaskVersion)
class TaskVersionAdmin(admin.ModelAdmin):
    list_display = ['task', 'version_number', 'modified_by', 'created_at']
    list_filter = ['created_at']
    search_fields = ['task__title']
    date_hierarchy = 'created_at'
    readonly_fields = ['task', 'version_number', 'title', 'description', 'status', 'priority', 
                       'due_date', 'modified_by', 'created_at', 'data_snapshot']

@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    list_display = ['task', 'user', 'start_time', 'end_time', 'duration', 'is_billable']
    list_filter = ['is_billable', 'created_at']
    search_fields = ['task__title', 'description']
    date_hierarchy = 'start_time'
    readonly_fields = ['duration', 'created_at', 'updated_at']

@admin.register(CustomField)
class CustomFieldAdmin(admin.ModelAdmin):
    list_display = ['name', 'field_type', 'is_required', 'created_by', 'created_at']
    list_filter = ['field_type', 'is_required', 'created_at']
    search_fields = ['name', 'description']
    date_hierarchy = 'created_at'
    filter_horizontal = ['projects']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(CustomFieldValue)
class CustomFieldValueAdmin(admin.ModelAdmin):
    list_display = ['field', 'task', 'created_at']
    list_filter = ['created_at']
    search_fields = ['field__name', 'task__title']
    date_hierarchy = 'created_at'
    readonly_fields = ['created_at', 'updated_at']

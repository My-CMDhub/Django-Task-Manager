from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
import uuid
from auth_app.models import User

# Create your models here.
class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name_plural = "Categories"

# Task status choices
class TaskStatus(models.TextChoices):
    TODO = 'TODO', 'To Do'
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    COMPLETED = 'COMPLETED', 'Completed'
    BLOCKED = 'BLOCKED', 'Blocked'
    DEFERRED = 'DEFERRED', 'Deferred'

# Task priority choices
class TaskPriority(models.TextChoices):
    LOW = 'LOW', 'Low'
    MEDIUM = 'MEDIUM', 'Medium'
    HIGH = 'HIGH', 'High'
    CRITICAL = 'CRITICAL', 'Critical'

# Recurrence pattern choices
class RecurrencePattern(models.TextChoices):
    DAILY = 'DAILY', 'Daily'
    WEEKLY = 'WEEKLY', 'Weekly'
    BIWEEKLY = 'BIWEEKLY', 'Every Two Weeks'
    MONTHLY = 'MONTHLY', 'Monthly'
    QUARTERLY = 'QUARTERLY', 'Quarterly'
    YEARLY = 'YEARLY', 'Yearly'
    CUSTOM = 'CUSTOM', 'Custom'

# Sync status choices
class SyncStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending Sync'
    SYNCED = 'SYNCED', 'Synced with Supabase'
    FAILED = 'FAILED', 'Sync Failed'
    NOT_NEEDED = 'NOT_NEEDED', 'Sync Not Needed'

class Project(models.Model):
    """Model to represent a project or workspace that contains tasks."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_projects')
    members = models.ManyToManyField(User, related_name='projects', blank=True)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Supabase sync fields
    supabase_id = models.CharField(max_length=255, blank=True, null=True)
    is_synced = models.BooleanField(default=False)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return self.name
    
    @property
    def completed_tasks(self):
        """Get all completed tasks for this project."""
        return self.tasks.filter(status='completed')
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Project'
        verbose_name_plural = 'Projects'

class TaskTag(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50)
    color = models.CharField(max_length=7, default="#1E90FF")  # Default to dodger blue
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Supabase sync fields
    supabase_id = models.CharField(max_length=255, blank=True, null=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        unique_together = ['name', 'created_by']
        ordering = ['name']
        verbose_name = 'Task Tag'
        verbose_name_plural = 'Task Tags'

class Task(models.Model):
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    STATUS_CHOICES = [
        ('todo', 'To Do'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('archived', 'Archived'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_tasks')
    assignees = models.ManyToManyField(User, related_name='assigned_tasks', blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='medium')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='todo')
    due_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    tags = models.ManyToManyField(TaskTag, related_name='tasks', blank=True)
    
    # New fields for Phase 2
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks', null=True, blank=True)
    parent_task = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subtasks')
    dependencies = models.ManyToManyField('self', blank=True, symmetrical=False, related_name='dependent_tasks')
    estimated_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    actual_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    position = models.PositiveIntegerField(default=0, help_text="Position for drag & drop prioritization")
    
    # AI-related fields
    ai_summary = models.TextField(blank=True)
    ai_suggestions = models.TextField(blank=True)
    is_ai_generated = models.BooleanField(default=False)
    
    # Supabase sync fields
    supabase_id = models.CharField(max_length=255, blank=True, null=True)
    is_synced = models.BooleanField(default=False)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    
    def mark_completed(self):
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
    
    def archive(self):
        self.status = 'archived'
        self.is_archived = True
        self.archived_at = timezone.now()
        self.save()
    
    def unarchive(self):
        """Restore an archived task to its previous state."""
        self.is_archived = False
        self.archived_at = None
        # Keep the status as it was before archiving if it was completed,
        # otherwise set it back to todo
        if self.status == 'archived':
            self.status = 'todo' if not self.completed_at else 'completed'
        self.save()
    
    def mark_in_progress(self):
        self.status = 'in_progress'
        self.completed_at = None
        self.save()
    
    def mark_todo(self):
        self.status = 'todo'
        self.completed_at = None
        self.save()
    
    def is_overdue(self):
        if self.due_date and self.status != 'completed' and self.status != 'archived':
            return timezone.now() > self.due_date
        return False
    
    def create_version(self, user):
        """Create a new version of this task."""
        import json
        
        # Serialize the task data
        data = {
            'title': self.title,
            'description': self.description,
            'priority': self.priority,
            'status': self.status,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'assignees': list(self.assignees.values_list('id', flat=True)),
            'tags': list(self.tags.values_list('id', flat=True)),
            'project_id': str(self.project.id) if self.project else None,
            'parent_task_id': str(self.parent_task.id) if self.parent_task else None,
            'estimated_hours': float(self.estimated_hours) if self.estimated_hours else None,
            'actual_hours': float(self.actual_hours) if self.actual_hours else None,
        }
        
        # Get the latest version number
        last_version = self.versions.order_by('-version_number').first()
        version_number = 1
        if last_version:
            version_number = last_version.version_number + 1
        
        # Create a new version
        TaskVersion.objects.create(
            task=self,
            version_number=version_number,
            title=self.title,
            description=self.description,
            status=self.status,
            priority=self.priority,
            due_date=self.due_date,
            modified_by=user,
            data_snapshot=data
        )
    
    def get_dependencies(self):
        """Get all task dependencies."""
        return self.dependencies.all()
    
    def get_dependent_tasks(self):
        """Get all tasks that depend on this task."""
        return self.dependent_tasks.all()
    
    def has_dependency_cycle(self, dependency_id):
        """Check if adding this dependency would create a cycle."""
        if str(self.id) == str(dependency_id):
            return True
            
        # Check if the dependency depends on this task
        dependency = Task.objects.get(id=dependency_id)
        if dependency.dependencies.filter(id=self.id).exists():
            return True
            
        # Check recursively for all dependent tasks
        for dependent_task in dependency.dependent_tasks.all():
            if dependent_task.has_dependency_cycle(self.id):
                return True
                
        return False
    
    def get_custom_fields(self):
        """Get all custom field values for this task."""
        return self.custom_field_values.all()
    
    def __str__(self):
        return self.title
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Task'
        verbose_name_plural = 'Tasks'

class TaskActivity(models.Model):
    ACTIVITY_TYPES = [
        ('create', 'Task Created'),
        ('update', 'Task Updated'),
        ('delete', 'Task Deleted'),
        ('status_change', 'Status Changed'),
        ('assignee_add', 'Assignee Added'),
        ('assignee_remove', 'Assignee Removed'),
        ('comment_add', 'Comment Added'),
        ('attachment_add', 'Attachment Added'),
        ('attachment_remove', 'Attachment Removed'),
        ('tag_add', 'Tag Added'),
        ('tag_remove', 'Tag Removed'),
        ('reminder_add', 'Reminder Added'),
        ('reminder_remove', 'Reminder Removed'),
        ('ai_suggestion', 'AI Suggestion'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)  # Null if AI action
    description = models.TextField()
    metadata = models.JSONField(null=True, blank=True)  # Additional data related to the activity
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.activity_type} on {self.task.title}"
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Task Activity'
        verbose_name_plural = 'Task Activities'

class TaskAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='task_attachments/')
    file_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=100)
    file_size = models.IntegerField()  # Size in bytes
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Supabase storage reference
    supabase_path = models.CharField(max_length=255, blank=True, null=True)
    
    def __str__(self):
        return f"{self.file_name} - {self.task.title}"
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Task Attachment'
        verbose_name_plural = 'Task Attachments'

class TaskComment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_ai_generated = models.BooleanField(default=False)
    
    # Supabase sync fields
    supabase_id = models.CharField(max_length=255, blank=True, null=True)
    
    def __str__(self):
        return f"Comment by {self.user.username} on {self.task.title}"
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Task Comment'
        verbose_name_plural = 'Task Comments'

class TaskReminder(models.Model):
    REMINDER_TYPE_CHOICES = [
        ('email', 'Email'),
        ('notification', 'In-app Notification'),
        ('both', 'Email and Notification'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='reminders')
    reminder_time = models.DateTimeField()
    reminder_type = models.CharField(max_length=15, choices=REMINDER_TYPE_CHOICES, default='both')
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def mark_as_sent(self):
        self.is_sent = True
        self.sent_at = timezone.now()
        self.save()
    
    def __str__(self):
        return f"Reminder for {self.task.title} at {self.reminder_time}"
    
    class Meta:
        ordering = ['reminder_time']
        verbose_name = 'Task Reminder'
        verbose_name_plural = 'Task Reminders'

    def clean(self):
        if self.reminder_time < timezone.now():
            raise ValidationError("Reminder time cannot be in the past.")
        
        if self.task.due_date and self.reminder_time > self.task.due_date:
            raise ValidationError("Reminder time cannot be after the task due date.")
        
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
        
        # Create activity for new reminder
        if not self.pk:
            TaskActivity.objects.create(
                task=self.task,
                activity_type='reminder',
                description=f'A reminder was set for {self.reminder_time.strftime("%Y-%m-%d %H:%M")}'
            )

class TaskVersion(models.Model):
    """Model to track version history for tasks."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField()
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20)
    priority = models.CharField(max_length=10)
    due_date = models.DateTimeField(null=True, blank=True)
    modified_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    data_snapshot = models.JSONField(help_text="Complete snapshot of task data at this version")
    
    def __str__(self):
        return f"{self.task.title} - v{self.version_number}"
    
    class Meta:
        ordering = ['-version_number']
        verbose_name = 'Task Version'
        verbose_name_plural = 'Task Versions'
        unique_together = ['task', 'version_number']

class TimeEntry(models.Model):
    """Model to track time spent on tasks."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='time_entries')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='time_entries')
    description = models.TextField(blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    duration = models.DurationField(null=True, blank=True, help_text="Duration in hours:minutes:seconds")
    is_billable = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Supabase sync fields
    supabase_id = models.CharField(max_length=255, blank=True, null=True)
    
    def save(self, *args, **kwargs):
        # Calculate duration if start and end times are set
        if self.start_time and self.end_time:
            self.duration = self.end_time - self.start_time
            
            # Update task's actual hours
            if self.task and self.duration:
                hours = self.duration.total_seconds() / 3600
                if self.task.actual_hours:
                    self.task.actual_hours += hours
                else:
                    self.task.actual_hours = hours
                self.task.save(update_fields=['actual_hours'])
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.task.title} - {self.start_time.strftime('%Y-%m-%d')}"
    
    class Meta:
        ordering = ['-start_time']
        verbose_name = 'Time Entry'
        verbose_name_plural = 'Time Entries'

class CustomFieldType(models.TextChoices):
    TEXT = 'TEXT', 'Text'
    NUMBER = 'NUMBER', 'Number'
    DATE = 'DATE', 'Date'
    BOOLEAN = 'BOOLEAN', 'Boolean'
    DROPDOWN = 'DROPDOWN', 'Dropdown'

class CustomField(models.Model):
    """Model for defining custom fields that can be added to tasks."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    field_type = models.CharField(max_length=20, choices=CustomFieldType.choices)
    is_required = models.BooleanField(default=False)
    default_value = models.JSONField(null=True, blank=True)
    options = models.JSONField(null=True, blank=True, help_text="Options for dropdown fields")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Option to restrict to specific projects
    projects = models.ManyToManyField(Project, related_name='custom_fields', blank=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Custom Field'
        verbose_name_plural = 'Custom Fields'

class CustomFieldValue(models.Model):
    """Model for storing values of custom fields for tasks."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='custom_field_values')
    field = models.ForeignKey(CustomField, on_delete=models.CASCADE, related_name='values')
    value = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.field.name}: {self.value}"
    
    class Meta:
        unique_together = ['task', 'field']
        verbose_name = 'Custom Field Value'
        verbose_name_plural = 'Custom Field Values'

from django.db.models.signals import post_save, post_delete, m2m_changed, post_migrate
from django.dispatch import receiver
from .models import Task, TaskActivity, TaskReminder
from django.utils import timezone
import logging
from django.core.management import call_command

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Task)
def task_post_save(sender, instance, created, **kwargs):
    """Signal handler for Task post_save events"""
    try:
        # Log task creation in activity log
        if created:
            TaskActivity.objects.create(
                task=instance,
                activity_type='create',
                description=f"Task '{instance.title}' was created",
                user=instance.owner
            )
        else:
            # For updates, create an update activity
            # But only if this is not coming from a status change handler
            # to avoid duplicate activities
            if not hasattr(instance, '_status_changed'):
                TaskActivity.objects.create(
                    task=instance,
                    activity_type='update',
                    description=f"Task '{instance.title}' was updated",
                    user=instance.owner
                )
            
            # Check if status changed to 'completed'
            if instance.status == 'completed' and not instance.completed_at:
                instance._status_changed = True
                instance.completed_at = timezone.now()
                instance.save()
    except Exception as e:
        logger.error(f"Error in task_post_save signal: {str(e)}")

@receiver(post_delete, sender=Task)
def task_post_delete(sender, instance, **kwargs):
    """Signal handler for Task post_delete events"""
    try:
        # We can't create an activity for a deleted task since the task is gone
        # But we could log this for auditing purposes
        logger.info(f"Task '{instance.title}' (ID: {instance.id}) was deleted by {instance.owner}")
    except Exception as e:
        logger.error(f"Error in task_post_delete signal: {str(e)}")

@receiver(m2m_changed, sender=Task.assignees.through)
def task_assignees_changed(sender, instance, action, pk_set, **kwargs):
    """Signal handler for changes to Task.assignees M2M relationship"""
    try:
        if action == 'post_add' and pk_set:
            # Get the usernames of added assignees
            from django.contrib.auth import get_user_model
            User = get_user_model()
            usernames = User.objects.filter(id__in=pk_set).values_list('username', flat=True)
            
            # Create activity for each added assignee
            for username in usernames:
                TaskActivity.objects.create(
                    task=instance,
                    activity_type='assignee_add',
                    description=f"User '{username}' was assigned to this task",
                    user=instance.owner
                )
                
        elif action == 'post_remove' and pk_set:
            # Get the usernames of removed assignees
            from django.contrib.auth import get_user_model
            User = get_user_model()
            usernames = User.objects.filter(id__in=pk_set).values_list('username', flat=True)
            
            # Create activity for each removed assignee
            for username in usernames:
                TaskActivity.objects.create(
                    task=instance,
                    activity_type='assignee_remove',
                    description=f"User '{username}' was removed from this task",
                    user=instance.owner
                )
    except Exception as e:
        logger.error(f"Error in task_assignees_changed signal: {str(e)}")

@receiver(m2m_changed, sender=Task.tags.through)
def task_tags_changed(sender, instance, action, pk_set, **kwargs):
    """Signal handler for changes to Task.tags M2M relationship"""
    try:
        if action == 'post_add' and pk_set:
            # Get the names of added tags
            from .models import TaskTag
            tag_names = TaskTag.objects.filter(id__in=pk_set).values_list('name', flat=True)
            
            # Create activity for each added tag
            for tag_name in tag_names:
                TaskActivity.objects.create(
                    task=instance,
                    activity_type='tag_add',
                    description=f"Tag '{tag_name}' was added to this task",
                    user=instance.owner
                )
                
        elif action == 'post_remove' and pk_set:
            # Get the names of removed tags
            from .models import TaskTag
            tag_names = TaskTag.objects.filter(id__in=pk_set).values_list('name', flat=True)
            
            # Create activity for each removed tag
            for tag_name in tag_names:
                TaskActivity.objects.create(
                    task=instance,
                    activity_type='tag_remove',
                    description=f"Tag '{tag_name}' was removed from this task",
                    user=instance.owner
                )
    except Exception as e:
        logger.error(f"Error in task_tags_changed signal: {str(e)}")

@receiver(post_save, sender=TaskReminder)
def reminder_post_save(sender, instance, created, **kwargs):
    """Signal handler for TaskReminder post_save events"""
    try:
        if created:
            # Create an activity for the new reminder
            TaskActivity.objects.create(
                task=instance.task,
                activity_type='reminder_add',
                description=f"Reminder set for {instance.reminder_time.strftime('%Y-%m-%d %H:%M')}",
                user=instance.created_by
            )
    except Exception as e:
        logger.error(f"Error in reminder_post_save signal: {str(e)}")

@receiver(post_delete, sender=TaskReminder)
def reminder_post_delete(sender, instance, **kwargs):
    """Signal handler for TaskReminder post_delete events"""
    try:
        # Create an activity for the deleted reminder
        TaskActivity.objects.create(
            task=instance.task,
            activity_type='reminder_remove',
            description=f"Reminder for {instance.reminder_time.strftime('%Y-%m-%d %H:%M')} was removed",
            user=instance.created_by
        )
    except Exception as e:
        logger.error(f"Error in reminder_post_delete signal: {str(e)}")

@receiver(post_migrate)
def sync_users_after_migrate(sender, **kwargs):
    """
    Run the sync_supabase_users management command after migrations
    to ensure users are up to date in Django admin.
    """
    if sender.name == 'tasks':
        logger.info("Running post-migration user sync...")
        try:
            call_command('sync_supabase_users')
            logger.info("User sync completed successfully after migration")
        except Exception as e:
            logger.error(f"Error during post-migration user sync: {str(e)}") 
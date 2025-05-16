from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import TaskCreationRequest

@receiver(post_save, sender=TaskCreationRequest)
def handle_task_creation(sender, instance, created, **kwargs):
    """
    Signal handler that processes task creation requests when they're saved or updated
    """
    # Only process pending requests that haven't been processed yet
    if instance.status == 'pending':
        from .utils import create_task
        
        try:
            # Get the user from the conversation
            user = instance.message.conversation.user
            
            # Create task info dict
            task_info = {
                'title': instance.title,
                'description': instance.description,
                'due_date': instance.due_date,
            }
            
            # Create the task
            task_id = create_task(user, task_info)
            
            # Update the request
            instance.created_task_id = task_id
            instance.status = 'completed'
            instance.save(update_fields=['created_task_id', 'status'])
            
        except Exception as e:
            # Update the request with error info
            instance.status = 'failed'
            instance.error_message = str(e)
            instance.save(update_fields=['status', 'error_message']) 
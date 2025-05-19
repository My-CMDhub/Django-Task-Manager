from django.db import models
from django.conf import settings
from django.utils import timezone

class Conversation(models.Model):
    """A conversation between a user and the chatbot."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='conversations'
    )
    title = models.CharField(max_length=255, blank=True, default="Conversation")
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Conversation {self.id}"
    
    def get_recent_messages(self, count=5):
        """
        Gets the most recent messages in the conversation to provide context.
        
        Args:
            count (int): Number of recent message pairs to retrieve
            
        Returns:
            list: List of dictionaries with message content and role
        """
        # Get the most recent messages, ordered by timestamp
        recent_messages = self.messages.order_by('-timestamp')[:count*2]
        
        # Re-order them from oldest to newest for context
        recent_messages = reversed(list(recent_messages))
        
        # Format the messages
        context = []
        for message in recent_messages:
            context.append({
                'role': 'user' if message.is_user else 'assistant',
                'content': message.content
            })
            
        return context

class Message(models.Model):
    """A message within a conversation."""
    conversation = models.ForeignKey(
        Conversation, 
        on_delete=models.CASCADE, 
        related_name='messages'
    )
    content = models.TextField()
    is_user = models.BooleanField(default=True)  # True if sent by user, False if sent by bot
    timestamp = models.DateTimeField(auto_now_add=True)
    # Add role field for compatibility with newer code
    role = models.CharField(max_length=20, blank=True, null=True)  # 'user' or 'assistant'
    
    def save(self, *args, **kwargs):
        # Set role based on is_user for backward compatibility
        if self.role is None:
            self.role = 'user' if self.is_user else 'assistant'
        # Set is_user based on role for backward compatibility
        if self.role == 'user':
            self.is_user = True
        elif self.role == 'assistant':
            self.is_user = False
        super().save(*args, **kwargs)
    
    def __str__(self):
        sender = "User" if self.is_user else "Bot"
        return f"{sender} message in conversation {self.conversation.id}"

class ChatbotConversation(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE,
        related_name='chatbot_conversations'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_interaction = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return f"Conversation with {self.user.username}"

class ChatMessage(models.Model):
    SENDER_CHOICES = (
        ('user', 'User'),
        ('bot', 'Bot'),
    )
    
    conversation = models.ForeignKey(
        ChatbotConversation, 
        on_delete=models.CASCADE,
        related_name='messages'
    )
    content = models.TextField()
    sender = models.CharField(max_length=10, choices=SENDER_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.sender} message in conversation {self.conversation.id}"

class TaskCreationRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    )
    STEP_CHOICES = (
        ('title', 'Title'),
        ('due_date', 'Due Date'),
        ('priority', 'Priority'),
        ('description', 'Description'),
        ('done', 'Done'),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='active_task_creations',
        null=True,
        blank=True
    )
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='task_creations',
        null=True,
        blank=True
    )
    current_step = models.CharField(max_length=20, choices=STEP_CHOICES, default='title')
    title = models.CharField(max_length=255, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    due_date = models.DateTimeField(null=True, blank=True)
    priority = models.CharField(max_length=20, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_task_id = models.CharField(max_length=255, null=True, blank=True)  # Changed to CharField to store UUID strings
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Task creation (user={self.user_id}, status={self.status}, step={self.current_step})"

    class Meta:
        app_label = 'chatbot_integration_chatbot_app'
        # No unique constraints - we'll handle this in the code
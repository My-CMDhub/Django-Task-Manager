from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
import uuid
import json
from django.utils.translation import gettext_lazy as _

class User(AbstractUser):
    """Extended user model with Supabase integration"""
    email_verified = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True)
    last_password_change = models.DateTimeField(auto_now_add=True)
    supabase_id = models.CharField(max_length=255, blank=True, null=True, db_index=True, help_text=_("User ID in Supabase"))
    last_login_at = models.DateTimeField(null=True)
    failed_login_attempts = models.PositiveIntegerField(default=0)
    account_locked_until = models.DateTimeField(null=True)
    
    # Additional security fields
    requires_password_change = models.BooleanField(default=False)
    mfa_enabled = models.BooleanField(default=False)
    recovery_codes = models.TextField(null=True, blank=True)
    verification_tokens = models.JSONField(null=True, blank=True)
    
    def update_last_login(self):
        self.last_login_at = timezone.now()
        self.save(update_fields=['last_login_at'])

    def increment_failed_attempts(self):
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            self.account_locked_until = timezone.now() + timezone.timedelta(minutes=15)
        self.save(update_fields=['failed_login_attempts', 'account_locked_until'])

    def reset_login_attempts(self):
        self.failed_login_attempts = 0
        self.account_locked_until = None
        self.save(update_fields=['failed_login_attempts', 'account_locked_until'])

    def active_sessions(self):
        return self.session_set.filter(expires_at__gt=timezone.now())

    def increment_login_attempts(self):
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            self.account_locked_until = timezone.now() + timezone.timedelta(minutes=30)
        self.save(update_fields=['failed_login_attempts', 'account_locked_until'])

    def __str__(self):
        return self.email or self.username

    @property
    def is_active_with_email(self):
        return self.is_active and self.email_verified

    class Meta:
        swappable = 'AUTH_USER_MODEL'
        verbose_name = _("user")
        verbose_name_plural = _("users")

class UserProfile(models.Model):
    """Profile model to extend the User model with additional fields and Supabase synchronization"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    supabase_uid = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    verified = models.BooleanField(default=False)
    last_synced = models.DateTimeField(auto_now=True)
    
    # Additional profile fields
    phone = models.CharField(max_length=20, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    avatar_url = models.URLField(blank=True, null=True)
    preferences = models.JSONField(default=dict, null=True, blank=True)
    
    def __str__(self):
        return f"Profile for {self.user.email or self.user.username}"
    
    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

class Session(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    ip_address = models.GenericIPAddressField()
    user_agent = models.CharField(max_length=255)
    device = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    last_activity = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email} - {self.device} ({self.ip_address})"

    class Meta:
        indexes = [
            models.Index(fields=['user', 'expires_at']),
        ]

class UserSyncSchedule(models.Model):
    """Configuration for automatic user synchronization between Django and Supabase"""
    DIRECTION_CHOICES = [
        ('to-django', 'From Supabase to Django'),
        ('to-supabase', 'From Django to Supabase'),
        ('both', 'Bidirectional')
    ]
    
    FREQUENCY_CHOICES = [
        ('hourly', 'Every Hour'),
        ('daily', 'Every Day'),
        ('weekly', 'Every Week')
    ]
    
    is_active = models.BooleanField(default=True, help_text="Enable or disable the scheduled sync")
    direction = models.CharField(max_length=15, choices=DIRECTION_CHOICES, default='to-django',
                                help_text="Direction of the synchronization")
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='daily',
                                help_text="How often to run the synchronization")
    force_update = models.BooleanField(default=False, 
                                      help_text="Force update even if users already exist")
    last_run = models.DateTimeField(null=True, blank=True, help_text="When the sync was last executed")
    next_run = models.DateTimeField(null=True, blank=True, help_text="When the sync is scheduled to run next")
    last_status = models.TextField(blank=True, help_text="Status of the last sync operation")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "User Sync Schedule"
        verbose_name_plural = "User Sync Schedules"
    
    def __str__(self):
        return f"User Sync ({self.frequency}, {self.direction})"
    
    def save(self, *args, **kwargs):
        # Calculate next run time based on frequency
        import datetime
        from django.utils import timezone
        
        now = timezone.now()
        
        if not self.next_run or self.next_run < now:
            if self.frequency == 'hourly':
                self.next_run = now.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)
            elif self.frequency == 'daily':
                self.next_run = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
            elif self.frequency == 'weekly':
                # Set to next Monday at midnight
                days_ahead = 7 - now.weekday() if now.weekday() > 0 else 7
                self.next_run = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=days_ahead)
        
        super().save(*args, **kwargs)

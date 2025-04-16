from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib import messages
from .models import User, Session, UserSyncSchedule

class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'is_active', 'email_verified', 'is_staff', 'is_superuser', 'supabase_id', 'date_joined', 'last_login')
    list_filter = ('is_active', 'email_verified', 'is_staff', 'is_superuser', 'deleted_at')
    search_fields = ('username', 'email', 'supabase_id')
    ordering = ('-date_joined',)  # Most recent users first
    
    # Include deleted users in the queryset
    def get_queryset(self, request):
        # Get all users, including soft-deleted ones
        queryset = self.model.objects.all()
        return queryset
    
    def last_login_at(self, obj):
        return obj.last_login
    last_login_at.short_description = 'Last Login'
    
    fieldsets = (
        (None, {'fields': ('username', 'email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name')}),
        ('Account status', {'fields': ('is_active', 'email_verified', 'deleted_at')}),
        ('Security', {'fields': ('failed_login_attempts', 'account_locked_until', 'requires_password_change', 'mfa_enabled')}),
        ('Supabase', {'fields': ('supabase_id',)}),
        ('Permissions', {'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'last_password_change', 'date_joined')}),
    )

class SessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'device', 'ip_address', 'created_at', 'expires_at')
    list_filter = ('device',)
    search_fields = ('user__username', 'user__email', 'ip_address')
    readonly_fields = ('id', 'created_at', 'last_activity')

@admin.register(UserSyncSchedule)
class UserSyncScheduleAdmin(admin.ModelAdmin):
    list_display = ('id', 'direction', 'frequency', 'is_active', 'next_run', 'last_run')
    list_filter = ('is_active', 'direction', 'frequency')
    search_fields = ('last_status',)
    readonly_fields = ('last_run', 'next_run', 'last_status', 'created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('is_active', 'direction', 'frequency', 'force_update')
        }),
        ('Schedule Information', {
            'fields': ('next_run', 'last_run', 'last_status'),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    actions = ['run_sync_now']
    
    def run_sync_now(self, request, queryset):
        from django.core.management import call_command
        import io
        from django.utils import timezone
        
        sync_count = 0
        for schedule in queryset:
            if not schedule.is_active:
                continue
                
            # Capture output
            output = io.StringIO()
            try:
                # Run the sync command based on schedule settings
                call_command(
                    'sync_users',
                    direction=schedule.direction,
                    force=schedule.force_update,
                    stdout=output
                )
                
                # Update the schedule
                schedule.last_run = timezone.now()
                schedule.last_status = output.getvalue()
                schedule.save()
                sync_count += 1
                
            except Exception as e:
                self.message_user(
                    request,
                    f"Error running sync for schedule {schedule.id}: {str(e)}",
                    level=messages.ERROR
                )
        
        if sync_count > 0:
            self.message_user(
                request, 
                f"Successfully ran sync for {sync_count} schedule(s).",
                level=messages.SUCCESS
            )
    
    run_sync_now.short_description = "Run selected sync schedules now"

admin.site.register(User, CustomUserAdmin)
admin.site.register(Session, SessionAdmin)

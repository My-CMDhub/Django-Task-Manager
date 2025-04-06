from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.utils import timezone
from auth_app.models import UserSyncSchedule
import logging
import io

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Run all active scheduled user synchronizations'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force-run-all', 
            action='store_true',
            help='Run all active schedules regardless of next_run time'
        )

    def handle(self, *args, **options):
        force_run_all = options.get('force_run_all', False)
        now = timezone.now()
        
        # Get all active schedules
        if force_run_all:
            schedules = UserSyncSchedule.objects.filter(is_active=True)
            self.stdout.write(f"Fetching all active schedules regardless of next_run time.")
        else:
            schedules = UserSyncSchedule.objects.filter(is_active=True, next_run__lte=now)
            self.stdout.write(f"Fetching schedules due to run (next_run <= {now}).")
        
        self.stdout.write(f"Found {schedules.count()} schedule(s) to run.")
        
        for schedule in schedules:
            self.stdout.write(f"Running sync schedule {schedule.id} ({schedule.direction}, {schedule.frequency})")
            
            # Capture output from the sync command
            output_buffer = io.StringIO()
            try:
                # Run the sync command with the schedule's settings
                call_command(
                    'sync_users',
                    direction=schedule.direction,
                    force=schedule.force_update,
                    stdout=output_buffer
                )
                
                output_text = output_buffer.getvalue()
                
                # Update the schedule record
                schedule.last_run = now
                schedule.last_status = output_text
                
                # Calculate the next run time based on frequency
                import datetime
                if schedule.frequency == 'hourly':
                    schedule.next_run = now.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(hours=1)
                elif schedule.frequency == 'daily':
                    schedule.next_run = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
                elif schedule.frequency == 'weekly':
                    # Set to next Monday at midnight
                    days_ahead = 7 - now.weekday() if now.weekday() > 0 else 7
                    schedule.next_run = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=days_ahead)
                
                schedule.save()
                self.stdout.write(self.style.SUCCESS(f"Sync completed successfully. Next run: {schedule.next_run}"))
                
                # Print the output
                self.stdout.write(output_text)
                
            except Exception as e:
                logger.error(f"Error running sync schedule {schedule.id}: {str(e)}", exc_info=True)
                self.stdout.write(self.style.ERROR(f"Error running sync schedule {schedule.id}: {str(e)}"))
                
                # Update the schedule record with the error
                schedule.last_run = now
                schedule.last_status = f"ERROR: {str(e)}"
                schedule.save()
                
        self.stdout.write(self.style.SUCCESS("All scheduled syncs completed.")) 
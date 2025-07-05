from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
import json
from chatbot_integration.chatbot_app.utils import get_user_context_data

class Command(BaseCommand):
    help = 'Test get_user_context_data for a given user (by username or user_id)'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='Username of the user')
        parser.add_argument('--user_id', type=int, help='ID of the user')

    def handle(self, *args, **options):
        User = get_user_model()
        user = None
        if options['username']:
            try:
                user = User.objects.get(username=options['username'])
            except User.DoesNotExist:
                raise CommandError(f"User with username '{options['username']}' does not exist.")
        elif options['user_id']:
            try:
                user = User.objects.get(id=options['user_id'])
            except User.DoesNotExist:
                raise CommandError(f"User with id '{options['user_id']}' does not exist.")
        else:
            raise CommandError('Please provide either --username or --user_id.')

        context_data = get_user_context_data(user)
        self.stdout.write(self.style.SUCCESS(json.dumps(context_data, indent=2))) 
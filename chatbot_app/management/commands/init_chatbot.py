from django.core.management.base import BaseCommand, CommandError
from chatbot_app.initialize import init_index_from_url
import os

class Command(BaseCommand):
    help = 'Initialize the chatbot by scraping data, creating embeddings, and setting up the knowledge base'

    def add_arguments(self, parser):
        parser.add_argument('--urls', nargs='+', type=str, help='List of URLs to scrape')
        parser.add_argument('--api-key', type=str, help='OpenAI API key (optional, will use env var if not provided)')

    def handle(self, *args, **options):
        urls = options['urls']
        api_key = options['api_key']
        
        if not urls:
            urls = [
                'https://docs.djangoproject.com/en/4.2/topics/db/models/',
                'https://en.wikipedia.org/wiki/Task_management',
                'https://en.wikipedia.org/wiki/Time_management'
            ]
            self.stdout.write(self.style.WARNING('No URLs provided, using default URLs'))
        
        self.stdout.write(self.style.SUCCESS(f'Initializing chatbot with {len(urls)} URLs'))
        
        # Use provided API key or get from environment
        if not api_key:
            api_key = os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise CommandError('No OpenAI API key provided or found in environment')
        
        # Initialize the index
        try:
            self.stdout.write('Starting initialization...')
            index = init_index_from_url(urls, api_key)
            if index:
                self.stdout.write(self.style.SUCCESS('Chatbot successfully initialized!'))
            else:
                self.stdout.write(self.style.ERROR('Failed to initialize chatbot'))
        except Exception as e:
            raise CommandError(f'Error initializing chatbot: {str(e)}') 
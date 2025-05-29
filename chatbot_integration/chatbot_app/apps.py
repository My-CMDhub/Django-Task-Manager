from django.apps import AppConfig


class ChatbotAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chatbot_integration.chatbot_app'
    label = 'chatbot_integration_chatbot_app'
    verbose_name = 'ChatGPT Task Manager Assistant'
    
    def ready(self):
        """
        Import signal handlers when the app is ready
        """
        try:
            import chatbot_integration.chatbot_app.signals
        except ImportError:
            pass 
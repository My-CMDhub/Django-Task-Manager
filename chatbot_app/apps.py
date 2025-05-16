from django.apps import AppConfig


class ChatbotAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chatbot_app'
    
    def ready(self):
        """
        Import signal handlers when the app is ready
        """
        import chatbot_app.signals 
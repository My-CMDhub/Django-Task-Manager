from django.apps import AppConfig

class ChatbotIntegrationConfig(AppConfig):
    name = 'chatbot_integration'
    verbose_name = 'Chatbot Integration'
 
    def ready(self):
        try:
            import chatbot_integration.signals
        except ImportError:
            pass 
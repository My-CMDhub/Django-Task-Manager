from django.urls import path
from . import views
from django.views.generic import TemplateView

app_name = 'integration_chatbot'

urlpatterns = [
    path('', views.chatbot_interface, name='interface'),
    path('message/', views.chatbot_message, name='message'),
    path('history/', views.get_conversation_history, name='history'),
    path('process_message/', views.process_message, name='process_message'),
    path('test/', TemplateView.as_view(template_name='chatbot_app/chatbot_test.html'), name='chatbot_test'),
]
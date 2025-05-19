from django.urls import path
from . import views
from django.views.generic import TemplateView

app_name = 'chatbot_app'
 
urlpatterns = [
    path('message/', views.chatbot_message, name='message'),
    path('history/', views.get_conversation_history, name='history'),
    path('test/', TemplateView.as_view(template_name='chatbot_app/chatbot_test.html'), name='chatbot_test'),
] 
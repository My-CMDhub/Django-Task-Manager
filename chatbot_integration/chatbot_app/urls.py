from django.urls import path
from . import views

app_name = 'integration_chatbot'

urlpatterns = [
    path('', views.chatbot_interface, name='interface'),
    path('message/', views.chatbot_message, name='message'),
    path('history/', views.get_conversation_history, name='history'),
    path('process_message/', views.process_message, name='process_message'),
]
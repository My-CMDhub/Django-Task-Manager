from django.urls import path
from . import views

app_name = 'chatbot_app'
 
urlpatterns = [
    path('message/', views.chatbot_message, name='message'),
    path('history/', views.get_conversation_history, name='history'),
] 
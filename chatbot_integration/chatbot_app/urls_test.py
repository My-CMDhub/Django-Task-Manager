from django.urls import path
from . import views_enhanced as views

app_name = 'chatbot_app'

urlpatterns = [
    # Main chatbot interface
    path('', views.ChatbotView.as_view(), name='chatbot_interface'),
    
    # Enhanced chat API endpoints
    path('api/chat/', views.chat_api, name='chat_api'),
    path('api/conversations/', views.get_user_conversations, name='get_user_conversations'),
    path('api/conversations/<str:conversation_id>/history/', views.get_conversation_history, name='get_conversation_history'),
    path('api/conversations/<str:conversation_id>/clear/', views.clear_conversation_context, name='clear_conversation_context'),
    path('api/stats/', views.get_chatbot_stats, name='get_chatbot_stats'),
    
    # Development and debugging
    path('test/', views.chatbot_test_view, name='chatbot_test'),
    path('api/debug/', views.chatbot_debug_info, name='chatbot_debug_info'),
    path('api/test/', views.test_chatbot_simple, name='test_chatbot_simple'),
]

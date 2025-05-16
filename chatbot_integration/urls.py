from django.urls import path, include

app_name = 'chatbot'
 
urlpatterns = [
    path('api/', include('chatbot_integration.chatbot_app.urls', namespace='api')),
    path('process_message/', include('chatbot_integration.chatbot_app.urls')),
]
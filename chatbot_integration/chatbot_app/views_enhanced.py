"""
Enhanced views for the chatbot system.
"""

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
import json
import logging
from .models import ChatbotConversation, ChatMessage
from .processor import chatbot_processor

logger = logging.getLogger(__name__)

@method_decorator(login_required, name='dispatch')
class ChatbotView(View):
    """Main chatbot interface view with enhanced capabilities"""
    
    def get(self, request):
        """Render the enhanced chatbot interface"""
        return render(request, 'chatbot_app/chatbot.html')

@csrf_exempt
@require_http_methods(["POST"])
@login_required
def chat_api(request):
    """Enhanced API endpoint for chatbot interactions"""
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '').strip()
        conversation_id = data.get('conversation_id')
        
        if not user_message:
            return JsonResponse({'error': 'Message is required'}, status=400)
        
        # Process message using the enhanced chatbot processor
        result = chatbot_processor.process_message(
            user_message=user_message,
            user=request.user,
            conversation_id=conversation_id
        )
        
        if result['success']:
            return JsonResponse({
                'response': result['response'],
                'conversation_id': result['conversation_id'],
                'intent': result.get('intent'),
                'entities': result.get('entities'),
                'context': result.get('context'),
                'success': True
            })
        else:
            return JsonResponse({
                'error': result.get('error', 'Unknown error'),
                'response': result.get('response', 'I encountered an error processing your message.'),
                'conversation_id': result.get('conversation_id'),
                'success': False
            }, status=500)
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"Error in chat API: {str(e)}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)

@login_required
@require_http_methods(["GET"])
def get_conversation_history(request, conversation_id):
    """Get conversation history with enhanced metadata"""
    try:
        limit = int(request.GET.get('limit', 50))
        result = chatbot_processor.get_conversation_history(
            user=request.user,
            conversation_id=conversation_id,
            limit=limit
        )
        
        if result['success']:
            return JsonResponse(result)
        else:
            return JsonResponse({
                'error': result.get('error', 'Failed to retrieve conversation'),
                'success': False
            }, status=404 if 'not found' in result.get('error', '').lower() else 500)
        
    except ValueError:
        return JsonResponse({'error': 'Invalid limit parameter'}, status=400)
    except Exception as e:
        logger.error(f"Error getting conversation history: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)

@login_required
@require_http_methods(["GET"])
def get_user_conversations(request):
    """Get all conversations for the current user"""
    try:
        limit = int(request.GET.get('limit', 20))
        result = chatbot_processor.get_user_conversations(
            user=request.user,
            limit=limit
        )
        
        return JsonResponse(result)
        
    except ValueError:
        return JsonResponse({'error': 'Invalid limit parameter'}, status=400)
    except Exception as e:
        logger.error(f"Error getting user conversations: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)

@csrf_exempt
@require_http_methods(["POST"])
@login_required
def clear_conversation_context(request, conversation_id):
    """Clear conversation context and memory"""
    try:
        success = chatbot_processor.clear_conversation_context(
            user=request.user,
            conversation_id=conversation_id
        )
        
        if success:
            return JsonResponse({
                'message': 'Conversation context cleared successfully',
                'success': True
            })
        else:
            return JsonResponse({
                'error': 'Conversation not found or could not be cleared',
                'success': False
            }, status=404)
        
    except Exception as e:
        logger.error(f"Error clearing conversation context: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)

@login_required
@require_http_methods(["GET"])
def get_chatbot_stats(request):
    """Get chatbot usage statistics for the current user"""
    try:
        result = chatbot_processor.get_chatbot_stats(user=request.user)
        return JsonResponse(result)
        
    except Exception as e:
        logger.error(f"Error getting chatbot stats: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)

@login_required
def chatbot_test_view(request):
    """Enhanced test view for chatbot development and debugging"""
    return render(request, 'chatbot_app/chatbot_test.html')

@login_required
@require_http_methods(["GET"])
def chatbot_debug_info(request):
    """Get debug information about the chatbot system"""
    try:
        from .nlp.intents import intent_classifier
        from .flows.base import flow_manager
        
        debug_info = {
            'intent_patterns': len(intent_classifier.intents),
            'cached_patterns': len(intent_classifier.pattern_cache),
            'registered_flows': list(flow_manager.flow_registry.keys()),
            'active_flows': len(flow_manager.active_flows),
            'user_conversations': ChatbotConversation.objects.filter(user=request.user).count(),
            'total_messages': ChatMessage.objects.filter(conversation__user=request.user).count(),
            'system_status': 'operational'
        }
        
        return JsonResponse({
            'debug_info': debug_info,
            'success': True
        })
        
    except Exception as e:
        logger.error(f"Error getting debug info: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)

# Simple test endpoint to verify basic functionality
@csrf_exempt
@require_http_methods(["POST"])
@login_required
def test_chatbot_simple(request):
    """Simple test endpoint for basic chatbot functionality"""
    try:
        data = json.loads(request.body)
        test_message = data.get('message', 'Hello')
        
        # Test basic intent classification
        from .nlp.intents import intent_classifier
        intent = intent_classifier.classify(test_message)
        
        # Test entity extraction
        from .nlp.entities import entity_extractor
        entities = entity_extractor.extract_entities(test_message)
        
        return JsonResponse({
            'message': test_message,
            'intent': {
                'primary': intent.primary,
                'secondary': intent.secondary,
                'confidence': intent.confidence
            },
            'entities': {k: [{'value': e.value, 'confidence': e.confidence} for e in v] for k, v in entities.items() if v},
            'status': 'success'
        })
        
    except Exception as e:
        logger.error(f"Error in simple test: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

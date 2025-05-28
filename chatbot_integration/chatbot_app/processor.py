"""
Main chatbot processor that orchestrates NLP, context management, and response generation.
"""

import logging
from typing import Dict, Any, Optional, Tuple
from django.utils import timezone
from django.contrib.auth.models import User

from .nlp.intents import intent_classifier, Intent
from .nlp.entities import entity_extractor
from .nlp.context import conversation_manager
from .flows.base import flow_manager
from .response_generation.generator import response_generator
from .models import ChatbotConversation, ChatMessage

logger = logging.getLogger(__name__)

class ChatbotProcessor:
    """
    Main chatbot processor that orchestrates all components:
    - NLP (intent classification and entity extraction)
    - Context management and conversation state
    - Conversation flows for multi-turn dialogues
    - Response generation with personalization
    """
    
    def __init__(self):
        self.conversation_timeout = 3600  # 1 hour
        
    def process_message(self, user_message: str, user: User, 
                       conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Process a user message and generate an appropriate response.
        
        Args:
            user_message: The user's input message
            user: Django User object
            conversation_id: Optional conversation ID for context
            
        Returns:
            Dictionary containing response and metadata
        """
        try:
            # Get or create conversation
            conversation = self._get_or_create_conversation(user, conversation_id)
            conversation_id = str(conversation.id)
            
            # Update conversation timestamp
            conversation.last_interaction = timezone.now()
            conversation.save()
            
            # Save user message
            user_msg = ChatMessage.objects.create(
                conversation=conversation,
                content=user_message,
                sender='user'
            )
            
            # Step 1: Intent Classification
            intent = intent_classifier.classify(user_message)
            logger.info(f"Classified intent: {intent.primary}.{intent.secondary} (confidence: {intent.confidence:.2f})")
            
            # Step 2: Entity Extraction
            entities = entity_extractor.extract_entities(user_message)
            logger.info(f"Extracted entities: {self._summarize_entities(entities)}")
            
            # Step 3: Context Management
            # Update conversation context with new entities
            for entity_type, entity_list in entities.items():
                for entity in entity_list:
                    if entity.confidence > 0.7:  # Only store high-confidence entities
                        conversation_manager.add_entity_to_memory(
                            conversation_id, str(user.id), entity.type, 
                            entity.value, entity.confidence
                        )
            
            # Update last intent in context
            conversation_manager.update_last_intent(
                conversation_id, str(user.id), f"{intent.primary}.{intent.secondary}"
            )
            
            # Get conversation context
            context = conversation_manager.get_conversation_context(conversation_id, str(user.id))
            
            # Step 4: Check for active conversation flows
            active_flow = flow_manager.get_active_flow(conversation_id)
            
            # Step 5: Generate response
            response_text = response_generator.generate_response(
                user_message=user_message,
                intent=intent,
                entities=entities,
                user=user,
                conversation_id=conversation_id,
                context=context
            )
            
            # Save bot response
            bot_msg = ChatMessage.objects.create(
                conversation=conversation,
                content=response_text,
                sender='bot'
            )
            
            # Prepare response metadata
            response_data = {
                'response': response_text,
                'conversation_id': conversation_id,
                'intent': {
                    'primary': intent.primary,
                    'secondary': intent.secondary,
                    'confidence': intent.confidence
                },
                'entities': self._format_entities_for_response(entities),
                'context': {
                    'has_active_flow': active_flow is not None,
                    'flow_type': active_flow.flow_id if active_flow else None,
                    'conversation_turn': conversation.messages.count()
                },
                'success': True
            }
            
            logger.info(f"Successfully processed message for user {user.username}")
            return response_data
            
        except Exception as e:
            logger.error(f"Error processing chatbot message: {e}", exc_info=True)
            
            # Create error response
            error_response = {
                'response': "I'm sorry, I encountered an error processing your message. Please try again.",
                'conversation_id': conversation_id if 'conversation_id' in locals() else None,
                'error': str(e),
                'success': False
            }
            
            # Try to save error message if conversation exists
            try:
                if 'conversation' in locals():
                    ChatMessage.objects.create(
                        conversation=conversation,
                        content=error_response['response'],
                        sender='bot'
                    )
            except:
                pass  # Don't let logging errors break the error response
            
            return error_response
    
    def _get_or_create_conversation(self, user: User, conversation_id: Optional[str] = None) -> ChatbotConversation:
        """Get existing conversation or create a new one"""
        if conversation_id:
            try:
                conversation = ChatbotConversation.objects.get(
                    id=conversation_id,
                    user=user
                )
                return conversation
            except ChatbotConversation.DoesNotExist:
                logger.warning(f"Conversation {conversation_id} not found for user {user.username}")
        
        # Create new conversation
        conversation = ChatbotConversation.objects.create(user=user)
        logger.info(f"Created new conversation {conversation.id} for user {user.username}")
        return conversation
    
    def _summarize_entities(self, entities: Dict) -> str:
        """Create a summary string of extracted entities for logging"""
        summary = []
        for entity_type, entity_list in entities.items():
            if entity_list:
                values = [str(e.value) for e in entity_list[:3]]  # Limit to 3 for brevity
                summary.append(f"{entity_type}: {', '.join(values)}")
        return "; ".join(summary) if summary else "none"
    
    def _format_entities_for_response(self, entities: Dict) -> Dict:
        """Format entities for the API response"""
        formatted = {}
        for entity_type, entity_list in entities.items():
            if entity_list:
                formatted[entity_type] = [
                    {
                        'value': entity.value,
                        'confidence': entity.confidence,
                        'raw_text': entity.raw_text
                    }
                    for entity in entity_list
                ]
        return formatted
    
    def get_conversation_history(self, user: User, conversation_id: str, 
                               limit: int = 50) -> Dict[str, Any]:
        """
        Get conversation history for a user.
        
        Args:
            user: Django User object
            conversation_id: Conversation identifier
            limit: Maximum number of messages to return
            
        Returns:
            Dictionary containing conversation history and metadata
        """
        try:
            conversation = ChatbotConversation.objects.get(
                id=conversation_id,
                user=user
            )
            
            messages = conversation.messages.order_by('-timestamp')[:limit]
            messages = list(reversed(messages))  # Chronological order
            
            history = []
            for msg in messages:
                history.append({
                    'content': msg.content,
                    'sender': msg.sender,
                    'timestamp': msg.timestamp.isoformat()
                })
            
            # Get conversation context
            context = conversation_manager.get_conversation_context(
                conversation_id, str(user.id)
            )
            
            return {
                'conversation_id': conversation_id,
                'messages': history,
                'context': context,
                'created_at': conversation.created_at.isoformat(),
                'last_interaction': conversation.last_interaction.isoformat(),
                'total_messages': conversation.messages.count(),
                'success': True
            }
            
        except ChatbotConversation.DoesNotExist:
            return {
                'error': 'Conversation not found',
                'success': False
            }
        except Exception as e:
            logger.error(f"Error getting conversation history: {e}")
            return {
                'error': 'Failed to retrieve conversation history',
                'success': False
            }
    
    def get_user_conversations(self, user: User, limit: int = 20) -> Dict[str, Any]:
        """
        Get all conversations for a user.
        
        Args:
            user: Django User object
            limit: Maximum number of conversations to return
            
        Returns:
            Dictionary containing conversations list and metadata
        """
        try:
            conversations = ChatbotConversation.objects.filter(
                user=user
            ).order_by('-last_interaction')[:limit]
            
            conversation_list = []
            for conv in conversations:
                # Get the last message for preview
                last_message = conv.messages.order_by('-timestamp').first()
                
                conversation_list.append({
                    'id': str(conv.id),
                    'created_at': conv.created_at.isoformat(),
                    'last_interaction': conv.last_interaction.isoformat(),
                    'message_count': conv.messages.count(),
                    'last_message_preview': last_message.content[:100] + '...' if last_message and len(last_message.content) > 100 else last_message.content if last_message else '',
                    'last_message_sender': last_message.sender if last_message else None
                })
            
            return {
                'conversations': conversation_list,
                'total_count': ChatbotConversation.objects.filter(user=user).count(),
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Error getting user conversations: {e}")
            return {
                'error': 'Failed to retrieve conversations',
                'success': False
            }
    
    def clear_conversation_context(self, user: User, conversation_id: str) -> bool:
        """
        Clear the context for a specific conversation.
        
        Args:
            user: Django User object
            conversation_id: Conversation identifier
            
        Returns:
            Boolean indicating success
        """
        try:
            # Verify the conversation belongs to the user
            conversation = ChatbotConversation.objects.get(
                id=conversation_id,
                user=user
            )
            
            # Clear conversation state from memory
            conversation_manager.clear_conversation_state(conversation_id)
            
            # End any active flows
            flow_manager.end_flow(conversation_id)
            
            logger.info(f"Cleared context for conversation {conversation_id}")
            return True
            
        except ChatbotConversation.DoesNotExist:
            logger.warning(f"Conversation {conversation_id} not found for user {user.username}")
            return False
        except Exception as e:
            logger.error(f"Error clearing conversation context: {e}")
            return False
    
    def get_chatbot_stats(self, user: User) -> Dict[str, Any]:
        """
        Get chatbot usage statistics for a user.
        
        Args:
            user: Django User object
            
        Returns:
            Dictionary containing usage statistics
        """
        try:
            conversations = ChatbotConversation.objects.filter(user=user)
            total_messages = ChatMessage.objects.filter(
                conversation__user=user
            ).count()
            
            user_messages = ChatMessage.objects.filter(
                conversation__user=user,
                sender='user'
            ).count()
            
            bot_messages = ChatMessage.objects.filter(
                conversation__user=user,
                sender='bot'
            ).count()
            
            # Get recent activity (last 30 days)
            from datetime import timedelta
            recent_cutoff = timezone.now() - timedelta(days=30)
            recent_conversations = conversations.filter(
                created_at__gte=recent_cutoff
            ).count()
            
            return {
                'total_conversations': conversations.count(),
                'total_messages': total_messages,
                'user_messages': user_messages,
                'bot_messages': bot_messages,
                'recent_conversations': recent_conversations,
                'first_conversation': conversations.order_by('created_at').first().created_at.isoformat() if conversations.exists() else None,
                'last_conversation': conversations.order_by('-last_interaction').first().last_interaction.isoformat() if conversations.exists() else None,
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Error getting chatbot stats: {e}")
            return {
                'error': 'Failed to retrieve statistics',
                'success': False
            }

# Global processor instance
chatbot_processor = ChatbotProcessor()

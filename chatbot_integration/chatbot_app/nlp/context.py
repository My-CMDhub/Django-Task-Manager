"""
Context management system for maintaining conversation state and managing multi-turn dialogues.
"""

import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.cache import cache
import logging

logger = logging.getLogger(__name__)

@dataclass
class ConversationState:
    """Represents the current state of a conversation"""
    conversation_id: str
    user_id: str
    current_flow: Optional[str] = None
    flow_step: int = 0
    context_data: Dict[str, Any] = None
    entity_memory: Dict[str, Any] = None
    topic_stack: List[str] = None
    last_intent: Optional[str] = None
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.context_data is None:
            self.context_data = {}
        if self.entity_memory is None:
            self.entity_memory = {}
        if self.topic_stack is None:
            self.topic_stack = []
        if self.created_at is None:
            self.created_at = timezone.now()
        if self.updated_at is None:
            self.updated_at = timezone.now()

@dataclass
class EntityReference:
    """Represents a reference to an entity in conversation memory"""
    entity_type: str
    entity_value: Any
    confidence: float
    mentioned_at: datetime
    last_referenced: datetime
    reference_count: int = 1
    
    def __post_init__(self):
        if self.last_referenced is None:
            self.last_referenced = self.mentioned_at

class ConversationManager:
    """
    Manages conversation state and context across multiple turns.
    Handles entity memory, topic tracking, and conversation flows.
    """
    
    def __init__(self):
        self.cache_timeout = 3600  # 1 hour
        self.max_entity_memory = 50  # Maximum entities to remember
        self.context_decay_hours = 24  # Hours after which context starts decaying
        
    def get_conversation_state(self, conversation_id: str, user_id: str) -> ConversationState:
        """
        Get or create conversation state for a conversation.
        
        Args:
            conversation_id: Unique conversation identifier
            user_id: User identifier
            
        Returns:
            ConversationState object
        """
        cache_key = f"conversation_state_{conversation_id}"
        
        # Try to get from cache
        cached_state = cache.get(cache_key)
        if cached_state:
            try:
                state_dict = json.loads(cached_state)
                # Convert datetime strings back to datetime objects
                if state_dict.get('created_at'):
                    state_dict['created_at'] = datetime.fromisoformat(state_dict['created_at'])
                if state_dict.get('updated_at'):
                    state_dict['updated_at'] = datetime.fromisoformat(state_dict['updated_at'])
                
                # Convert entity memory back to EntityReference objects
                entity_memory = {}
                for key, entity_data in state_dict.get('entity_memory', {}).items():
                    if isinstance(entity_data, dict):
                        entity_data['mentioned_at'] = datetime.fromisoformat(entity_data['mentioned_at'])
                        entity_data['last_referenced'] = datetime.fromisoformat(entity_data['last_referenced'])
                        entity_memory[key] = EntityReference(**entity_data)
                    else:
                        # Legacy format, create new EntityReference
                        entity_memory[key] = EntityReference(
                            entity_type='unknown',
                            entity_value=entity_data,
                            confidence=0.5,
                            mentioned_at=timezone.now(),
                            last_referenced=timezone.now()
                        )
                
                state_dict['entity_memory'] = entity_memory
                return ConversationState(**state_dict)
            except Exception as e:
                logger.warning(f"Failed to deserialize conversation state: {e}")
        
        # Create new state
        return ConversationState(
            conversation_id=conversation_id,
            user_id=user_id
        )
    
    def save_conversation_state(self, state: ConversationState):
        """
        Save conversation state to cache.
        
        Args:
            state: ConversationState to save
        """
        state.updated_at = timezone.now()
        
        # Convert to serializable format
        state_dict = asdict(state)
        
        # Convert datetime objects to ISO strings
        state_dict['created_at'] = state.created_at.isoformat()
        state_dict['updated_at'] = state.updated_at.isoformat()
        
        # Convert EntityReference objects to dictionaries
        entity_memory_dict = {}
        for key, entity_ref in state.entity_memory.items():
            if isinstance(entity_ref, EntityReference):
                entity_dict = asdict(entity_ref)
                entity_dict['mentioned_at'] = entity_ref.mentioned_at.isoformat()
                entity_dict['last_referenced'] = entity_ref.last_referenced.isoformat()
                entity_memory_dict[key] = entity_dict
            else:
                # Legacy format
                entity_memory_dict[key] = entity_ref
        
        state_dict['entity_memory'] = entity_memory_dict
        
        cache_key = f"conversation_state_{state.conversation_id}"
        cache.set(cache_key, json.dumps(state_dict), self.cache_timeout)
    
    def start_flow(self, conversation_id: str, user_id: str, flow_type: str, initial_data: Dict = None) -> ConversationState:
        """
        Start a new conversation flow.
        
        Args:
            conversation_id: Conversation identifier
            user_id: User identifier
            flow_type: Type of flow to start
            initial_data: Initial data for the flow
            
        Returns:
            Updated ConversationState
        """
        state = self.get_conversation_state(conversation_id, user_id)
        
        # Save current flow to topic stack if exists
        if state.current_flow:
            state.topic_stack.append(f"{state.current_flow}:{state.flow_step}")
        
        state.current_flow = flow_type
        state.flow_step = 0
        
        if initial_data:
            state.context_data.update(initial_data)
        
        self.save_conversation_state(state)
        return state
    
    def advance_flow(self, conversation_id: str, user_id: str, step_data: Dict = None) -> ConversationState:
        """
        Advance the current flow to the next step.
        
        Args:
            conversation_id: Conversation identifier
            user_id: User identifier
            step_data: Data from the current step
            
        Returns:
            Updated ConversationState
        """
        state = self.get_conversation_state(conversation_id, user_id)
        
        if state.current_flow:
            state.flow_step += 1
            
            if step_data:
                state.context_data.update(step_data)
        
        self.save_conversation_state(state)
        return state
    
    def end_flow(self, conversation_id: str, user_id: str) -> ConversationState:
        """
        End the current flow and return to previous topic if available.
        
        Args:
            conversation_id: Conversation identifier
            user_id: User identifier
            
        Returns:
            Updated ConversationState
        """
        state = self.get_conversation_state(conversation_id, user_id)
        
        # Clear current flow
        state.current_flow = None
        state.flow_step = 0
        
        # Restore previous topic if available
        if state.topic_stack:
            previous_topic = state.topic_stack.pop()
            if ':' in previous_topic:
                flow_type, step = previous_topic.split(':', 1)
                state.current_flow = flow_type
                try:
                    state.flow_step = int(step)
                except ValueError:
                    state.flow_step = 0
        
        self.save_conversation_state(state)
        return state
    
    def add_entity_to_memory(self, conversation_id: str, user_id: str, entity_type: str, 
                           entity_value: Any, confidence: float = 1.0):
        """
        Add an entity to conversation memory.
        
        Args:
            conversation_id: Conversation identifier
            user_id: User identifier
            entity_type: Type of entity (task, project, etc.)
            entity_value: Value of the entity
            confidence: Confidence score
        """
        state = self.get_conversation_state(conversation_id, user_id)
        
        # Create memory key
        memory_key = f"{entity_type}:{str(entity_value).lower()}"
        
        now = timezone.now()
        
        if memory_key in state.entity_memory:
            # Update existing entity
            entity_ref = state.entity_memory[memory_key]
            entity_ref.last_referenced = now
            entity_ref.reference_count += 1
            entity_ref.confidence = max(entity_ref.confidence, confidence)
        else:
            # Add new entity
            state.entity_memory[memory_key] = EntityReference(
                entity_type=entity_type,
                entity_value=entity_value,
                confidence=confidence,
                mentioned_at=now,
                last_referenced=now
            )
        
        # Clean up old entities if memory is full
        self._cleanup_entity_memory(state)
        
        self.save_conversation_state(state)
    
    def get_entity_from_memory(self, conversation_id: str, user_id: str, 
                             entity_type: str, partial_match: str = None) -> List[EntityReference]:
        """
        Retrieve entities from conversation memory.
        
        Args:
            conversation_id: Conversation identifier
            user_id: User identifier
            entity_type: Type of entity to search for
            partial_match: Partial string to match against entity values
            
        Returns:
            List of matching EntityReference objects
        """
        state = self.get_conversation_state(conversation_id, user_id)
        
        matches = []
        for memory_key, entity_ref in state.entity_memory.items():
            if entity_ref.entity_type == entity_type:
                if partial_match is None:
                    matches.append(entity_ref)
                elif partial_match.lower() in str(entity_ref.entity_value).lower():
                    matches.append(entity_ref)
        
        # Sort by recency and reference count
        matches.sort(key=lambda x: (x.last_referenced, x.reference_count), reverse=True)
        
        return matches
    
    def resolve_reference(self, conversation_id: str, user_id: str, 
                         reference: str, entity_type: str = None) -> Optional[Any]:
        """
        Resolve a contextual reference (like "it", "this task", etc.) to an actual entity.
        
        Args:
            conversation_id: Conversation identifier
            user_id: User identifier
            reference: The reference string to resolve
            entity_type: Optional entity type to limit search
            
        Returns:
            Resolved entity value or None
        """
        state = self.get_conversation_state(conversation_id, user_id)
        
        reference_lower = reference.lower()
        
        # Handle pronoun references
        if reference_lower in ['it', 'this', 'that']:
            # Get the most recently mentioned entity
            most_recent = None
            most_recent_time = None
            
            for entity_ref in state.entity_memory.values():
                if entity_type is None or entity_ref.entity_type == entity_type:
                    if most_recent_time is None or entity_ref.last_referenced > most_recent_time:
                        most_recent = entity_ref
                        most_recent_time = entity_ref.last_referenced
            
            return most_recent.entity_value if most_recent else None
        
        # Handle specific references
        if 'task' in reference_lower:
            tasks = self.get_entity_from_memory(conversation_id, user_id, 'task_reference')
            if tasks:
                return tasks[0].entity_value
        
        if 'project' in reference_lower:
            projects = self.get_entity_from_memory(conversation_id, user_id, 'project_reference')
            if projects:
                return projects[0].entity_value
        
        return None
    
    def get_conversation_context(self, conversation_id: str, user_id: str) -> Dict[str, Any]:
        """
        Get a summary of the current conversation context.
        
        Args:
            conversation_id: Conversation identifier
            user_id: User identifier
            
        Returns:
            Dictionary containing context information
        """
        state = self.get_conversation_state(conversation_id, user_id)
        
        # Get recent entities
        recent_entities = {}
        for entity_type in ['task_reference', 'project_reference', 'priority', 'date']:
            entities = self.get_entity_from_memory(conversation_id, user_id, entity_type)
            if entities:
                recent_entities[entity_type] = [e.entity_value for e in entities[:3]]
        
        return {
            'current_flow': state.current_flow,
            'flow_step': state.flow_step,
            'context_data': state.context_data,
            'recent_entities': recent_entities,
            'topic_stack': state.topic_stack,
            'last_intent': state.last_intent
        }
    
    def _cleanup_entity_memory(self, state: ConversationState):
        """Clean up old entities from memory when it gets too full"""
        if len(state.entity_memory) <= self.max_entity_memory:
            return
        
        # Calculate decay scores for entities
        now = timezone.now()
        entity_scores = []
        
        for memory_key, entity_ref in state.entity_memory.items():
            # Calculate recency score (0-1, newer is better)
            time_diff = now - entity_ref.last_referenced
            recency_score = max(0, 1 - (time_diff.total_seconds() / (self.context_decay_hours * 3600)))
            
            # Calculate reference score (normalized by reference count)
            reference_score = min(1, entity_ref.reference_count / 10)
            
            # Calculate confidence score
            confidence_score = entity_ref.confidence
            
            # Combined score
            total_score = (recency_score * 0.5 + reference_score * 0.3 + confidence_score * 0.2)
            
            entity_scores.append((memory_key, total_score))
        
        # Sort by score and keep only the top entities
        entity_scores.sort(key=lambda x: x[1], reverse=True)
        entities_to_keep = entity_scores[:self.max_entity_memory]
        
        # Update entity memory
        new_memory = {}
        for memory_key, _ in entities_to_keep:
            new_memory[memory_key] = state.entity_memory[memory_key]
        
        state.entity_memory = new_memory
    
    def clear_conversation_state(self, conversation_id: str):
        """
        Clear conversation state from cache.
        
        Args:
            conversation_id: Conversation identifier to clear
        """
        cache_key = f"conversation_state_{conversation_id}"
        cache.delete(cache_key)
    
    def update_last_intent(self, conversation_id: str, user_id: str, intent: str):
        """
        Update the last detected intent for context.
        
        Args:
            conversation_id: Conversation identifier
            user_id: User identifier
            intent: The detected intent
        """
        state = self.get_conversation_state(conversation_id, user_id)
        state.last_intent = intent
        self.save_conversation_state(state)

# Global conversation manager instance
conversation_manager = ConversationManager()

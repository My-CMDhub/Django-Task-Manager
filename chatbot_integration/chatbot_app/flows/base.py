"""
Base classes for conversation flows and multi-turn dialogue management.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class FlowState(Enum):
    """States for conversation flows"""
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"

@dataclass
class FlowStep:
    """Represents a step in a conversation flow"""
    step_id: str
    prompt: str
    validation_required: bool = False
    optional: bool = False
    retry_limit: int = 3
    error_message: str = "I didn't understand that. Could you please try again?"
    
class FlowResult:
    """Result of a flow execution"""
    def __init__(self, success: bool, message: str, data: Dict = None, next_step: str = None):
        self.success = success
        self.message = message
        self.data = data or {}
        self.next_step = next_step
        self.should_continue = next_step is not None

class BaseFlow(ABC):
    """
    Base class for all conversation flows.
    Provides common functionality for multi-turn dialogues.
    """
    
    def __init__(self, flow_id: str, user_id: str, conversation_id: str):
        self.flow_id = flow_id
        self.user_id = user_id
        self.conversation_id = conversation_id
        self.state = FlowState.STARTED
        self.current_step = 0
        self.collected_data = {}
        self.retry_count = 0
        self.steps = self._define_steps()
        
    @abstractmethod
    def _define_steps(self) -> List[FlowStep]:
        """Define the steps for this flow"""
        pass
    
    @abstractmethod
    def process_user_input(self, user_input: str, step_id: str) -> FlowResult:
        """Process user input for the current step"""
        pass
    
    def start_flow(self) -> FlowResult:
        """Start the conversation flow"""
        self.state = FlowState.IN_PROGRESS
        if self.steps:
            first_step = self.steps[0]
            return FlowResult(
                success=True,
                message=first_step.prompt,
                next_step=first_step.step_id
            )
        else:
            return FlowResult(
                success=False,
                message="No steps defined for this flow"
            )
    
    def advance_step(self, user_input: str) -> FlowResult:
        """Advance to the next step in the flow"""
        if self.current_step >= len(self.steps):
            return self.complete_flow()
        
        current_step_def = self.steps[self.current_step]
        
        # Process the user input for current step
        result = self.process_user_input(user_input, current_step_def.step_id)
        
        if result.success:
            # Move to next step
            self.current_step += 1
            self.retry_count = 0
            
            if self.current_step >= len(self.steps):
                return self.complete_flow()
            else:
                next_step_def = self.steps[self.current_step]
                result.next_step = next_step_def.step_id
                result.message = next_step_def.prompt
                result.should_continue = True
        else:
            # Handle retry logic
            self.retry_count += 1
            if self.retry_count >= current_step_def.retry_limit:
                return self.cancel_flow("Too many failed attempts")
            
            result.message = current_step_def.error_message
            result.next_step = current_step_def.step_id
            result.should_continue = True
        
        return result
    
    def complete_flow(self) -> FlowResult:
        """Complete the flow and return final result"""
        self.state = FlowState.COMPLETED
        return self._on_flow_complete()
    
    def cancel_flow(self, reason: str = "Flow cancelled") -> FlowResult:
        """Cancel the current flow"""
        self.state = FlowState.CANCELLED
        return FlowResult(
            success=False,
            message=f"Flow cancelled: {reason}"
        )
    
    def get_current_step(self) -> Optional[FlowStep]:
        """Get the current step definition"""
        if 0 <= self.current_step < len(self.steps):
            return self.steps[self.current_step]
        return None
    
    def get_progress(self) -> Dict[str, Any]:
        """Get flow progress information"""
        return {
            'flow_id': self.flow_id,
            'state': self.state.value,
            'current_step': self.current_step,
            'total_steps': len(self.steps),
            'progress_percentage': (self.current_step / len(self.steps)) * 100 if self.steps else 0,
            'collected_data': self.collected_data
        }
    
    @abstractmethod
    def _on_flow_complete(self) -> FlowResult:
        """Called when the flow is completed. Subclasses should implement this."""
        pass
    
    def validate_input(self, user_input: str, step_id: str) -> Tuple[bool, str]:
        """Validate user input for a specific step. Override in subclasses."""
        return True, ""
    
    def can_interrupt(self) -> bool:
        """Check if the flow can be interrupted. Override in subclasses."""
        return True
    
    def handle_interruption(self, interruption_type: str, data: Dict = None) -> FlowResult:
        """Handle flow interruption. Override in subclasses."""
        return FlowResult(
            success=True,
            message="Flow interrupted. We can continue where we left off later."
        )

class FlowManager:
    """
    Manages active conversation flows for users.
    """
    
    def __init__(self):
        self.active_flows = {}  # conversation_id -> BaseFlow
        self.flow_registry = {}  # flow_type -> Flow class
    
    def register_flow(self, flow_type: str, flow_class):
        """Register a flow class for a flow type"""
        self.flow_registry[flow_type] = flow_class
    
    def start_flow(self, flow_type: str, user_id: str, conversation_id: str, 
                   initial_data: Dict = None) -> FlowResult:
        """Start a new conversation flow"""
        if flow_type not in self.flow_registry:
            return FlowResult(
                success=False,
                message=f"Unknown flow type: {flow_type}"
            )
        
        # End any existing flow for this conversation
        if conversation_id in self.active_flows:
            self.end_flow(conversation_id)
        
        # Create new flow instance
        flow_class = self.flow_registry[flow_type]
        flow = flow_class(flow_type, user_id, conversation_id)
        
        if initial_data:
            flow.collected_data.update(initial_data)
        
        self.active_flows[conversation_id] = flow
        
        return flow.start_flow()
    
    def process_input(self, conversation_id: str, user_input: str) -> FlowResult:
        """Process user input for an active flow"""
        if conversation_id not in self.active_flows:
            return FlowResult(
                success=False,
                message="No active flow for this conversation"
            )
        
        flow = self.active_flows[conversation_id]
        result = flow.advance_step(user_input)
        
        # Remove flow if completed or cancelled
        if flow.state in [FlowState.COMPLETED, FlowState.CANCELLED, FlowState.ERROR]:
            self.end_flow(conversation_id)
        
        return result
    
    def get_active_flow(self, conversation_id: str) -> Optional[BaseFlow]:
        """Get the active flow for a conversation"""
        return self.active_flows.get(conversation_id)
    
    def end_flow(self, conversation_id: str) -> bool:
        """End the active flow for a conversation"""
        if conversation_id in self.active_flows:
            del self.active_flows[conversation_id]
            return True
        return False
    
    def interrupt_flow(self, conversation_id: str, interruption_type: str, 
                      data: Dict = None) -> FlowResult:
        """Interrupt an active flow"""
        if conversation_id not in self.active_flows:
            return FlowResult(
                success=False,
                message="No active flow to interrupt"
            )
        
        flow = self.active_flows[conversation_id]
        if not flow.can_interrupt():
            return FlowResult(
                success=False,
                message="Current flow cannot be interrupted"
            )
        
        return flow.handle_interruption(interruption_type, data)
    
    def get_flow_progress(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get progress information for an active flow"""
        if conversation_id in self.active_flows:
            return self.active_flows[conversation_id].get_progress()
        return None

# Global flow manager instance
flow_manager = FlowManager()

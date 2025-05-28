"""
Task creation conversation flow with step-by-step guidance.
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from django.utils import timezone
from .base import BaseFlow, FlowStep, FlowResult
from ..nlp.entities import entity_extractor
from tasks.models import Task, Project
import logging

logger = logging.getLogger(__name__)

class TaskCreationFlow(BaseFlow):
    """
    Multi-turn conversation flow for creating tasks with guided input collection.
    """
    
    def _define_steps(self) -> List[FlowStep]:
        """Define the steps for task creation"""
        return [
            FlowStep(
                step_id="title",
                prompt="What would you like to call this task? Please provide a title:",
                validation_required=True,
                error_message="Please provide a valid task title. It should be at least 3 characters long."
            ),
            FlowStep(
                step_id="description",
                prompt="Would you like to add a description for this task? (You can type 'skip' if not needed)",
                optional=True,
                error_message="Please provide a description or type 'skip' to continue."
            ),
            FlowStep(
                step_id="due_date",
                prompt="When should this task be completed? You can say 'today', 'tomorrow', a specific date, or 'skip' for no due date:",
                optional=True,
                error_message="Please provide a valid date (like 'tomorrow', '2024-01-15', or 'next week') or type 'skip'."
            ),
            FlowStep(
                step_id="priority",
                prompt="What priority should this task have? Choose from: high, medium, low (or 'skip' for medium priority):",
                optional=True,
                error_message="Please choose 'high', 'medium', 'low', or 'skip' for default priority."
            ),
            FlowStep(
                step_id="project",
                prompt="Should this task be part of a project? Enter the project name or 'skip':",
                optional=True,
                error_message="Please enter a project name or 'skip' to continue."
            ),
            FlowStep(
                step_id="confirmation",
                prompt="",  # Will be dynamically generated
                validation_required=True,
                error_message="Please confirm by saying 'yes' to create the task or 'no' to cancel."
            )
        ]
    
    def process_user_input(self, user_input: str, step_id: str) -> FlowResult:
        """Process user input for each step of task creation"""
        user_input = user_input.strip()
        
        try:
            if step_id == "title":
                return self._process_title(user_input)
            elif step_id == "description":
                return self._process_description(user_input)
            elif step_id == "due_date":
                return self._process_due_date(user_input)
            elif step_id == "priority":
                return self._process_priority(user_input)
            elif step_id == "project":
                return self._process_project(user_input)
            elif step_id == "confirmation":
                return self._process_confirmation(user_input)
            else:
                return FlowResult(
                    success=False,
                    message="Unknown step in task creation flow"
                )
        except Exception as e:
            logger.error(f"Error processing task creation step {step_id}: {e}")
            return FlowResult(
                success=False,
                message="I encountered an error processing your input. Please try again."
            )
    
    def _process_title(self, user_input: str) -> FlowResult:
        """Process task title input"""
        if len(user_input) < 3:
            return FlowResult(
                success=False,
                message="Task title should be at least 3 characters long. Please try again:"
            )
        
        if len(user_input) > 200:
            return FlowResult(
                success=False,
                message="Task title is too long. Please keep it under 200 characters:"
            )
        
        self.collected_data['title'] = user_input
        return FlowResult(
            success=True,
            message="Great! Task title saved.",
            data={'title': user_input}
        )
    
    def _process_description(self, user_input: str) -> FlowResult:
        """Process task description input"""
        if user_input.lower() in ['skip', 'no', 'none', '']:
            self.collected_data['description'] = ''
            return FlowResult(
                success=True,
                message="No description added.",
                data={'description': ''}
            )
        
        if len(user_input) > 2000:
            return FlowResult(
                success=False,
                message="Description is too long. Please keep it under 2000 characters or type 'skip':"
            )
        
        self.collected_data['description'] = user_input
        return FlowResult(
            success=True,
            message="Description saved.",
            data={'description': user_input}
        )
    
    def _process_due_date(self, user_input: str) -> FlowResult:
        """Process due date input"""
        if user_input.lower() in ['skip', 'no', 'none', 'no due date']:
            self.collected_data['due_date'] = None
            return FlowResult(
                success=True,
                message="No due date set.",
                data={'due_date': None}
            )
        
        # Extract date using entity extractor
        entities = entity_extractor.extract_entities(user_input)
        
        if entities['dates']:
            due_date = entities['dates'][0].value
            self.collected_data['due_date'] = due_date
            return FlowResult(
                success=True,
                message=f"Due date set to {due_date.strftime('%Y-%m-%d %H:%M')}.",
                data={'due_date': due_date}
            )
        else:
            return FlowResult(
                success=False,
                message="I couldn't understand that date format. Please try formats like 'tomorrow', '2024-01-15', 'next Friday', or type 'skip':"
            )
    
    def _process_priority(self, user_input: str) -> FlowResult:
        """Process priority input"""
        user_input_lower = user_input.lower().strip()
        
        if user_input_lower in ['skip', 'default', 'medium']:
            self.collected_data['priority'] = 'medium'
            return FlowResult(
                success=True,
                message="Priority set to medium.",
                data={'priority': 'medium'}
            )
        
        # Extract priority using entity extractor
        entities = entity_extractor.extract_entities(user_input)
        
        if entities['priorities']:
            priority = entities['priorities'][0].value
            self.collected_data['priority'] = priority
            return FlowResult(
                success=True,
                message=f"Priority set to {priority}.",
                data={'priority': priority}
            )
        
        # Manual mapping for common inputs
        priority_mapping = {
            'high': 'high',
            'urgent': 'high',
            'important': 'high',
            'critical': 'high',
            'medium': 'medium',
            'normal': 'medium',
            'low': 'low',
            'not urgent': 'low',
            'whenever': 'low'
        }
        
        if user_input_lower in priority_mapping:
            priority = priority_mapping[user_input_lower]
            self.collected_data['priority'] = priority
            return FlowResult(
                success=True,
                message=f"Priority set to {priority}.",
                data={'priority': priority}
            )
        
        return FlowResult(
            success=False,
            message="Please choose 'high', 'medium', 'low', or 'skip' for default priority:"
        )
    
    def _process_project(self, user_input: str) -> FlowResult:
        """Process project input"""
        if user_input.lower() in ['skip', 'no', 'none', 'no project']:
            self.collected_data['project'] = None
            return FlowResult(
                success=True,
                message="Task will not be assigned to a project.",
                data={'project': None}
            )
        
        # Check if project exists
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=self.user_id)
            
            project = Project.objects.filter(
                members=user,
                name__icontains=user_input
            ).first()
            
            if project:
                self.collected_data['project'] = project
                return FlowResult(
                    success=True,
                    message=f"Task will be added to project '{project.name}'.",
                    data={'project': project.name}
                )
            else:
                # Ask if they want to create a new project
                self.collected_data['new_project_name'] = user_input
                return FlowResult(
                    success=True,
                    message=f"Project '{user_input}' doesn't exist. I'll create it for you.",
                    data={'project': user_input, 'create_new': True}
                )
        except Exception as e:
            logger.error(f"Error checking project: {e}")
            return FlowResult(
                success=False,
                message="I had trouble checking your projects. Please try again or type 'skip':"
            )
    
    def _process_confirmation(self, user_input: str) -> FlowResult:
        """Process confirmation input"""
        user_input_lower = user_input.lower().strip()
        
        if user_input_lower in ['yes', 'y', 'confirm', 'create', 'ok', 'okay', 'sure']:
            return FlowResult(
                success=True,
                message="Task creation confirmed!",
                data={'confirmed': True}
            )
        elif user_input_lower in ['no', 'n', 'cancel', 'abort', 'stop']:
            return FlowResult(
                success=False,
                message="Task creation cancelled.",
                data={'confirmed': False}
            )
        else:
            return FlowResult(
                success=False,
                message="Please confirm by saying 'yes' to create the task or 'no' to cancel:"
            )
    
    def advance_step(self, user_input: str) -> FlowResult:
        """Override to handle confirmation step prompt generation"""
        # Handle confirmation step specially
        if (self.current_step == len(self.steps) - 1 and 
            self.steps[self.current_step].step_id == "confirmation"):
            
            # Generate confirmation prompt
            confirmation_prompt = self._generate_confirmation_prompt()
            self.steps[self.current_step].prompt = confirmation_prompt
        
        return super().advance_step(user_input)
    
    def _generate_confirmation_prompt(self) -> str:
        """Generate a confirmation prompt with task details"""
        prompt = "Please review your task details:\n\n"
        prompt += f"**Title:** {self.collected_data.get('title', 'N/A')}\n"
        
        if self.collected_data.get('description'):
            prompt += f"**Description:** {self.collected_data['description']}\n"
        
        if self.collected_data.get('due_date'):
            due_date = self.collected_data['due_date']
            prompt += f"**Due Date:** {due_date.strftime('%Y-%m-%d %H:%M')}\n"
        
        priority = self.collected_data.get('priority', 'medium')
        prompt += f"**Priority:** {priority.capitalize()}\n"
        
        if self.collected_data.get('project'):
            if isinstance(self.collected_data['project'], str):
                prompt += f"**Project:** {self.collected_data['project']} (new)\n"
            else:
                prompt += f"**Project:** {self.collected_data['project'].name}\n"
        
        prompt += "\nWould you like to create this task? (yes/no)"
        return prompt
    
    def _on_flow_complete(self) -> FlowResult:
        """Create the actual task when flow is completed"""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=self.user_id)
            
            # Handle project creation if needed
            project = None
            if self.collected_data.get('new_project_name'):
                project = Project.objects.create(
                    name=self.collected_data['new_project_name'],
                    description=f"Auto-created project for task: {self.collected_data['title']}"
                )
                project.members.add(user)
            elif self.collected_data.get('project') and not isinstance(self.collected_data['project'], str):
                project = self.collected_data['project']
            
            # Create the task
            task = Task.objects.create(
                title=self.collected_data['title'],
                description=self.collected_data.get('description', ''),
                due_date=self.collected_data.get('due_date'),
                priority=self.collected_data.get('priority', 'medium'),
                project=project,
                owner=user,
                status='todo'
            )
            
            # Add user as assignee
            task.assignees.add(user)
            
            # Create task activity
            try:
                from tasks.models import TaskActivity
                TaskActivity.objects.create(
                    task=task,
                    activity_type='create',
                    user=user,
                    description=f"Task '{task.title}' created via chatbot flow"
                )
            except Exception as e:
                logger.warning(f"Failed to create task activity: {e}")
            
            success_message = f"✅ Task '{task.title}' created successfully!"
            
            if project:
                success_message += f" It has been added to project '{project.name}'."
            
            if task.due_date:
                success_message += f" Due date: {task.due_date.strftime('%Y-%m-%d %H:%M')}."
            
            success_message += "\n\nYou can view and manage this task in your task dashboard."
            
            return FlowResult(
                success=True,
                message=success_message,
                data={'task_id': str(task.id), 'task_title': task.title}
            )
            
        except Exception as e:
            logger.error(f"Error creating task in flow: {e}")
            return FlowResult(
                success=False,
                message=f"I'm sorry, there was an error creating your task: {str(e)}. Please try again or use the main interface."
            )
    
    def can_interrupt(self) -> bool:
        """Task creation can be interrupted and resumed"""
        return True
    
    def handle_interruption(self, interruption_type: str, data: Dict = None) -> FlowResult:
        """Handle flow interruption gracefully"""
        if interruption_type == "urgent_request":
            return FlowResult(
                success=True,
                message="I'll save your progress on this task. We can continue creating it after I help with your urgent request."
            )
        elif interruption_type == "user_cancel":
            return FlowResult(
                success=False,
                message="Task creation cancelled. Your progress has been discarded."
            )
        else:
            return FlowResult(
                success=True,
                message="Task creation paused. We can continue where we left off when you're ready."
            )

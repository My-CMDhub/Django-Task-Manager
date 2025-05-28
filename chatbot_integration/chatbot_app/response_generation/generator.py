"""
Enhanced response generation system with context awareness and personalization.
"""

import random
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from django.utils import timezone
from django.conf import settings
import pytz
import httpx
import json
import os

from ..nlp.intents import Intent
from ..nlp.entities import Entity
from ..nlp.context import conversation_manager
from ..flows.base import flow_manager
from tasks.models import Task, Project

logger = logging.getLogger(__name__)

class ResponseGenerator:
    """
    Enhanced response generation system with context awareness, personalization,
    and intelligent response selection.
    """
    
    def __init__(self):
        self.timezone = pytz.timezone('Australia/Melbourne')
        self._load_response_templates()
        
    def _load_response_templates(self):
        """Load response templates for different intents and scenarios"""
        self.templates = {
            'greeting': {
                'morning': [
                    "Good morning! ☀️ Ready to tackle today's tasks?",
                    "Morning! Hope you're having a great start to your day. How can I help?",
                    "Good morning! Let's make today productive together.",
                    "Rise and shine! 🌅 What's on your task list today?"
                ],
                'afternoon': [
                    "Good afternoon! 🌤️ How's your day going so far?",
                    "Afternoon! Making good progress today? How can I assist?",
                    "Good afternoon! Ready to tackle the rest of your day?",
                    "Hi there! Hope your afternoon is productive. What can I help with?"
                ],
                'evening': [
                    "Good evening! 🌙 How did your day go?",
                    "Evening! Time to wrap up or plan for tomorrow?",
                    "Good evening! Let's review what you've accomplished today.",
                    "Hi! Hope you had a productive day. How can I help you wind down?"
                ],
                'general': [
                    "Hello! I'm here to help you manage your tasks and stay organized.",
                    "Hi there! Ready to boost your productivity today?",
                    "Greetings! How can I assist with your task management?",
                    "Hello! What would you like to accomplish today?"
                ]
            },
            'farewell': [
                "Goodbye! Have a productive day! 👋",
                "Take care! Your tasks will be here when you return.",
                "Until next time! Keep up the great work! ✨",
                "Goodbye! Remember to take breaks between tasks.",
                "See you later! May your tasks be ever in your favor! 🎯"
            ],
            'thanks': [
                "You're welcome! Happy to help! 😊",
                "Glad I could assist! Anything else you need?",
                "No problem at all! I'm here whenever you need task help.",
                "You're very welcome! Keep being productive! ⭐",
                "Anytime! That's what I'm here for."
            ],
            'error': [
                "I'm having trouble understanding that. Could you rephrase it?",
                "Sorry, I didn't quite catch that. Could you try again?",
                "I'm not sure what you mean. Can you be more specific?",
                "Could you clarify what you're looking for?",
                "I didn't understand that. Maybe try asking differently?"
            ],
            'task_not_found': [
                "I couldn't find that task. Could you check the name?",
                "That task doesn't seem to exist. Want to try a different name?",
                "I don't see a task with that name. Could you be more specific?",
                "No matching task found. Maybe it has a different name?"
            ],
            'no_tasks': [
                "You don't have any tasks yet. Ready to create your first one?",
                "Your task list is empty! Perfect time for a fresh start.",
                "No tasks found. Feeling productive? Let's create something!",
                "Clean slate! No tasks to show. Want to add one?"
            ],
            'task_completed': [
                "🎉 Excellent work! Task marked as complete!",
                "✅ Well done! Another task off your list!",
                "🌟 Great job! You're making excellent progress!",
                "💪 Task completed! You're on fire today!",
                "🎯 Nice work! Keep up the momentum!"
            ],
            'help': [
                "I can help you manage tasks, projects, and stay organized! Here's what I can do:",
                "I'm your productivity assistant! Here are my capabilities:",
                "Great question! I can help you with several things:",
                "I'm here to boost your productivity! I can assist with:"
            ]
        }
        
        self.help_content = [
            "📋 **Task Management**: Create, view, update, and complete tasks",
            "📊 **Progress Tracking**: See your productivity statistics and summaries",
            "🗂️ **Project Organization**: Manage projects and organize your work",
            "🔍 **Smart Search**: Find tasks and projects with natural language",
            "⏰ **Due Date Management**: Track deadlines and overdue items",
            "🎯 **Priority Management**: Set and manage task priorities",
            "",
            "Just ask me naturally! For example:",
            "• 'Show my tasks for today'",
            "• 'Create a new task'",
            "• 'Mark task as complete'",
            "• 'What's my progress this week?'"
        ]
    
    def generate_response(self, user_message: str, intent: Intent, entities: Dict[str, List[Entity]], 
                         user, conversation_id: str, context: Dict = None) -> str:
        """
        Generate an appropriate response based on intent, entities, and context.
        
        Args:
            user_message: The user's original message
            intent: Detected intent
            entities: Extracted entities
            user: Django user object
            conversation_id: Conversation identifier
            context: Additional context information
            
        Returns:
            Generated response string
        """
        try:
            # Handle conversation flows first
            active_flow = flow_manager.get_active_flow(conversation_id)
            if active_flow:
                return self._handle_flow_response(user_message, active_flow)
            
            # Handle intents based on primary and secondary classification
            if intent.primary == "greeting":
                return self._handle_greeting(intent, user, context)
            elif intent.primary == "farewell":
                return self._handle_farewell(intent, user)
            elif intent.primary == "acknowledgment":
                return self._handle_acknowledgment(intent, user)
            elif intent.primary == "task":
                return self._handle_task_intent(intent, entities, user, conversation_id, user_message)
            elif intent.primary == "project":
                return self._handle_project_intent(intent, entities, user, conversation_id, user_message)
            elif intent.primary == "statistics":
                return self._handle_statistics_intent(intent, user)
            elif intent.primary == "help":
                return self._handle_help_intent(intent, user)
            elif intent.primary == "question":
                return self._handle_question_intent(intent, user_message, user)
            else:
                return self._handle_unknown_intent(user_message, user, conversation_id)
                
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return "I encountered an error processing your request. Please try again."
    
    def _handle_flow_response(self, user_message: str, flow) -> str:
        """Handle response when a conversation flow is active"""
        try:
            result = flow_manager.process_input(flow.conversation_id, user_message)
            return result.message
        except Exception as e:
            logger.error(f"Error handling flow response: {e}")
            return "I encountered an error in our conversation flow. Let's start over."
    
    def _handle_greeting(self, intent: Intent, user, context: Dict = None) -> str:
        """Handle greeting intents with time-aware responses"""
        now = timezone.now().astimezone(self.timezone)
        hour = now.hour
        
        # Determine time of day
        if 5 <= hour < 12:
            time_period = 'morning'
        elif 12 <= hour < 17:
            time_period = 'afternoon'
        elif 17 <= hour < 22:
            time_period = 'evening'
        else:
            time_period = 'general'
        
        # Get base greeting
        if time_period in self.templates['greeting']:
            base_response = random.choice(self.templates['greeting'][time_period])
        else:
            base_response = random.choice(self.templates['greeting']['general'])
        
        # Add personalized task information
        try:
            pending_tasks = Task.objects.filter(
                models.Q(owner=user) | models.Q(assignees=user),
                ~models.Q(status='completed')
            ).distinct().count()
            
            due_today = Task.objects.filter(
                models.Q(owner=user) | models.Q(assignees=user),
                ~models.Q(status='completed'),
                due_date__date=now.date()
            ).distinct().count()
            
            if due_today > 0:
                base_response += f" You have {due_today} task{'s' if due_today != 1 else ''} due today."
            elif pending_tasks > 0:
                base_response += f" You have {pending_tasks} pending task{'s' if pending_tasks != 1 else ''}."
            else:
                base_response += " Your task list is all caught up! 🎉"
                
        except Exception as e:
            logger.warning(f"Could not add task info to greeting: {e}")
        
        return base_response
    
    def _handle_farewell(self, intent: Intent, user) -> str:
        """Handle farewell intents"""
        return random.choice(self.templates['farewell'])
    
    def _handle_acknowledgment(self, intent: Intent, user) -> str:
        """Handle acknowledgment intents like thanks"""
        if intent.secondary == "thanks":
            return random.choice(self.templates['thanks'])
        elif intent.secondary == "affirmation":
            return "Great! How else can I help you?"
        elif intent.secondary == "negation":
            return "No problem! Let me know if you need anything else."
        else:
            return "I appreciate that! How can I assist you further?"
    
    def _handle_task_intent(self, intent: Intent, entities: Dict, user, conversation_id: str, user_message: str) -> str:
        """Handle task-related intents"""
        from django.db import models
        
        if intent.secondary == "create":
            return self._start_task_creation_flow(conversation_id, user.id, entities)
        elif intent.secondary == "list":
            return self._handle_task_list(entities, user, user_message)
        elif intent.secondary == "complete":
            return self._handle_task_completion(entities, user, user_message)
        elif intent.secondary == "delete":
            return "For security reasons, I recommend using the main interface to delete tasks. Would you like me to show you your current tasks instead?"
        elif intent.secondary == "search":
            return self._handle_task_search(entities, user, user_message)
        else:
            return "I can help you with tasks! You can create, view, complete, or search for tasks. What would you like to do?"
    
    def _handle_project_intent(self, intent: Intent, entities: Dict, user, conversation_id: str, user_message: str) -> str:
        """Handle project-related intents"""
        if intent.secondary == "create":
            return "I'd love to help you create a project! For the best experience with all available options, please use the 'Create Project' feature in the main interface."
        elif intent.secondary == "list":
            return self._handle_project_list(entities, user)
        elif intent.secondary == "status":
            return self._handle_project_status(entities, user)
        else:
            return "I can help you with projects! You can view project lists, check status, or get project information. What would you like to know?"
    
    def _handle_statistics_intent(self, intent: Intent, user) -> str:
        """Handle statistics and dashboard requests"""
        try:
            from django.db import models
            
            # Get comprehensive statistics
            all_tasks = Task.objects.filter(
                models.Q(owner=user) | models.Q(assignees=user)
            ).distinct()
            
            completed_tasks = all_tasks.filter(status='completed')
            pending_tasks = all_tasks.exclude(status='completed')
            
            now = timezone.now()
            overdue_tasks = pending_tasks.filter(due_date__lt=now)
            due_today = pending_tasks.filter(due_date__date=now.date())
            
            projects = Project.objects.filter(members=user)
            
            response = "📊 **Your Productivity Dashboard**\n\n"
            response += "**Tasks Overview:**\n"
            response += f"• Total tasks: {all_tasks.count()}\n"
            response += f"• Completed: {completed_tasks.count()}\n"
            response += f"• Pending: {pending_tasks.count()}\n"
            
            if overdue_tasks.exists():
                response += f"• Overdue: {overdue_tasks.count()}\n"
            
            if due_today.exists():
                response += f"• Due today: {due_today.count()}\n"
            
            if projects.exists():
                response += f"\n**Projects:** {projects.count()} total\n"
            
            # Add completion rate
            if all_tasks.count() > 0:
                completion_rate = (completed_tasks.count() / all_tasks.count()) * 100
                response += f"\n**Completion Rate:** {completion_rate:.1f}%"
            
            # Add encouragement
            if completion_rate >= 80:
                response += " 🌟 Excellent work!"
            elif completion_rate >= 60:
                response += " 💪 Great progress!"
            elif completion_rate >= 40:
                response += " 📈 Keep it up!"
            
            return response
            
        except Exception as e:
            logger.error(f"Error generating statistics: {e}")
            return "I encountered an issue retrieving your statistics. Please try again."
    
    def _handle_help_intent(self, intent: Intent, user) -> str:
        """Handle help requests"""
        base_response = random.choice(self.templates['help'])
        help_text = "\n\n" + "\n".join(self.help_content)
        return base_response + help_text
    
    def _handle_question_intent(self, intent: Intent, user_message: str, user) -> str:
        """Handle question intents"""
        if intent.secondary == "status":
            return "I'm doing great and ready to help you be productive! How are you doing with your tasks today?"
        elif intent.secondary == "capability":
            return self._handle_help_intent(intent, user)
        else:
            return self._generate_ai_response(user_message, user)
    
    def _handle_unknown_intent(self, user_message: str, user, conversation_id: str) -> str:
        """Handle unknown intents with AI fallback"""
        # Try to generate an intelligent response using AI
        return self._generate_ai_response(user_message, user, conversation_id)
    
    def _start_task_creation_flow(self, conversation_id: str, user_id: str, entities: Dict) -> str:
        """Start the task creation conversation flow"""
        try:
            from ..flows.task_creation import TaskCreationFlow
            
            # Register the flow if not already registered
            if 'task_creation' not in flow_manager.flow_registry:
                flow_manager.register_flow('task_creation', TaskCreationFlow)
            
            # Extract any initial data from entities
            initial_data = {}
            if entities.get('dates'):
                initial_data['due_date'] = entities['dates'][0].value
            if entities.get('priorities'):
                initial_data['priority'] = entities['priorities'][0].value
            
            result = flow_manager.start_flow('task_creation', user_id, conversation_id, initial_data)
            return result.message
            
        except Exception as e:
            logger.error(f"Error starting task creation flow: {e}")
            return "I'd love to help you create a task! For now, please use the 'Add Task' button in the main interface for the full experience."
    
    def _handle_task_list(self, entities: Dict, user, user_message: str) -> str:
        """Handle task listing requests"""
        try:
            from django.db import models
            
            # Start with all user's tasks
            tasks = Task.objects.filter(
                models.Q(owner=user) | models.Q(assignees=user)
            ).distinct()
            
            filter_description = "all"
            
            # Apply filters based on entities and message content
            message_lower = user_message.lower()
            
            if any(word in message_lower for word in ['pending', 'incomplete', 'todo', 'active']):
                tasks = tasks.exclude(status='completed')
                filter_description = "pending"
            elif any(word in message_lower for word in ['completed', 'done', 'finished']):
                tasks = tasks.filter(status='completed')
                filter_description = "completed"
            elif any(word in message_lower for word in ['overdue', 'late', 'past due']):
                tasks = tasks.filter(due_date__lt=timezone.now()).exclude(status='completed')
                filter_description = "overdue"
            elif any(word in message_lower for word in ['today', 'due today']):
                tasks = tasks.filter(due_date__date=timezone.now().date()).exclude(status='completed')
                filter_description = "due today"
            elif any(word in message_lower for word in ['high priority', 'urgent', 'important']):
                tasks = tasks.filter(priority='high')
                filter_description = "high priority"
            
            if not tasks.exists():
                if filter_description == "all":
                    return random.choice(self.templates['no_tasks'])
                else:
                    return f"You don't have any {filter_description} tasks at the moment."
            
            # Format response
            response = f"Here are your {filter_description} tasks:\n\n"
            
            # Show up to 10 tasks
            display_tasks = tasks[:10]
            for i, task in enumerate(display_tasks, 1):
                due_info = f" (Due: {task.due_date.strftime('%b %d')})" if task.due_date else ""
                priority_info = f" [{task.priority.upper()}]" if task.priority != 'medium' else ""
                status_info = f" - {task.get_status_display()}" if hasattr(task, 'get_status_display') else ""
                
                response += f"{i}. {task.title}{due_info}{priority_info}{status_info}\n"
            
            if tasks.count() > 10:
                response += f"\n(Showing 10 of {tasks.count()} {filter_description} tasks)"
            
            return response
            
        except Exception as e:
            logger.error(f"Error handling task list: {e}")
            return "I encountered an issue retrieving your tasks. Please try again."
    
    def _handle_task_completion(self, entities: Dict, user, user_message: str) -> str:
        """Handle task completion requests"""
        try:
            from django.db import models
            
            # Try to find the specific task mentioned
            task_names = [entity.value for entity in entities.get('tasks', [])]
            
            if task_names:
                # Look for the specific task
                for task_name in task_names:
                    tasks = Task.objects.filter(
                        models.Q(owner=user) | models.Q(assignees=user),
                        title__icontains=task_name
                    ).exclude(status='completed')
                    
                    if tasks.count() == 1:
                        task = tasks.first()
                        task.status = 'completed'
                        if hasattr(task, 'completed_at'):
                            task.completed_at = timezone.now()
                        task.save()
                        
                        return random.choice(self.templates['task_completed']) + f"\n\nTask '{task.title}' is now complete!"
                    elif tasks.count() > 1:
                        task_list = [f"• {t.title}" for t in tasks[:5]]
                        return f"I found multiple tasks matching '{task_name}'. Which one did you complete?\n\n" + "\n".join(task_list)
                    else:
                        return f"I couldn't find an incomplete task named '{task_name}'. Could you check the name?"
            
            # No specific task mentioned - ask for clarification
            incomplete_tasks = Task.objects.filter(
                models.Q(owner=user) | models.Q(assignees=user)
            ).exclude(status='completed').distinct()
            
            if not incomplete_tasks.exists():
                return "Great news! You don't have any incomplete tasks. Everything is done! 🎉"
            elif incomplete_tasks.count() == 1:
                task = incomplete_tasks.first()
                task.status = 'completed'
                if hasattr(task, 'completed_at'):
                    task.completed_at = timezone.now()
                task.save()
                
                return random.choice(self.templates['task_completed']) + f"\n\nYour task '{task.title}' is now complete!"
            else:
                task_list = [f"• {task.title}" for task in incomplete_tasks[:7]]
                return f"Which task did you complete? Here are your incomplete tasks:\n\n" + "\n".join(task_list) + "\n\nJust tell me the task name!"
                
        except Exception as e:
            logger.error(f"Error handling task completion: {e}")
            return "I encountered an issue marking the task as complete. Please try again."
    
    def _handle_task_search(self, entities: Dict, user, user_message: str) -> str:
        """Handle task search requests"""
        # Extract search terms from the message
        search_terms = []
        
        # Look for quoted terms
        import re
        quoted_terms = re.findall(r'"([^"]*)"', user_message)
        search_terms.extend(quoted_terms)
        
        # If no quoted terms, extract keywords after common search phrases
        if not search_terms:
            search_patterns = [
                r'(?:search for|find|look for|about|containing)\s+(.+?)(?:\s+(?:in|among|from)|$)',
                r'tasks?\s+(?:with|about|containing|related to)\s+(.+?)(?:\s|$)'
            ]
            
            for pattern in search_patterns:
                match = re.search(pattern, user_message.lower())
                if match:
                    search_terms.append(match.group(1).strip())
                    break
        
        if not search_terms:
            return "What would you like to search for in your tasks? Please be more specific."
        
        try:
            from django.db import models
            
            # Search in task titles and descriptions
            search_term = search_terms[0]
            matching_tasks = Task.objects.filter(
                models.Q(owner=user) | models.Q(assignees=user),
                models.Q(title__icontains=search_term) | models.Q(description__icontains=search_term)
            ).distinct()
            
            if not matching_tasks.exists():
                return f"I couldn't find any tasks containing '{search_term}'. Try a different search term?"
            
            response = f"Found {matching_tasks.count()} task{'s' if matching_tasks.count() != 1 else ''} matching '{search_term}':\n\n"
            
            for i, task in enumerate(matching_tasks[:8], 1):
                status_info = f" [{task.get_status_display()}]" if hasattr(task, 'get_status_display') else f" [{task.status}]"
                response += f"{i}. {task.title}{status_info}\n"
            
            if matching_tasks.count() > 8:
                response += f"\n(Showing 8 of {matching_tasks.count()} matches)"
            
            return response
            
        except Exception as e:
            logger.error(f"Error handling task search: {e}")
            return "I encountered an issue searching your tasks. Please try again."
    
    def _handle_project_list(self, entities: Dict, user) -> str:
        """Handle project listing requests"""
        try:
            projects = Project.objects.filter(members=user)
            
            if not projects.exists():
                return "You don't have any projects yet. Ready to create your first one?"
            
            response = f"Here are your {projects.count()} project{'s' if projects.count() != 1 else ''}:\n\n"
            
            for i, project in enumerate(projects[:10], 1):
                # Get task count for each project
                try:
                    task_count = Task.objects.filter(project=project).count()
                    completed_count = Task.objects.filter(project=project, status='completed').count()
                    progress = f" ({completed_count}/{task_count} tasks)" if task_count > 0 else " (no tasks)"
                except:
                    progress = ""
                
                response += f"{i}. {project.name}{progress}\n"
            
            if projects.count() > 10:
                response += f"\n(Showing 10 of {projects.count()} projects)"
            
            return response
            
        except Exception as e:
            logger.error(f"Error handling project list: {e}")
            return "I encountered an issue retrieving your projects. Please try again."
    
    def _handle_project_status(self, entities: Dict, user) -> str:
        """Handle project status requests"""
        try:
            projects = Project.objects.filter(members=user)
            
            if not projects.exists():
                return "You don't have any projects to check status for."
            
            response = "📊 **Project Status Overview:**\n\n"
            
            for project in projects[:5]:
                try:
                    all_tasks = Task.objects.filter(project=project)
                    completed_tasks = all_tasks.filter(status='completed')
                    
                    if all_tasks.count() > 0:
                        progress_percent = (completed_tasks.count() / all_tasks.count()) * 100
                        progress_bar = "█" * int(progress_percent // 10) + "░" * (10 - int(progress_percent // 10))
                        
                        response += f"**{project.name}**\n"
                        response += f"Progress: {progress_bar} {progress_percent:.1f}%\n"
                        response += f"Tasks: {completed_tasks.count()}/{all_tasks.count()} completed\n\n"
                    else:
                        response += f"**{project.name}**\n"
                        response += "No tasks yet\n\n"
                        
                except Exception as e:
                    logger.warning(f"Error calculating project status for {project.name}: {e}")
                    response += f"**{project.name}**\n"
                    response += "Status unavailable\n\n"
            
            if projects.count() > 5:
                response += f"(Showing 5 of {projects.count()} projects)"
            
            return response
            
        except Exception as e:
            logger.error(f"Error handling project status: {e}")
            return "I encountered an issue retrieving project status. Please try again."
    
    def _generate_ai_response(self, user_message: str, user, conversation_id: str = None) -> str:
        """Generate AI response using external API as fallback"""
        try:
            # Get user context data
            from ..utils import get_user_context_data
            user_context = get_user_context_data(user=user, query=user_message)
            
            # System message for the AI
            system_message = {
                "role": "system",
                "content": f"""You are TaskBuddy, a helpful and friendly task management assistant. You help users manage their tasks and projects with a positive, encouraging attitude.

Your capabilities:
- Help users understand their tasks and projects
- Provide insights about productivity and task management
- Answer questions about the task management system
- Give encouraging and supportive responses

IMPORTANT RULES:
1. NEVER create, update, or delete tasks/projects - always direct users to use the main interface
2. Be friendly, encouraging, and solution-oriented
3. Keep responses concise but helpful
4. Use the provided user context to give personalized responses
5. If you don't know something specific about their tasks, ask them to be more specific

User Context:
{user_context}

Respond in a helpful, encouraging way that makes the user feel supported in their productivity journey."""
            }
            
            # User message
            user_msg = {
                "role": "user", 
                "content": user_message
            }
            
            # Call Mistral AI
            mistral_api_key = getattr(settings, 'MISTRAL_API_KEY', os.environ.get("MISTRAL_API_KEY"))
            if not mistral_api_key:
                return "I'd love to help, but I'm having trouble with my AI capabilities right now. Could you try asking about your tasks or projects in a simpler way?"
            
            headers = {
                "Authorization": f"Bearer {mistral_api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "mistral-small-latest",
                "messages": [system_message, user_msg],
                "max_tokens": 300,
                "temperature": 0.7
            }
            
            with httpx.Client(timeout=30.0) as client:
                response = client.post("https://api.mistral.ai/v1/chat/completions", headers=headers, json=payload)
                response.raise_for_status()
                
                response_data = response.json()
                ai_response = response_data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
                
                if ai_response:
                    return ai_response
                else:
                    return "I'm having trouble generating a response right now. Could you try rephrasing your question?"
                    
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return random.choice(self.templates['error'])

# Global response generator instance
response_generator = ResponseGenerator()

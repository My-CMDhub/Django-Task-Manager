"""
Intent recognition system for the chatbot.
Implements hierarchical intent classification with fuzzy matching and confidence scoring.
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from fuzzywuzzy import fuzz
import logging

logger = logging.getLogger(__name__)

@dataclass
class Intent:
    """Represents a detected intent with confidence score"""
    primary: str
    secondary: Optional[str] = None
    confidence: float = 0.0
    matched_pattern: Optional[str] = None
    entities: Dict = None
    
    def __post_init__(self):
        if self.entities is None:
            self.entities = {}

class IntentClassifier:
    """
    Hierarchical intent classification system with fuzzy matching capabilities.
    """
    
    def __init__(self):
        self.intents = self._load_intent_hierarchy()
        self.pattern_cache = {}
        
    def _load_intent_hierarchy(self) -> Dict:
        """Load the hierarchical intent structure"""
        return {
            "greeting": {
                "general": [
                    "hello", "hi", "hey", "howdy", "greetings", "good morning", 
                    "good afternoon", "good evening", "good day", "hiya", "heya"
                ],
                "casual": ["yo", "sup", "what's up", "whats up", "wassup"],
                "polite": ["good to see you", "nice to see you", "hope you're well"]
            },
            "farewell": {
                "general": ["bye", "goodbye", "see you", "farewell", "cya", "talk to you later", "ttyl"],
                "gratitude": ["thanks bye", "thank you goodbye", "thanks and bye"],
                "departure": ["have to go", "going now", "leaving", "I'm off"]
            },
            "task": {
                "create": [
                    "create task", "add task", "make task", "new task", "start task",
                    "create a task", "add a task", "make a task", "new task for",
                    "i need to create", "i want to add", "please create", "could you create"
                ],
                "list": [
                    "show tasks", "list tasks", "my tasks", "view tasks", "display tasks",
                    "what tasks", "which tasks", "task list", "tasks overview",
                    "tell me about my tasks", "show me my tasks"
                ],
                "update": [
                    "update task", "modify task", "edit task", "change task",
                    "update the task", "modify the task", "change the task"
                ],
                "delete": [
                    "delete task", "remove task", "cancel task", "get rid of task",
                    "delete the task", "remove the task", "trash task"
                ],
                "complete": [
                    "complete task", "finish task", "mark task done", "mark complete",
                    "task completed", "finished task", "done with task", "mark as complete"
                ],
                "search": [
                    "find task", "search task", "look for task", "search for",
                    "find tasks with", "tasks containing", "tasks about"
                ]
            },
            "project": {
                "create": [
                    "create project", "add project", "make project", "new project", "start project"
                ],
                "list": [
                    "show projects", "list projects", "my projects", "view projects",
                    "what projects", "project list", "projects overview"
                ],
                "update": ["update project", "modify project", "edit project", "change project"],
                "delete": ["delete project", "remove project", "cancel project"],
                "status": ["project status", "project progress", "how is project"]
            },
            "statistics": {
                "general": [
                    "statistics", "stats", "dashboard", "overview", "summary",
                    "my progress", "how am i doing", "productivity report"
                ],
                "tasks": [
                    "task statistics", "task stats", "how many tasks", "task count",
                    "task summary", "task status"
                ],
                "projects": [
                    "project statistics", "project stats", "how many projects",
                    "project count", "project summary"
                ]
            },
            "help": {
                "general": [
                    "help", "what can you do", "how do you work", "commands",
                    "what are your features", "how to use"
                ],
                "specific": [
                    "help with tasks", "help with projects", "how to create task",
                    "how to create project"
                ]
            },
            "acknowledgment": {
                "thanks": [
                    "thank you", "thanks", "ty", "thx", "thank you very much",
                    "thanks a lot", "much appreciated", "appreciate it"
                ],
                "affirmation": ["yes", "yeah", "yep", "ok", "okay", "sure", "alright"],
                "negation": ["no", "nope", "not really", "no thanks"]
            },
            "question": {
                "status": ["how are you", "how's it going", "how you doing", "how are things"],
                "capability": ["what can you do", "what are you", "who are you"],
                "clarification": ["what do you mean", "can you explain", "i don't understand"]
            }
        }
    
    def classify(self, message: str) -> Intent:
        """
        Classify the intent of a message with confidence scoring.
        
        Args:
            message: The user's message
            
        Returns:
            Intent object with primary/secondary classification and confidence
        """
        message = message.lower().strip()
        
        if not message:
            return Intent("unknown", confidence=0.0)
        
        # Check cache first
        cache_key = message
        if cache_key in self.pattern_cache:
            return self.pattern_cache[cache_key]
        
        best_match = Intent("unknown", confidence=0.0)
        
        # Direct pattern matching first (highest confidence)
        for primary_intent, secondary_intents in self.intents.items():
            for secondary_intent, patterns in secondary_intents.items():
                for pattern in patterns:
                    # Exact match
                    if message == pattern:
                        intent = Intent(
                            primary=primary_intent,
                            secondary=secondary_intent,
                            confidence=1.0,
                            matched_pattern=pattern
                        )
                        self.pattern_cache[cache_key] = intent
                        return intent
                    
                    # Contains match
                    if pattern in message:
                        confidence = 0.9 if len(pattern.split()) > 1 else 0.7
                        if confidence > best_match.confidence:
                            best_match = Intent(
                                primary=primary_intent,
                                secondary=secondary_intent,
                                confidence=confidence,
                                matched_pattern=pattern
                            )
        
        # Fuzzy matching for partial matches
        if best_match.confidence < 0.8:
            fuzzy_match = self._fuzzy_match(message)
            if fuzzy_match.confidence > best_match.confidence:
                best_match = fuzzy_match
        
        # Context-based classification for ambiguous cases
        if best_match.confidence < 0.6:
            context_match = self._classify_by_context(message)
            if context_match.confidence > best_match.confidence:
                best_match = context_match
        
        # Cache the result
        self.pattern_cache[cache_key] = best_match
        
        return best_match
    
    def _fuzzy_match(self, message: str) -> Intent:
        """Perform fuzzy string matching for similar intents"""
        best_match = Intent("unknown", confidence=0.0)
        
        for primary_intent, secondary_intents in self.intents.items():
            for secondary_intent, patterns in secondary_intents.items():
                for pattern in patterns:
                    # Calculate fuzzy ratio
                    ratio = fuzz.ratio(message, pattern) / 100.0
                    partial_ratio = fuzz.partial_ratio(message, pattern) / 100.0
                    token_ratio = fuzz.token_sort_ratio(message, pattern) / 100.0
                    
                    # Use the best fuzzy matching score
                    fuzzy_confidence = max(ratio, partial_ratio, token_ratio)
                    
                    # Apply threshold and scaling
                    if fuzzy_confidence > 0.75:  # Minimum threshold for fuzzy matching
                        scaled_confidence = fuzzy_confidence * 0.8  # Scale down fuzzy matches
                        
                        if scaled_confidence > best_match.confidence:
                            best_match = Intent(
                                primary=primary_intent,
                                secondary=secondary_intent,
                                confidence=scaled_confidence,
                                matched_pattern=pattern
                            )
        
        return best_match
    
    def _classify_by_context(self, message: str) -> Intent:
        """Classify intent based on contextual clues and keywords"""
        
        # Task-related keywords
        task_keywords = ["task", "todo", "to do", "assignment", "work", "job"]
        project_keywords = ["project", "initiative", "effort", "plan"]
        action_keywords = {
            "create": ["create", "add", "make", "new", "start", "begin"],
            "delete": ["delete", "remove", "cancel", "trash", "get rid"],
            "update": ["update", "modify", "change", "edit", "alter"],
            "list": ["show", "list", "view", "display", "see"],
            "complete": ["complete", "finish", "done", "finished", "completed"]
        }
        
        # Check for task or project context
        has_task_context = any(keyword in message for keyword in task_keywords)
        has_project_context = any(keyword in message for keyword in project_keywords)
        
        # Check for action context
        detected_action = None
        for action, keywords in action_keywords.items():
            if any(keyword in message for keyword in keywords):
                detected_action = action
                break
        
        # Determine intent based on context
        if has_task_context and detected_action:
            return Intent(
                primary="task",
                secondary=detected_action,
                confidence=0.6,
                matched_pattern=f"context: task + {detected_action}"
            )
        elif has_project_context and detected_action:
            return Intent(
                primary="project", 
                secondary=detected_action,
                confidence=0.6,
                matched_pattern=f"context: project + {detected_action}"
            )
        elif detected_action:
            # Default to task if action is detected but no specific context
            return Intent(
                primary="task",
                secondary=detected_action,
                confidence=0.5,
                matched_pattern=f"context: action {detected_action}"
            )
        
        # Question detection
        question_indicators = ["what", "how", "why", "when", "where", "who", "which", "?"]
        if any(indicator in message for indicator in question_indicators):
            return Intent(
                primary="question",
                secondary="general",
                confidence=0.5,
                matched_pattern="context: question"
            )
        
        return Intent("unknown", confidence=0.0)
    
    def get_similar_intents(self, intent: Intent, threshold: float = 0.7) -> List[Intent]:
        """Get similar intents for suggestion purposes"""
        similar = []
        
        for primary_intent, secondary_intents in self.intents.items():
            for secondary_intent, patterns in secondary_intents.items():
                for pattern in patterns:
                    # Skip the exact match
                    if (primary_intent == intent.primary and 
                        secondary_intent == intent.secondary):
                        continue
                    
                    # Calculate similarity
                    if intent.matched_pattern:
                        similarity = fuzz.ratio(intent.matched_pattern, pattern) / 100.0
                        if similarity >= threshold:
                            similar.append(Intent(
                                primary=primary_intent,
                                secondary=secondary_intent,
                                confidence=similarity,
                                matched_pattern=pattern
                            ))
        
        return sorted(similar, key=lambda x: x.confidence, reverse=True)
    
    def validate_intent(self, intent: Intent, context: Dict = None) -> bool:
        """Validate if an intent makes sense in the given context"""
        if intent.confidence < 0.5:
            return False
        
        # Add context-specific validation rules here
        if context:
            # Example: Don't allow task creation if user already has max tasks
            if (intent.primary == "task" and intent.secondary == "create" and
                context.get("user_task_count", 0) > context.get("max_tasks", 1000)):
                return False
        
        return True
    
    def clear_cache(self):
        """Clear the pattern matching cache"""
        self.pattern_cache.clear()

# Global classifier instance
intent_classifier = IntentClassifier()

"""
Entity extraction system for the chatbot.
Extracts dates, tasks, projects, priorities, and other relevant entities from user messages.
"""

import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from dateutil import parser
from django.utils import timezone
import pytz
import logging

logger = logging.getLogger(__name__)

@dataclass
class Entity:
    """Represents an extracted entity"""
    type: str
    value: Any
    confidence: float
    start_pos: int = -1
    end_pos: int = -1
    raw_text: str = ""

class EntityExtractor:
    """
    Advanced entity extraction system for chatbot conversations.
    """
    
    def __init__(self):
        self.timezone = pytz.timezone('Australia/Melbourne')
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regex patterns for entity extraction"""
        
        # Date patterns
        self.date_patterns = [
            # Relative dates
            (r'\btoday\b', 'relative_date'),
            (r'\btomorrow\b', 'relative_date'),
            (r'\byesterday\b', 'relative_date'),
            (r'\bnext week\b', 'relative_date'),
            (r'\bthis week\b', 'relative_date'),
            (r'\bnext month\b', 'relative_date'),
            (r'\bthis month\b', 'relative_date'),
            
            # Days of week
            (r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', 'day_of_week'),
            (r'\b(mon|tue|wed|thu|fri|sat|sun)\b', 'day_of_week_short'),
            
            # Specific dates
            (r'\b(\d{1,2})/(\d{1,2})/(\d{4})\b', 'date_slash'),
            (r'\b(\d{1,2})-(\d{1,2})-(\d{4})\b', 'date_dash'),
            (r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b', 'date_iso'),
            
            # Time expressions
            (r'\b(\d{1,2}):(\d{2})\s*(am|pm)?\b', 'time'),
            (r'\b(\d{1,2})\s*(am|pm)\b', 'time_simple'),
            
            # Duration expressions
            (r'\bin\s+(\d+)\s+(minute|hour|day|week|month)s?\b', 'duration'),
            (r'\bafter\s+(\d+)\s+(minute|hour|day|week|month)s?\b', 'duration'),
        ]
        
        # Priority patterns
        self.priority_patterns = [
            (r'\b(urgent|critical|emergency|asap)\b', 'high'),
            (r'\bhigh\s+priority\b', 'high'),
            (r'\bimportant\b', 'high'),
            (r'\bmedium\s+priority\b', 'medium'),
            (r'\bnormal\s+priority\b', 'medium'),
            (r'\blow\s+priority\b', 'low'),
            (r'\bnot\s+urgent\b', 'low'),
            (r'\bwhenever\b', 'low'),
        ]
        
        # Task reference patterns
        self.task_patterns = [
            (r'\btask\s+(?:named|called|titled)\s+["\']([^"\']+)["\']', 'task_name_quoted'),
            (r'\btask\s+["\']([^"\']+)["\']', 'task_name_quoted'),
            (r'\bthe\s+task\s+([^\s,\.!?]+(?:\s+[^\s,\.!?]+)*)', 'task_name'),
            (r'\btask\s+(\w+(?:\s+\w+)*)', 'task_name'),
        ]
        
        # Project reference patterns
        self.project_patterns = [
            (r'\bproject\s+(?:named|called|titled)\s+["\']([^"\']+)["\']', 'project_name_quoted'),
            (r'\bproject\s+["\']([^"\']+)["\']', 'project_name_quoted'),
            (r'\bthe\s+project\s+([^\s,\.!?]+(?:\s+[^\s,\.!?]+)*)', 'project_name'),
            (r'\bproject\s+(\w+(?:\s+\w+)*)', 'project_name'),
        ]
        
        # Number patterns
        self.number_patterns = [
            (r'\b(\d+)\b', 'number'),
            (r'\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth)\b', 'ordinal'),
            (r'\b(one|two|three|four|five|six|seven|eight|nine|ten)\b', 'word_number'),
        ]
        
        # Status patterns
        self.status_patterns = [
            (r'\b(completed?|finished?|done)\b', 'completed'),
            (r'\b(pending|todo|to do|in progress|ongoing)\b', 'pending'),
            (r'\b(cancelled?|deleted?|removed?)\b', 'cancelled'),
        ]
    
    def extract_entities(self, message: str) -> Dict[str, List[Entity]]:
        """
        Extract all entities from a message.
        
        Args:
            message: The user's message
            
        Returns:
            Dictionary mapping entity types to lists of Entity objects
        """
        entities = {
            'dates': [],
            'times': [],
            'priorities': [],
            'tasks': [],
            'projects': [],
            'numbers': [],
            'statuses': [],
            'durations': []
        }
        
        message_lower = message.lower()
        
        # Extract dates and times
        date_entities = self._extract_dates(message_lower)
        entities['dates'].extend(date_entities)
        
        # Extract priorities
        priority_entities = self._extract_priorities(message_lower)
        entities['priorities'].extend(priority_entities)
        
        # Extract task references
        task_entities = self._extract_tasks(message)
        entities['tasks'].extend(task_entities)
        
        # Extract project references
        project_entities = self._extract_projects(message)
        entities['projects'].extend(project_entities)
        
        # Extract numbers
        number_entities = self._extract_numbers(message_lower)
        entities['numbers'].extend(number_entities)
        
        # Extract statuses
        status_entities = self._extract_statuses(message_lower)
        entities['statuses'].extend(status_entities)
        
        return entities
    
    def _extract_dates(self, message: str) -> List[Entity]:
        """Extract date entities from message"""
        entities = []
        
        for pattern, pattern_type in self.date_patterns:
            matches = re.finditer(pattern, message, re.IGNORECASE)
            for match in matches:
                try:
                    parsed_date = self._parse_date(match.group(), pattern_type)
                    if parsed_date:
                        entities.append(Entity(
                            type='date',
                            value=parsed_date,
                            confidence=0.9,
                            start_pos=match.start(),
                            end_pos=match.end(),
                            raw_text=match.group()
                        ))
                except Exception as e:
                    logger.warning(f"Failed to parse date '{match.group()}': {e}")
        
        return entities
    
    def _parse_date(self, date_text: str, pattern_type: str) -> Optional[datetime]:
        """Parse date text into datetime object"""
        now = timezone.now().astimezone(self.timezone)
        
        try:
            if pattern_type == 'relative_date':
                if date_text == 'today':
                    return now.replace(hour=23, minute=59, second=59)
                elif date_text == 'tomorrow':
                    return (now + timedelta(days=1)).replace(hour=23, minute=59, second=59)
                elif date_text == 'yesterday':
                    return (now - timedelta(days=1)).replace(hour=23, minute=59, second=59)
                elif date_text == 'next week':
                    return now + timedelta(weeks=1)
                elif date_text == 'this week':
                    return now + timedelta(days=(6 - now.weekday()))
                elif date_text == 'next month':
                    if now.month == 12:
                        return now.replace(year=now.year + 1, month=1)
                    else:
                        return now.replace(month=now.month + 1)
                elif date_text == 'this month':
                    return now.replace(day=28)  # Safe day for any month
                        
            elif pattern_type in ['day_of_week', 'day_of_week_short']:
                days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
                short_days = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
                
                if pattern_type == 'day_of_week_short':
                    day_index = short_days.index(date_text.lower())
                else:
                    day_index = days.index(date_text.lower())
                
                days_ahead = (day_index - now.weekday()) % 7
                if days_ahead == 0:  # Today, assume next week
                    days_ahead = 7
                
                return now + timedelta(days=days_ahead)
            
            else:
                # Use dateutil parser for other formats
                return parser.parse(date_text, fuzzy=True)
                
        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse date '{date_text}': {e}")
            return None
    
    def _extract_priorities(self, message: str) -> List[Entity]:
        """Extract priority entities from message"""
        entities = []
        
        for pattern, priority_level in self.priority_patterns:
            matches = re.finditer(pattern, message, re.IGNORECASE)
            for match in matches:
                entities.append(Entity(
                    type='priority',
                    value=priority_level,
                    confidence=0.9,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    raw_text=match.group()
                ))
        
        return entities
    
    def _extract_tasks(self, message: str) -> List[Entity]:
        """Extract task reference entities from message"""
        entities = []
        
        for pattern, pattern_type in self.task_patterns:
            matches = re.finditer(pattern, message, re.IGNORECASE)
            for match in matches:
                task_name = match.group(1) if match.groups() else match.group()
                
                # Clean up the task name
                task_name = task_name.strip()
                
                # Skip very short or common words
                if len(task_name) < 2 or task_name.lower() in ['it', 'this', 'that', 'the']:
                    continue
                
                confidence = 0.9 if 'quoted' in pattern_type else 0.7
                
                entities.append(Entity(
                    type='task_reference',
                    value=task_name,
                    confidence=confidence,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    raw_text=match.group()
                ))
        
        return entities
    
    def _extract_projects(self, message: str) -> List[Entity]:
        """Extract project reference entities from message"""
        entities = []
        
        for pattern, pattern_type in self.project_patterns:
            matches = re.finditer(pattern, message, re.IGNORECASE)
            for match in matches:
                project_name = match.group(1) if match.groups() else match.group()
                
                # Clean up the project name
                project_name = project_name.strip()
                
                # Skip very short or common words
                if len(project_name) < 2 or project_name.lower() in ['it', 'this', 'that', 'the']:
                    continue
                
                confidence = 0.9 if 'quoted' in pattern_type else 0.7
                
                entities.append(Entity(
                    type='project_reference',
                    value=project_name,
                    confidence=confidence,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    raw_text=match.group()
                ))
        
        return entities
    
    def _extract_numbers(self, message: str) -> List[Entity]:
        """Extract number entities from message"""
        entities = []
        
        word_to_number = {
            'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
            'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
            'first': 1, 'second': 2, 'third': 3, 'fourth': 4, 'fifth': 5,
            'sixth': 6, 'seventh': 7, 'eighth': 8, 'ninth': 9, 'tenth': 10
        }
        
        for pattern, pattern_type in self.number_patterns:
            matches = re.finditer(pattern, message, re.IGNORECASE)
            for match in matches:
                if pattern_type == 'number':
                    number_value = int(match.group(1))
                else:
                    word = match.group(1).lower()
                    number_value = word_to_number.get(word)
                
                if number_value is not None:
                    entities.append(Entity(
                        type='number',
                        value=number_value,
                        confidence=0.95,
                        start_pos=match.start(),
                        end_pos=match.end(),
                        raw_text=match.group()
                    ))
        
        return entities
    
    def _extract_statuses(self, message: str) -> List[Entity]:
        """Extract status entities from message"""
        entities = []
        
        for pattern, status_value in self.status_patterns:
            matches = re.finditer(pattern, message, re.IGNORECASE)
            for match in matches:
                entities.append(Entity(
                    type='status',
                    value=status_value,
                    confidence=0.85,
                    start_pos=match.start(),
                    end_pos=match.end(),
                    raw_text=match.group()
                ))
        
        return entities
    
    def extract_task_info(self, message: str) -> Dict[str, Any]:
        """
        Extract task creation information from a message.
        
        Args:
            message: The user's message
            
        Returns:
            Dictionary containing extracted task information
        """
        entities = self.extract_entities(message)
        
        task_info = {
            'title': None,
            'description': None,
            'due_date': None,
            'priority': 'medium',
            'project': None
        }
        
        # Extract title from the message (everything after creation intent)
        title_patterns = [
            r'(?:create|add|make|new)\s+(?:task|todo)(?:\s*:)?\s*(.+?)(?:\s+(?:by|due|on|priority|project)|$)',
            r'(?:task|todo)(?:\s*:)?\s*(.+?)(?:\s+(?:by|due|on|priority|project)|$)'
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                title = match.group(1).strip()
                # Clean title from extracted entities
                for entity_list in entities.values():
                    for entity in entity_list:
                        if entity.raw_text in title:
                            title = title.replace(entity.raw_text, '').strip()
                
                if title and len(title) > 2:
                    task_info['title'] = title
                    break
        
        # Set due date from date entities
        if entities['dates']:
            # Use the first date found
            task_info['due_date'] = entities['dates'][0].value
        
        # Set priority from priority entities
        if entities['priorities']:
            task_info['priority'] = entities['priorities'][0].value
        
        # Set project from project entities
        if entities['projects']:
            task_info['project'] = entities['projects'][0].value
        
        return task_info
    
    def get_entity_summary(self, entities: Dict[str, List[Entity]]) -> str:
        """Generate a human-readable summary of extracted entities"""
        summary_parts = []
        
        for entity_type, entity_list in entities.items():
            if entity_list:
                values = [str(entity.value) for entity in entity_list]
                summary_parts.append(f"{entity_type}: {', '.join(values)}")
        
        return "; ".join(summary_parts) if summary_parts else "No entities extracted"

# Global extractor instance
entity_extractor = EntityExtractor()

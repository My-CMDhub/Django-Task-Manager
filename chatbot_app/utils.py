import re
import datetime
from dateutil import parser
from django.utils import timezone
from django.db import models
from collections import Counter

def extract_task_info(message):
    """
    Extract task information from a user's message using pattern matching
    """
    # Check for common task creation patterns
    task_patterns = [
        # Direct task creation commands
        r'add task[s]?\s*:?\s*(.+)',
        r'create task[s]?\s*:?\s*(.+)',
        r'new task[s]?\s*:?\s*(.+)',
        
        # Reminder style patterns
        r'remind me to\s*(.+)',
        r'I need to\s*(.+)',
        r'don\'t let me forget to\s*(.+)',
        
        # Deadline focused patterns
        r'I have to\s*(.+?)\s+by\s+(.+)',
        r'need to finish\s*(.+?)\s+by\s+(.+)',
        r'must complete\s*(.+?)\s+by\s+(.+)',
        
        # Project focused patterns
        r'for project\s*(.+?)\s*[,:]\s*(.+)',
        r'in project\s*(.+?)\s*[,:]\s*(.+)',
        
        # Simple task statements
        r'I should\s*(.+)',
        r'Let\'s\s*(.+)',
    ]
    
    task_content = None
    project_name = None
    matched_pattern_idx = -1
    
    for idx, pattern in enumerate(task_patterns):
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            matched_pattern_idx = idx
            # Special handling for patterns with project information
            if idx in [9, 10]:  # project focused patterns
                project_name = match.group(1).strip()
                task_content = match.group(2).strip()
            # Special handling for deadline patterns
            elif idx in [6, 7, 8]:  # deadline focused patterns
                task_content = match.group(1).strip()
                # Automatically add the deadline info to the task content
                deadline = match.group(2).strip()
                task_content += f" by {deadline}"
            else:
                task_content = match.group(1).strip()
            break
    
    if not task_content:
        return None
    
    # Now extract details from the content
    task_info = {
        'title': task_content,
        'description': '',
        'due_date': None,
        'priority': 'medium',
        'project': project_name,
    }
    
    # Extract due date if present
    date_patterns = [
        r'by\s+(.+?)(?:\s+at\s+|$)',
        r'due\s+(.+?)(?:\s+at\s+|$)', 
        r'on\s+(.+?)(?:\s+at\s+|$)',
        r'for\s+(.+?)(?:\s+at\s+|$)',
        r'before\s+(.+?)(?:\s+at\s+|$)',
    ]
    
    # Enhanced date recognition
    for pattern in date_patterns:
        match = re.search(pattern, task_content, re.IGNORECASE)
        if match:
            date_str = match.group(1).strip()
            try:
                # Handle relative dates like "tomorrow", "next week", etc.
                if date_str.lower() == 'tomorrow':
                    due_date = timezone.now() + datetime.timedelta(days=1)
                elif date_str.lower() == 'tonight':
                    due_date = timezone.now().replace(hour=20, minute=0, second=0)
                elif date_str.lower() in ['next week', 'the next week']:
                    due_date = timezone.now() + datetime.timedelta(days=7)
                elif 'day' in date_str.lower() and 'after' in date_str.lower():
                    # "day after tomorrow" = 2 days
                    due_date = timezone.now() + datetime.timedelta(days=2)
                else:
                    due_date = parser.parse(date_str, fuzzy=True)
                
                # If only date is provided (no time), set default time to end of day
                if due_date.hour == 0 and due_date.minute == 0 and due_date.second == 0:
                    due_date = due_date.replace(hour=23, minute=59, second=59)
                
                task_info['due_date'] = due_date
                # Remove date part from title
                task_info['title'] = re.sub(pattern, '', task_info['title'], flags=re.IGNORECASE).strip()
                break
            except ValueError:
                pass
    
    # Enhanced priority recognition
    priority_mapping = {
        'high': ['urgent', 'important', 'critical', 'high priority', 'asap', 'emergency', 'top priority', 'highest priority', 'crucial'],
        'medium': ['medium priority', 'normal priority', 'moderate priority', 'standard priority'],
        'low': ['low priority', 'whenever', 'not urgent', 'at your leisure', 'when possible', 'least important', 'can wait']
    }
    
    for priority, keywords in priority_mapping.items():
        for keyword in keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', task_content.lower()):
                task_info['priority'] = priority
                # Remove priority keyword from title
                task_info['title'] = re.sub(r'\b' + re.escape(keyword) + r'\b', '', task_info['title'], flags=re.IGNORECASE).strip()
                break
    
    # Check for descriptive content and split into title/description
    has_description = False
    
    # Look for explicit description markers
    description_markers = [': ', ' - ', '. ', ' with details ', ' description: ']
    for marker in description_markers:
        if marker in task_info['title']:
            parts = task_info['title'].split(marker, 1)
            task_info['title'] = parts[0].strip()
            task_info['description'] = parts[1].strip()
            has_description = True
            break
    
    # If no explicit markers but title is long, split it
    if not has_description:
        title_words = task_info['title'].split()
        if len(title_words) > 8:
            task_info['title'] = ' '.join(title_words[:8])
            task_info['description'] = ' '.join(title_words[8:])
    
    # Clean up title and description
    task_info['title'] = task_info['title'].rstrip('.,;:').strip()
    
    # If title is still too long, truncate and move the rest to description
    if len(task_info['title']) > 100:
        task_info['description'] = task_info['title'][100:] + (" " + task_info['description'] if task_info['description'] else "")
        task_info['title'] = task_info['title'][:100].rstrip()
    
    return task_info

def create_task(user, task_info):
    """
    Create a task in the database
    """
    # Import here to avoid circular imports
    from tasks.models import Task
    
    # Default priority if not specified
    priority = task_info.get('priority', 'medium')
    
    # Create the task
    task = Task.objects.create(
        owner=user,
        title=task_info['title'],
        description=task_info.get('description', ''),
        due_date=task_info.get('due_date'),
        priority=priority,
        status='todo'
    )
    
    # Add the user as an assignee
    task.assignees.add(user)
    
    # Log the activity
    from tasks.models import TaskActivity
    TaskActivity.objects.create(
        task=task,
        activity_type='create',
        user=user,
        description=f"Task '{task.title}' created via chatbot"
    )
    
    return task.id

def get_user_tasks(user, status=None, limit=5):
    """
    Get tasks for a user with optional filtering by status
    """
    from tasks.models import Task
    
    tasks = Task.objects.filter(assignees=user)
    
    if status:
        tasks = tasks.filter(status=status)
    
    # Order by due date (if set) with null dates last
    tasks = tasks.order_by(
        models.F('due_date').asc(nulls_last=True),
        '-priority',
        'created_at'
    )
    
    return tasks[:limit]

def format_task_list(tasks):
    """
    Format a list of tasks for display in the chatbot
    """
    if not tasks:
        return "No tasks found."
    
    result = []
    for i, task in enumerate(tasks, 1):
        due_info = f", due {task.due_date.strftime('%b %d, %Y')}" if task.due_date else ""
        priority_info = f", {task.priority} priority"
        result.append(f"{i}. {task.title}{due_info}{priority_info}")
    
    return "\n".join(result)

def analyze_user_patterns(user):
    """
    Analyze user task patterns to generate intelligent suggestions
    """
    from tasks.models import Task, TaskActivity
    from django.db.models import Count, Avg, Q
    
    # Get user's completed tasks
    completed_tasks = Task.objects.filter(
        assignees=user,
        status='completed',
        is_archived=False
    )
    
    # Get user's active tasks
    active_tasks = Task.objects.filter(
        assignees=user,
        is_archived=False
    ).exclude(status='completed')
    
    patterns = {}
    
    # 1. Find most productive time of day
    if completed_tasks.exists():
        activities = TaskActivity.objects.filter(
            task__in=completed_tasks,
            activity_type='status_change',
            description__contains='completed'
        )
        
        if activities.exists():
            # Group completed tasks by hour of day
            hour_counts = Counter([a.created_at.hour for a in activities])
            
            # Find the most common hour
            most_productive_hour = hour_counts.most_common(1)[0][0] if hour_counts else None
            
            if most_productive_hour is not None:
                # Convert to time period
                if 5 <= most_productive_hour < 12:
                    patterns['productive_time'] = 'morning'
                elif 12 <= most_productive_hour < 17:
                    patterns['productive_time'] = 'afternoon'
                elif 17 <= most_productive_hour < 21:
                    patterns['productive_time'] = 'evening'
                else:
                    patterns['productive_time'] = 'late night'
    
    # 2. Find recurring task patterns
    if completed_tasks.count() >= 3:
        # Look for similar task titles
        all_tasks = Task.objects.filter(assignees=user)
        title_words = Counter()
        
        for task in all_tasks:
            words = task.title.lower().split()
            title_words.update(words)
        
        common_words = [word for word, count in title_words.most_common(10) if count >= 3 and len(word) > 3]
        if common_words:
            patterns['common_task_words'] = common_words
            
            # Find potential recurring tasks based on title similarity
            potential_recurring = {}
            for word in common_words:
                similar_tasks = Task.objects.filter(
                    assignees=user,
                    title__icontains=word
                ).count()
                
                if similar_tasks >= 3:
                    potential_recurring[word] = similar_tasks
            
            if potential_recurring:
                patterns['recurring_task_keywords'] = potential_recurring
    
    # 3. Check for overdue tasks
    overdue_count = Task.objects.filter(
        assignees=user,
        due_date__lt=timezone.now(),
        is_archived=False
    ).exclude(status='completed').count()
    
    if overdue_count > 0:
        patterns['overdue_count'] = overdue_count
    
    # 4. Calculate weekly task completion rate
    one_week_ago = timezone.now() - datetime.timedelta(days=7)
    two_weeks_ago = timezone.now() - datetime.timedelta(days=14)
    
    tasks_completed_this_week = completed_tasks.filter(completed_at__gte=one_week_ago).count()
    tasks_completed_last_week = completed_tasks.filter(
        completed_at__gte=two_weeks_ago,
        completed_at__lt=one_week_ago
    ).count()
    
    patterns['tasks_completed_this_week'] = tasks_completed_this_week
    
    if tasks_completed_last_week > 0:
        percent_change = ((tasks_completed_this_week - tasks_completed_last_week) / tasks_completed_last_week) * 100
        if percent_change > 0:
            patterns['completion_trend'] = f"{int(percent_change)}% more"
        else:
            patterns['completion_trend'] = f"{int(abs(percent_change))}% fewer"
    
    # 5. Task priority distribution
    priority_counts = active_tasks.values('priority').annotate(count=Count('priority'))
    priority_dict = {item['priority']: item['count'] for item in priority_counts}
    
    high_priority_count = priority_dict.get('high', 0)
    if high_priority_count >= 3:
        patterns['high_priority_count'] = high_priority_count
    
    return patterns

def generate_task_suggestions(user):
    """
    Generate personalized task suggestions based on user patterns
    """
    from tasks.models import Task
    from django.db.models import Q
    
    patterns = analyze_user_patterns(user)
    suggestions = []
    
    # 1. Check for overdue tasks
    if 'overdue_count' in patterns and patterns['overdue_count'] > 0:
        suggestions.append({
            'type': 'overdue_reminder',
            'message': f"You have {patterns['overdue_count']} overdue tasks. Would you like to see them?"
        })
    
    # 2. Productivity insights
    if 'productive_time' in patterns:
        suggestions.append({
            'type': 'productivity_insight',
            'message': f"Based on your history, you're most productive in the {patterns['productive_time']}. Would you like me to prioritize important tasks during this time?"
        })
    
    # 3. Weekly accomplishment
    if 'tasks_completed_this_week' in patterns and patterns['tasks_completed_this_week'] > 0:
        message = f"You've completed {patterns['tasks_completed_this_week']} tasks this week."
        if 'completion_trend' in patterns:
            message += f" That's {patterns['completion_trend']} than last week!"
        suggestions.append({
            'type': 'accomplishment',
            'message': message
        })
    
    # 4. Recurring task suggestions
    if 'recurring_task_keywords' in patterns:
        keyword, count = max(patterns['recurring_task_keywords'].items(), key=lambda x: x[1])
        suggestions.append({
            'type': 'recurring_task_suggestion',
            'message': f"I notice you've created {count} tasks related to '{keyword}'. Would you like to set up a recurring task for this?"
        })
    
    # 5. High priority task alert
    if 'high_priority_count' in patterns and patterns['high_priority_count'] >= 3:
        suggestions.append({
            'type': 'priority_suggestion',
            'message': f"You have {patterns['high_priority_count']} high-priority tasks. Would you like help creating a plan to tackle them?"
        })
    
    # 6. Break suggestion (random chance, about 20%)
    import random
    if random.random() < 0.2:
        suggestions.append({
            'type': 'break_suggestion',
            'message': "You've been working hard! Consider taking a short break before starting your next task."
        })
    
    return suggestions

def get_personalized_greeting(user):
    """
    Generate a personalized greeting based on time of day and user's task status
    """
    from tasks.models import Task
    
    current_hour = timezone.now().hour
    name = user.first_name or user.username
    
    # Determine time of day
    if 5 <= current_hour < 12:
        greeting_base = f"Good morning, {name}!"
    elif 12 <= current_hour < 17:
        greeting_base = f"Good afternoon, {name}!"
    elif 17 <= current_hour < 21:
        greeting_base = f"Good evening, {name}!"
    else:
        greeting_base = f"Hello, {name}!"
    
    # Check for due today tasks
    today = timezone.now().date()
    due_today_count = Task.objects.filter(
        assignees=user,
        due_date__date=today,
        is_archived=False
    ).exclude(status='completed').count()
    
    overdue_count = Task.objects.filter(
        assignees=user,
        due_date__lt=timezone.now(),
        is_archived=False
    ).exclude(status='completed').count()
    
    if overdue_count > 0:
        return f"{greeting_base} You have {overdue_count} overdue tasks that need attention."
    elif due_today_count > 0:
        return f"{greeting_base} You have {due_today_count} tasks due today."
    else:
        return f"{greeting_base} What can TaskBuddy help you with today?"

def analyze_conversation_context(context):
    """
    Analyze conversation context to identify patterns and current conversation flow
    """
    if not context or len(context) < 2:
        return {
            'topic': None,
            'flow': None,
            'has_question': False,
            'recent_mentions': []
        }
    
    # Initialize analysis result
    analysis = {
        'topic': None,
        'flow': None,
        'has_question': False,
        'recent_mentions': [],
        'last_bot_question_type': None
    }
    
    # Extract content for analysis
    messages = [msg["content"].lower() for msg in context]
    
    # Check for active conversation flows
    if any("due date" in msg for msg in messages[-3:]):
        analysis['flow'] = 'due_date_setting'
    elif any("add more details" in msg for msg in messages[-3:] or "additional details" in msg for msg in messages[-3:]):
        analysis['flow'] = 'adding_details'
    elif any("create a task" in msg for msg in messages[-3:] or "add a task" in msg for msg in messages[-3:]):
        analysis['flow'] = 'task_creation'
    elif any(re.search(r'(show|see|list|display).+(tasks?|to-?dos?)', msg) for msg in messages[-3:]):
        analysis['flow'] = 'showing_tasks'
    
    # Identify topic
    topic_keywords = {
        'task_management': ['task', 'todo', 'to-do', 'to do', 'complete', 'finish', 'done', 'status'],
        'productivity': ['productive', 'efficiency', 'focus', 'progress', 'accomplish'],
        'planning': ['plan', 'schedule', 'organize', 'prioritize', 'agenda'],
        'reminders': ['remind', 'remember', 'forget', 'notification', 'alert'],
        'time_management': ['time', 'deadline', 'due date', 'late', 'overdue']
    }
    
    # Count keyword occurrences for topic identification
    topic_counts = {topic: 0 for topic in topic_keywords}
    
    for msg in messages[-5:]:  # Analyze last 5 messages
        for topic, keywords in topic_keywords.items():
            for keyword in keywords:
                if keyword in msg:
                    topic_counts[topic] += 1
    
    # Determine main topic based on keyword frequency
    if topic_counts:
        main_topic = max(topic_counts.items(), key=lambda x: x[1])
        if main_topic[1] > 0:  # Only set if there are actual mentions
            analysis['topic'] = main_topic[0]
    
    # Check for questions in latest bot message
    if len(context) >= 2:
        bot_messages = [msg for msg in context if msg["role"] == "bot"]
        if bot_messages:
            last_bot_msg = bot_messages[-1]["content"].lower()
            
            # Check if it's a question by looking for question marks or interrogative phrases
            if "?" in last_bot_msg or any(phrase in last_bot_msg for phrase in [
                "would you like", "do you want", "can i help", "should i", 
                "how about", "what would you like", "how can i", "would you prefer",
                "would you like me to show"
            ]):
                analysis['has_question'] = True
                
                # Try to determine what type of question it is
                question_types = {
                    'show_tasks': ['show you your tasks', 'see your tasks', 'list your tasks', 'display your tasks'],
                    'create_task': ['create a task', 'add a task', 'new task'],
                    'priority': ['prioritize', 'high priority', 'important tasks'],
                    'reminder': ['remind you', 'set a reminder', 'notification'],
                    'due_date': ['due date', 'deadline', 'when is it due'],
                    'help': ['help you with', 'assist you', 'how can i help']
                }
                
                for q_type, phrases in question_types.items():
                    if any(phrase in last_bot_msg for phrase in phrases):
                        analysis['last_bot_question_type'] = q_type
                        break
    
    # Extract potential entities mentioned (tasks, projects, etc.)
    entity_patterns = [
        r'task [\'""]?([\w\s]+?)[\'""]?[\s\.,:;]',
        r'project [\'""]?([\w\s]+?)[\'""]?[\s\.,:;]',
        r'to do [\'""]?([\w\s]+?)[\'""]?[\s\.,:;]',
        r'about [\'""]?([\w\s]+?)[\'""]?[\s\.,:;]'
    ]
    
    for msg in messages[-3:]:  # Look in last 3 messages
        for pattern in entity_patterns:
            matches = re.findall(pattern, msg)
            for match in matches:
                if match and len(match) > 3 and match not in analysis['recent_mentions']:
                    analysis['recent_mentions'].append(match.strip())
    
    return analysis 

def get_user_context_data(user, query=None, limit=10):
    """
    Get relevant user context data on demand based on the query.
    Returns formatted data that can be injected into the AI prompt.
    
    Args:
        user: The user object
        query: The user's query text to help determine what data to fetch
        limit: Maximum number of items to return per category
        
    Returns:
        str: Formatted context data as text
    """
    from tasks.models import Task, Project, TaskActivity
    from django.utils import timezone
    from django.db.models import Q
    import datetime
    
    # Initialize context data
    context_data = []
    now = timezone.now()
    today = now.date()
    
    # Analyze the query to determine what data to fetch
    query_lower = query.lower() if query else ""
    
    # Default to include basic task info if query is empty or very short
    if not query or len(query.split()) <= 3:
        # Basic info: Return a summary of the user's tasks
        active_tasks_count = Task.objects.filter(
            assignees=user,
            is_archived=False
        ).exclude(status='completed').count()
        
        overdue_tasks_count = Task.objects.filter(
            assignees=user,
            due_date__lt=now,
            is_archived=False
        ).exclude(status='completed').count()
        
        due_today_count = Task.objects.filter(
            assignees=user,
            due_date__date=today,
            is_archived=False
        ).exclude(status='completed').count()
        
        projects_count = Project.objects.filter(members=user).count()
        
        context_data.append(f"USER TASK SUMMARY:")
        context_data.append(f"- Active tasks: {active_tasks_count}")
        context_data.append(f"- Overdue tasks: {overdue_tasks_count}")
        context_data.append(f"- Due today: {due_today_count}")
        context_data.append(f"- Projects: {projects_count}")
        context_data.append("")
        
        # Include a few high priority tasks
        high_priority_tasks = Task.objects.filter(
            assignees=user,
            priority__in=['high', 'urgent'],
            is_archived=False
        ).exclude(status='completed').order_by('due_date')[:3]
        
        if high_priority_tasks.exists():
            context_data.append("HIGH PRIORITY TASKS:")
            for i, task in enumerate(high_priority_tasks, 1):
                due_info = f", due {task.due_date.strftime('%b %d')}" if task.due_date else ""
                context_data.append(f"{i}. {task.title}{due_info}")
            context_data.append("")
    
    # Look for task-specific queries
    if any(word in query_lower for word in ['task', 'todo', 'to-do', 'to do', 'work', 'assignment']):
        # Task listing: Get active tasks
        active_tasks = Task.objects.filter(
            assignees=user,
            is_archived=False
        ).exclude(status='completed').order_by('due_date', '-priority')[:limit]
        
        if active_tasks.exists():
            context_data.append("ACTIVE TASKS:")
            for i, task in enumerate(active_tasks, 1):
                due_info = f", due {task.due_date.strftime('%b %d')}" if task.due_date else ""
                priority_info = f", {task.priority} priority"
                context_data.append(f"{i}. {task.title}{due_info}{priority_info}")
            context_data.append("")
        
    # Look for priority-specific queries
    if any(word in query_lower for word in ['priority', 'important', 'urgent', 'critical']):
        # Priority focus: Get high priority tasks
        high_priority_tasks = Task.objects.filter(
            assignees=user,
            priority__in=['high', 'urgent'],
            is_archived=False
        ).exclude(status='completed').order_by('due_date')[:limit]
        
        if high_priority_tasks.exists():
            context_data.append("HIGH PRIORITY TASKS:")
            for i, task in enumerate(high_priority_tasks, 1):
                due_info = f", due {task.due_date.strftime('%b %d')}" if task.due_date else ""
                context_data.append(f"{i}. {task.title}{due_info}")
            context_data.append("")
    
    # Look for date-specific queries
    if any(word in query_lower for word in ['today', 'tomorrow', 'this week', 'overdue', 'late']):
        # Time-sensitive tasks
        due_tasks = []
        date_context = ""
        
        if 'today' in query_lower:
            due_tasks = Task.objects.filter(
                assignees=user,
                due_date__date=today,
                is_archived=False
            ).exclude(status='completed').order_by('due_date')[:limit]
            date_context = "TODAY"
            
        elif 'tomorrow' in query_lower:
            tomorrow = today + datetime.timedelta(days=1)
            due_tasks = Task.objects.filter(
                assignees=user,
                due_date__date=tomorrow,
                is_archived=False
            ).exclude(status='completed').order_by('due_date')[:limit]
            date_context = "TOMORROW"
            
        elif 'this week' in query_lower:
            week_end = today + datetime.timedelta(days=7)
            due_tasks = Task.objects.filter(
                assignees=user,
                due_date__date__range=[today, week_end],
                is_archived=False
            ).exclude(status='completed').order_by('due_date')[:limit]
            date_context = "THIS WEEK"
            
        elif 'overdue' in query_lower or 'late' in query_lower:
            due_tasks = Task.objects.filter(
                assignees=user,
                due_date__lt=now,
                is_archived=False
            ).exclude(status='completed').order_by('due_date')[:limit]
            date_context = "OVERDUE"
        
        if due_tasks.exists():
            context_data.append(f"TASKS DUE {date_context}:")
            for i, task in enumerate(due_tasks, 1):
                due_info = f", due {task.due_date.strftime('%b %d')}" if task.due_date else ""
                priority_info = f", {task.priority} priority"
                context_data.append(f"{i}. {task.title}{due_info}{priority_info}")
            context_data.append("")
    
    # Look for completed task queries
    if any(word in query_lower for word in ['completed', 'finished', 'done']):
        # Recently completed tasks
        completed_tasks = Task.objects.filter(
            assignees=user,
            status='completed',
            is_archived=False
        ).order_by('-completed_at')[:limit]
        
        if completed_tasks.exists():
            context_data.append("RECENTLY COMPLETED TASKS:")
            for i, task in enumerate(completed_tasks, 1):
                completed_info = f", completed {task.completed_at.strftime('%b %d')}" if task.completed_at else ""
                context_data.append(f"{i}. {task.title}{completed_info}")
            context_data.append("")
    
    # Look for project-specific queries
    if any(word in query_lower for word in ['project', 'projects', 'workspace']):
        # Projects data
        projects = Project.objects.filter(
            members=user,
            is_archived=False
        ).order_by('-updated_at')[:limit]
        
        if projects.exists():
            context_data.append("YOUR PROJECTS:")
            for i, project in enumerate(projects, 1):
                task_count = project.tasks.filter(is_archived=False).count()
                context_data.append(f"{i}. {project.name} ({task_count} tasks)")
            context_data.append("")
        
        # If specific project is mentioned, get tasks for that project
        for project in projects:
            if project.name.lower() in query_lower:
                project_tasks = Task.objects.filter(
                    project=project,
                    is_archived=False
                ).exclude(status='completed').order_by('due_date')[:limit]
                
                if project_tasks.exists():
                    context_data.append(f"TASKS IN PROJECT '{project.name}':")
                    for i, task in enumerate(project_tasks, 1):
                        due_info = f", due {task.due_date.strftime('%b %d')}" if task.due_date else ""
                        priority_info = f", {task.priority} priority"
                        context_data.append(f"{i}. {task.title}{due_info}{priority_info}")
                    context_data.append("")
    
    # Look for status-specific queries
    if any(word in query_lower for word in ['status', 'progress', 'in progress']):
        # Tasks by status
        status_tasks = Task.objects.filter(
            assignees=user,
            status='in_progress',
            is_archived=False
        ).order_by('due_date')[:limit]
        
        if status_tasks.exists():
            context_data.append("IN-PROGRESS TASKS:")
            for i, task in enumerate(status_tasks, 1):
                due_info = f", due {task.due_date.strftime('%b %d')}" if task.due_date else ""
                priority_info = f", {task.priority} priority"
                context_data.append(f"{i}. {task.title}{due_info}{priority_info}")
            context_data.append("")
    
    # Look for activity-related queries
    if any(word in query_lower for word in ['activity', 'history', 'recent', 'latest']):
        # Recent activity
        recent_activities = TaskActivity.objects.filter(
            task__assignees=user
        ).order_by('-created_at')[:limit]
        
        if recent_activities.exists():
            context_data.append("RECENT ACTIVITY:")
            for i, activity in enumerate(recent_activities, 1):
                activity_date = activity.created_at.strftime('%b %d')
                context_data.append(f"{i}. {activity_date}: {activity.description}")
            context_data.append("")
    
    # If we haven't found any relevant data yet, add some basic task info
    if not context_data:
        active_tasks = Task.objects.filter(
            assignees=user,
            is_archived=False
        ).exclude(status='completed').order_by('due_date')[:limit]
        
        if active_tasks.exists():
            context_data.append("YOUR ACTIVE TASKS:")
            for i, task in enumerate(active_tasks, 1):
                due_info = f", due {task.due_date.strftime('%b %d')}" if task.due_date else ""
                priority_info = f", {task.priority} priority"
                context_data.append(f"{i}. {task.title}{due_info}{priority_info}")
            context_data.append("")
    
    # Return the formatted context data
    return "\n".join(context_data) 
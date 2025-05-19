# Chatbot Context Awareness

The Task Manager chatbot has been enhanced with context awareness capabilities, allowing it to understand and respond appropriately to messages that reference previous parts of the conversation.

## How It Works

The context awareness system consists of several components working together:

1. **Conversation Memory**: Stores recent message history
2. **Context Processing**: Extracts relevant context from previous messages
3. **Pattern Recognition**: Identifies contextual references in user queries
4. **Action Handling**: Performs appropriate actions based on context

## Key Components

### Conversation Memory

The chatbot remembers the last 5 exchanges between the user and the bot, providing enough context for natural conversations:

```python
def get_recent_messages(self, count=5):
    """
    Gets the most recent messages in the conversation to provide context.
    
    Args:
        count (int): Number of recent message pairs to retrieve
        
    Returns:
        list: List of dictionaries with message content and role
    """
    # Get the most recent messages, limiting to count*2 to get 'count' exchanges
    recent_messages = self.messages.order_by('-created_at')[:count*2]
    
    # Sort them by creation time
    recent_messages = sorted(recent_messages, key=lambda x: x.created_at)
    
    # Format them as {"role": "user"/"assistant", "content": "..."}
    context = []
    for message in recent_messages:
        role = "user" if message.is_from_user else "assistant"
        context.append({"role": role, "content": message.content})
    
    return context
```

### Context Processing

When a new message is received, it's processed together with recent message history to understand contextual references:

```python
def process_context_with_query(conversation_context, user_message):
    """
    Process the conversation context with the user's query to understand
    context-based references.
    """
    # Initialize context info
    context_info = {
        'referenced_tasks': [],
        'referenced_projects': [],
        'referencing_previous': False,
        'action_context': None
    }
    
    # Check for reference indicators
    referencing_indicators = ['it', 'this', 'that', 'these', 'those', 'the task', 'the project']
    for indicator in referencing_indicators:
        if indicator in user_message.lower():
            context_info['referencing_previous'] = True
            break
    
    # Extract task/project names from previous messages
    if context_info['referencing_previous']:
        for message in reversed(conversation_context):
            if message['role'] == 'assistant':
                # Extract task names from bullet points
                bullet_items = re.findall(r'•\s+([^•\n]+)', message['content'])
                for item in bullet_items:
                    # Clean up the task name
                    task_name = re.sub(r'\(.*?\)', '', item).strip()
                    task_name = re.sub(r'\[.*?\]', '', task_name).strip()
                    task_name = re.sub(r'-\s*Status:.*$', '', task_name).strip()
                    context_info['referenced_tasks'].append(task_name)
                
                # Look for task names in regular text
                task_mentions = re.findall(r"task '([^']+)'", message['content'])
                context_info['referenced_tasks'].extend(task_mentions)
                
                # Look for project mentions
                project_mentions = re.findall(r"project '([^']+)'", message['content'])
                context_info['referenced_projects'].extend(project_mentions)
    
    # Determine action context
    if 'mark' in user_message.lower() or 'complete' in user_message.lower():
        context_info['action_context'] = 'complete'
    elif 'delete' in user_message.lower() or 'remove' in user_message.lower():
        context_info['action_context'] = 'delete'
    
    return (user_message, context_info)
```

## Example Scenarios

### Scenario 1: Task Completion

**Previous Exchange:**
```
User: Show me my tasks
Bot: Here are your tasks:
• Project Proposal (Due: 2023-05-20) [Priority: High]
• Weekly Meeting Notes (Due: 2023-05-15) [Priority: Medium]
```

**Current Exchange:**
```
User: Mark the first one as completed
Bot: I've marked "Project Proposal" as completed! Great job on finishing that high priority task.
```

### Scenario 2: Task Deletion

**Previous Exchange:**
```
User: What tasks are overdue?
Bot: You have 2 overdue tasks:
• Quarterly Report (Due: 2023-05-01) [Priority: Medium]
• Client Follow-up (Due: 2023-05-10) [Priority: Low]
```

**Current Exchange:**
```
User: Delete the quarterly report
Bot: I've deleted the "Quarterly Report" task.
```

## Implementation Notes

1. **Context Depth**: The system remembers the last 5 exchanges, which balances memory needs with context awareness
2. **Reference Resolution**: Uses patterns like "it", "this task", etc., to identify when a user is referring to previous information
3. **Time Sensitivity**: More recent messages have higher priority for reference resolution
4. **Bullet Point Extraction**: Special handling for bullet point lists to extract task names
5. **Action Detection**: Recognizes action keywords (mark, complete, delete) to determine intent

## Testing

The context awareness system includes a test suite that validates the following capabilities:

1. Extracting task names from bullet points
2. Recognizing reference indicators
3. Determining the correct action context
4. Handling multi-turn conversations

## Future Improvements

1. **Deeper Context Understanding**: Enhance ability to understand more complex references
2. **Sentiment Tracking**: Track user sentiment across conversation
3. **Session Memory**: Remember key details across multiple sessions
4. **User Preferences**: Learn and remember user preferences for task management 
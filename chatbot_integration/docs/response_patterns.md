# Chatbot Response Patterns

The Nexus chatbot has been enhanced with various response patterns to provide a professional and personalized user experience. This document outlines the various patterns and how they work.

## Key Response Patterns

### 1. Inventory Queries
- Matches queries like "What I have?", "Show me what I have", "My stuff"
- Provides a comprehensive summary of:
  - Task counts (total, pending, completed)
  - Due today tasks
  - Overdue tasks
  - High priority tasks
  - Project statistics
  - Recent activity

### 2. Task Management Commands
- View tasks: "show me my tasks", "list my tasks"
- Task completion: "mark completed", "mark task X as complete"
- Overdue tasks: "mark all overdue tasks as completed"

### 3. Project Management Queries
- View projects: "show me my projects", "list my projects"
- Project status: "project status"

### 4. Greeting and Farewell Messages
- Personalized greetings based on time of day
- Friendly farewell messages

### 5. Unclear Query Handling
- Provides helpful suggestions for ambiguous queries
- Gives examples of valid commands

## Debugging Response Patterns

When a pattern is not matching as expected, check the following:

1. **Regex Pattern Syntax**: Ensure the regex patterns are correctly formed
   - Test patterns in isolation using a regex tester
   - Verify case sensitivity handling

2. **Pattern Order**: Patterns are checked in sequence, so order matters
   - More specific patterns should come before general patterns
   - The fallback/unclear patterns should be last

3. **Pattern Placement**: Ensure patterns are in the correct part of the generate_bot_response function
   - This function processes patterns in a specific order
   - Greeting/farewell detection happens early 
   - Context-specific patterns are applied after context processing

4. **Debugging Tips**:
   - Add debug logging to print matched patterns: `logger.debug(f"Pattern matched: {pattern}")`
   - Test the regex directly: `if re.search(pattern, test_string): print("Match!")`
   - Use named capture groups for clarity: `(?P<greeting>hello|hi)`

## Extending Response Patterns

When adding new response patterns:

1. Identify the category of response (greeting, task, project, etc.)
2. Add patterns to the appropriate section
3. Create useful, friendly responses
4. Test with a variety of inputs
5. Consider adding context awareness for the pattern

For example, to add a new task-related pattern:

```python
# New pattern for task priority questions
priority_patterns = [
    r"what(?:'s| is) the priority of (.*?)(?:\?|$)",
    r"how important is (.*?)(?:\?|$)",
    r"is (.*?) high priority(?:\?|$)"
]

for pattern in priority_patterns:
    match = re.search(pattern, user_message.lower())
    if match:
        task_name = match.group(1).strip()
        # Task handling code here
        return response
```

## Testing Response Patterns

Use the test_chatbot.py script to test response patterns:

```bash
# Test a specific query
python test_chatbot.py "what I have?"

# Test all predefined categories
python test_chatbot.py
``` 
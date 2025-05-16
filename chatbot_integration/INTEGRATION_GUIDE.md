# Task Manager Chatbot Integration Guide

This guide provides step-by-step instructions to integrate the AI-powered Task Assistant chatbot into your Django Task Manager application.

## Overview

The chatbot integration provides:
- Natural language task creation and management
- An interactive chat interface built in React
- Knowledge retrieval capabilities powered by LlamaIndex and OpenAI
- Seamless integration with your existing Django Task Manager

## Prerequisites

- Django Task Manager project
- React frontend
- Python 3.8+
- OpenAI API key

## Installation Steps

### 1. Install Required Packages

Add these packages to your project's requirements:

```bash
pip install llama-index==0.9.2 openai==1.3.0 python-dotenv==1.0.0 selenium==4.14.0 nltk==3.8.1
```

### 2. Copy Django App Files

Copy the `chatbot_app` directory to your Django project root.

### 3. Update Django Settings

Add the chatbot app to your `settings.py`:

```python
INSTALLED_APPS = [
    # ... existing apps
    'chatbot_app',
]

# Chatbot settings (optional but recommended)
CHATBOT_SETTINGS = {
    'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY'),
    'VECTOR_DB_PATH': os.path.join(BASE_DIR, 'PKL_file'),
    'TRAINING_DATA_PATH': os.path.join(BASE_DIR, 'data'),
}
```

### 4. Add URL Routes

In your project's `urls.py`, add:

```python
from django.urls import path, include

urlpatterns = [
    # ... existing patterns
    path('api/chatbot/', include('chatbot_app.urls')),
]
```

### 5. Copy Data Directories

Copy the following directories to your project root:
- `PKL_file/` - Contains the vector database
- `data/` - Contains training data

### 6. Set Environment Variables

Create or update your `.env` file with:

```
OPENAI_API_KEY=your-api-key-here
```

### 7. Run Migrations

```bash
python manage.py makemigrations chatbot_app
python manage.py migrate
```

### 8. Initialize the Chatbot

```bash
python manage.py init_chatbot
```

This command will scrape default URLs and create embeddings. You can customize it with:

```bash
python manage.py init_chatbot --urls https://your-docs-url.com https://another-url.com
```

### 9. Frontend Integration

#### Copy React Components

Copy these files to your React frontend:
- `react_components/ChatbotButton.jsx` and `ChatbotButton.css`
- `react_components/ChatbotModal.jsx` and `ChatbotModal.css`

#### Add Chatbot to Dashboard

In your dashboard component:

```jsx
import ChatbotButton from '../components/ChatbotButton';

function Dashboard() {
  // Your existing dashboard code
  const [darkMode, setDarkMode] = useState(false);
  
  return (
    <div className="dashboard">
      {/* Dashboard content */}
      <ChatbotButton darkMode={darkMode} />
    </div>
  );
}
```

## Using the Chatbot

The chatbot can:

1. **Create tasks** with natural language:
   - "Add task: Complete project report by Friday"
   - "Create task: Call John regarding the budget tomorrow at 2pm"
   - "Remind me to send the invoice by next Wednesday"

2. **List tasks**:
   - "Show my tasks"
   - "What tasks are due today?"
   - "Show my overdue tasks"

3. **Complete tasks**:
   - "Mark task Project Report as completed"
   - "I finished the budget analysis"

4. **Answer questions**:
   - "How does task prioritization work?"
   - "What is time management?"

## Customization

### Custom Responses

Edit `custom_responses` in `chatbot_app/views.py` to change preset responses.

### UI Customization

Modify the CSS files to match your app's design system:
- `ChatbotButton.css`
- `ChatbotModal.css`

### Task Patterns

Modify regex patterns in `chatbot_app/utils.py` to handle additional task creation formats.

## Troubleshooting

### Common Issues

1. **OpenAI API errors**:
   - Check your API key is valid
   - Ensure your account has sufficient credits

2. **Missing dependencies**:
   - Run `pip install -r requirements.txt`

3. **Model loading errors**:
   - Ensure the PKL_file directory is correctly placed
   - Reinitialize with `python manage.py init_chatbot`

4. **Task creation issues**:
   - Check Django logs for detailed error messages
   - Verify the Task model structure matches what's expected in utils.py

### Getting Help

If you encounter issues, please check:
- Django logs for backend errors
- Browser console for frontend errors
- OpenAI API dashboard for API-related errors 
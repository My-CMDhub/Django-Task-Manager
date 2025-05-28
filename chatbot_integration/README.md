# Nexus AI Chatbot

An AI-powered Task Assistant for your Django Nexus application.

![Nexus Chatbot](https://img.shields.io/badge/Task%20Manager-AI%20Chatbot-006622)
![Python 3.8+](https://img.shields.io/badge/Python-3.8+-blue)
![Django 4.0+](https://img.shields.io/badge/Django-4.0+-green)
![React](https://img.shields.io/badge/React-17.0+-61DAFB)

## 🤖 About

This chatbot integrates with your Django Nexus to provide an AI-powered assistant that helps users create and manage tasks through natural language. It supports task creation, listing, updating, and smart responses to productivity-related questions.

## ✨ Features

- **Natural Language Task Creation:** Create tasks by simply typing what you need to do
- **Task Management:** List, update, and mark tasks as completed with conversational commands
- **Smart Responses:** Powered by OpenAI and LlamaIndex for intelligent, context-aware conversations
- **Modern UI:** Sleek React-based chatbot interface that integrates with your dashboard
- **User-Specific Context:** Each user has their own conversation history and task context

## 🛠️ Technology Stack

- **Backend:** Django with Django REST Framework
- **Frontend:** React components that can be integrated with any React app
- **NLP & AI:** OpenAI API + LlamaIndex for RAG (Retrieval Augmented Generation)
- **Database:** Django ORM for conversation storage and task management
- **Authentication:** Works with your existing Django authentication system

## 📚 Files Overview

- `chatbot_app/` - Django application files
  - `models.py` - Database models for conversations and messages
  - `views.py` - API endpoints and message processing
  - `utils.py` - Task parsing and creation utilities
  - `initialize.py` - Chatbot knowledge base initialization
  
- `react_components/` - React UI components
  - `ChatbotButton.jsx` - Toggle button to show/hide the chatbot
  - `ChatbotModal.jsx` - Chatbot interface with message history
  
- `PKL_file/` - Vector database for the chatbot's knowledge
- `data/` - Training data for the chatbot

## 🚀 Quick Start

1. Copy the `chatbot_app` directory to your Django project
2. Add 'chatbot_app' to your INSTALLED_APPS
3. Add API routes to your urls.py
4. Copy PKL_file and data directories to your project root
5. Add the React components to your frontend
6. Run migrations and initialize the chatbot

Detailed instructions are in the [INTEGRATION_GUIDE.md](./INTEGRATION_GUIDE.md) file.

## 💬 Usage Examples

### Creating Tasks
```
User: Add task: Complete the quarterly report by Friday
Bot: I've created your task: "Complete the quarterly report" due on May 12, 2023. Is there anything else you'd like to do?
```

### Listing Tasks
```
User: What are my tasks for today?
Bot: Here are your tasks due today:

1. Team meeting, due May 9, 2023, medium priority
2. Call with client, due May 9, 2023, high priority
```

### Marking Tasks Complete
```
User: Mark task Team meeting as completed
Bot: Great job! I've marked 'Team meeting' as completed.
```

## 🛠️ Customization

You can customize:
- Chatbot responses and phrases
- UI appearance and behavior
- Task parsing patterns
- Knowledge base and training data

See the [INTEGRATION_GUIDE.md](./INTEGRATION_GUIDE.md) for details.

## 📝 Requirements

- Python 3.8+
- Django 4.0+
- React 17.0+
- OpenAI API key

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details. 
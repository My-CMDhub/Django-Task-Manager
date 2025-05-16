# Technical Context

## Technologies Used

### Backend

#### Core Framework
- **Django** (Python web framework)
  - Version: Latest stable (assumed 4.x)
  - Purpose: Backend framework for request handling, database operations, and business logic

#### Database
- **SQLite** (Development)
  - Purpose: Development and testing database
- **PostgreSQL** (Production - via Supabase)
  - Purpose: Production database for robust data storage

#### Authentication
- **Supabase Auth**
  - Purpose: User authentication, registration, and management
  - Features: Email/password auth, social login, JWT tokens

#### Task Processing and Background Jobs
- **Django Signals**
  - Purpose: Event-driven operations like notifications and background processing

### Frontend

#### Templating and Rendering
- **Django Templates**
  - Purpose: Server-side HTML rendering
  - Features: Template inheritance, context variables, filters

#### CSS Framework
- **Bootstrap**
  - Purpose: Responsive design and UI components
  - Version: 5.x (assumed)

#### JavaScript
- **Vanilla JavaScript**
  - Purpose: Enhanced interactivity and animations
- **jQuery** (If used)
  - Purpose: DOM manipulation, AJAX requests

### External Services

#### User Authentication
- **Supabase**
  - Purpose: Authentication and user management
  - Integration: REST API, webhooks

#### Email Delivery
- **SMTP Provider** (Configurable)
  - Purpose: Email notifications and verification

#### Development Tunneling
- **ngrok**
  - Purpose: Expose local server to internet for webhook testing

### Deployment

- **Not specified** but likely supports:
  - Traditional hosting
  - Docker containers
  - Cloud platforms (AWS, Google Cloud, etc.)

## Development Setup

### Local Environment

1. **Python Environment**
   - Python 3.8 or higher
   - Virtual environment (venv)
   - Dependencies managed via pip

2. **Django Project**
   - Django 4.x (assumed)
   - SQLite for development database
   - Environment variables for configuration

3. **External Services Integration**
   - Supabase project for authentication
   - ngrok for exposing local webhooks

### Configuration

- **Environment Variables (.env)**
  - Supabase credentials
  - Django secret key
  - Email service credentials
  - Webhook secrets

### Running the Application

A development script (`run-dev.sh`) is provided that:
1. Starts ngrok to expose the local server
2. Updates the .env file with the ngrok URL
3. Starts the Django development server

## Technical Constraints

### Authentication Flow

The application uses a hybrid authentication approach:
- Supabase for primary auth (registration, login, password reset)
- Local Django auth for session management
- Webhooks sync users between systems

This introduces complexity in user state management between the two systems.

### Database Schema

The application uses:
- UUID primary keys throughout for distributed compatibility
- Extensive relationship modeling
- Signals for event handling on model changes

### API Design

The API follows REST principles:
- Resource-based endpoints
- Standard HTTP methods
- Authentication via tokens

### Performance Considerations

1. **Database Query Optimization**
   - Proper indexing for UUID fields
   - Query optimization for relationship traversal
   - Limiting queries in loops

2. **View Performance**
   - Pagination for list views
   - Caching where appropriate
   - Deferred loading of large data sets

3. **Background Processing**
   - Signal handlers for asynchronous tasks
   - Email sending outside request-response cycle

## Dependencies

The application has these key dependencies (based on typical Django project):

```
# Web Framework
Django>=4.0.0

# Environment Variables
python-dotenv

# Supabase Integration
supabase-py
jwt

# Database
psycopg2-binary  # For PostgreSQL

# Development
django-debug-toolbar

# Utilities
Pillow  # For image processing
python-dateutil
requests
```

Additional dependencies may be added as needed for specific features.

## Development Workflow

1. **Local Development**
   - Run `run-dev.sh` to start development environment
   - Access the application at localhost:8000
   - Use ngrok URL for webhook testing

2. **Authentication Testing**
   - Configure Supabase webhook to point to ngrok URL
   - Test user registration and login flows
   - Monitor webhook synchronization

3. **Code Organization**
   - Django apps for modularity (auth_app, tasks, etc.)
   - Views organized by functionality
   - Models reflect business domain 
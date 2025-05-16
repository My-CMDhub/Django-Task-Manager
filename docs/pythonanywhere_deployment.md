# Task Manager - PythonAnywhere Deployment Guide

This guide provides step-by-step instructions for deploying the Task Manager application to PythonAnywhere.

## Prerequisites

- PythonAnywhere account (free tier is sufficient for this lab exercise)
- Git repository access for the Task Manager project
- Supabase and OpenAI API keys (if using those features)

## Step 1: Set up PythonAnywhere

1. Sign up for a PythonAnywhere account if you don't have one at [https://www.pythonanywhere.com/](https://www.pythonanywhere.com/)
2. Once logged in, go to the Dashboard

## Step 2: Clone the Repository

1. Open a Bash console from the PythonAnywhere dashboard
2. Clone the repository:
   ```
   git clone https://github.com/yourusername/Task_Manager.git
   cd Task_Manager
   git checkout production
   ```

## Step 3: Create a Virtual Environment

1. In the Bash console, create a virtual environment:
   ```
   mkvirtualenv --python=python3.9 task_manager_env
   ```
2. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

## Step 4: Configure the Web App

1. Go to the "Web" tab in the PythonAnywhere dashboard
2. Click "Add a new web app"
3. Choose "Manual configuration"
4. Select Python 3.9
5. Enter the path to your project: `/home/yourusername/Task_Manager`

## Step 5: Configure the WSGI File

1. Click on the WSGI configuration file link in the Web tab
2. Replace the contents with the code from `mysite/pythonanywhere_wsgi.py`
3. Update the following settings in the file:
   - Replace `yourusername` with your PythonAnywhere username
   - Set a secure `SECRET_KEY` 
   - Add your Supabase API keys
   - Update the domain name
   - Add your OpenAI API key (if using the chatbot)

## Step 6: Configure Static Files

1. Go to the "Static Files" section in the Web tab
2. Add a static files mapping:
   - URL: `/static/`
   - Directory: `/home/yourusername/Task_Manager/staticfiles`
3. In your Bash console, run:
   ```
   python manage.py collectstatic --settings=mysite.production_settings
   ```

## Step 7: Configure Virtual Environment

1. Go to the "Virtualenv" section in the Web tab
2. Enter: `/home/yourusername/.virtualenvs/task_manager_env`

## Step 8: Apply Database Migrations

1. In the Bash console, run:
   ```
   python manage.py migrate --settings=mysite.production_settings
   ```

## Step 9: Create a Superuser

1. In the Bash console, run:
   ```
   python manage.py createsuperuser --settings=mysite.production_settings
   ```

## Step 10: Reload the Web App

1. Click the "Reload" button in the Web tab

## Step 11: Test the Deployment

1. Visit your site at `yourusername.pythonanywhere.com`
2. Test the main functionality:
   - User registration and login
   - Task creation and management
   - Project creation and management

## Troubleshooting

- **Static files not loading**: Check the static files configuration and run collectstatic again
- **Database errors**: Check that migrations have been applied correctly
- **500 errors**: Check the error logs in the Web tab
- **API connections failing**: Verify API keys in the WSGI file

## Security Considerations

- Keep your API keys secure and never commit them to public repositories
- Regularly update your dependencies
- Enable HTTPS for production environments

## Maintenance

- Pull updates from the repository as needed
- Run migrations after updates
- Collect static files after frontend changes

This deployment uses a SQLite database, which is suitable for this lab exercise. For a production environment with multiple users, consider upgrading to a MySQL database (available on paid PythonAnywhere plans). 
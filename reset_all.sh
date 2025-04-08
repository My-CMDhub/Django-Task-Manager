#!/bin/bash

# Display banner
echo "====================================="
echo "  Task Manager - Complete Reset Tool "
echo "====================================="
echo ""
echo "This script will:"
echo "1. Remove all users from both Django and Supabase"
echo "2. Verify the cleanup was successful"
echo "3. Restart the Django development server"
echo ""
echo "WARNING: All user data will be permanently deleted!"
echo ""

# Ask for confirmation
read -p "Are you sure you want to proceed? (yes/no): " confirm
if [[ "$confirm" != "yes" ]]; then
    echo "Operation cancelled."
    exit 1
fi

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Step 1: Run the cleanup command
echo ""
echo "Step 1: Removing all users..."
python manage.py cleanup_users --confirm

# Step 2: Verify the cleanup
echo ""
echo "Step 2: Verifying cleanup..."
python manage.py verify_clean

# Step 3: Ask if user wants to restart the server
echo ""
echo "Step 3: Restart the server"
read -p "Would you like to restart the Django server now? (yes/no): " restart_server
if [[ "$restart_server" == "yes" ]]; then
    echo "Restarting Django server..."
    # Kill any existing Django process
    pkill -f "python manage.py runserver" || true
    # Start the server (background)
    python manage.py runserver &
    echo "Server started at http://127.0.0.1:8000/"
    echo "Visit http://127.0.0.1:8000/auth/register/ to create a new account"
else
    echo ""
    echo "You can start the server manually with: python manage.py runserver"
    echo "Then visit: http://127.0.0.1:8000/auth/register/ to create a new account"
fi

echo ""
echo "====================================="
echo "Reset process completed!"
echo "=====================================" 
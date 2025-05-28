#!/bin/bash

# Display banner
echo "====================================="
echo "  Nexus - User Reset Script  "
echo "====================================="
echo ""
echo "This script will completely reset all users from both Django and Supabase databases."
echo "Use this when you want to start fresh or troubleshoot authentication issues."
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Run the cleanup script
echo "Executing user cleanup script..."
python cleanup.py

# Provide instructions after cleanup
echo ""
echo "====================================="
echo "  Next Steps  "
echo "====================================="
echo "1. Restart the Django server"
echo "2. Register a new account at http://127.0.0.1:8000/auth/register/"
echo "3. Verify your email when prompted"
echo ""
echo "If you encounter any issues, check the logs in the logs/ directory" 
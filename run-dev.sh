#!/bin/bash

# Colors for nicer output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting Nexus Development Environment${NC}"
echo -e "${BLUE}===============================================${NC}"

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    echo -e "${RED}Error: ngrok is not installed or not in your PATH${NC}"
    echo -e "Please install ngrok from https://ngrok.com/download"
    exit 1
fi

# Check if Django is installed
if ! python -c "import django" &> /dev/null; then
    echo -e "${RED}Error: Django is not installed${NC}"
    echo -e "Please run: pip install -r requirements.txt"
    exit 1
fi

# Create a logs directory if it doesn't exist
mkdir -p logs

# Kill any existing ngrok processes to ensure clean start
echo -e "${YELLOW}Checking for existing ngrok processes...${NC}"
pkill -f ngrok || true
sleep 1

# Start ngrok in the background with clean state
echo -e "${YELLOW}Starting ngrok with fresh session...${NC}"
ngrok http 8000 > /dev/null &
NGROK_PID=$!

# Give ngrok a moment to start up
echo -e "${YELLOW}Waiting for ngrok to initialize...${NC}"
sleep 3

# Get the ngrok public URL (with retries)
MAX_RETRIES=5
RETRY_COUNT=0
NGROK_URL=""

while [ -z "$NGROK_URL" ] && [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    NGROK_URL=$(curl -s http://localhost:4040/api/tunnels | grep -o '"public_url":"https://[^"]*' | grep -o 'https://[^"]*')
    
    if [ -z "$NGROK_URL" ]; then
        RETRY_COUNT=$((RETRY_COUNT+1))
        echo -e "${YELLOW}Waiting for ngrok URL (attempt $RETRY_COUNT of $MAX_RETRIES)...${NC}"
        sleep 2
    fi
done

if [ -z "$NGROK_URL" ]; then
    echo -e "${RED}Failed to get ngrok URL after multiple attempts. Make sure ngrok is running correctly.${NC}"
    kill $NGROK_PID
    exit 1
fi

echo -e "${GREEN}ngrok is running at: ${NGROK_URL}${NC}"

# Update environment variables for the current session
export NGROK_URL=$NGROK_URL
export SUPABASE_SITE_URL=$NGROK_URL
export SITE_URL=$NGROK_URL
export SITE_DOMAIN=$(echo $NGROK_URL | sed 's/https:\/\///')
export SITE_PROTOCOL="https"
export SUPPRESS_EMAIL_WARNINGS=true
export SUPABASE_SYNC_ENABLED=true

# Update .env file with new ngrok URL (with OS-specific handling)
if [ -f ".env" ]; then
    echo -e "${YELLOW}Updating .env file with new ngrok URL...${NC}"
    
    # Detect OS for sed command compatibility
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        sed -i '' "s|NGROK_URL=.*|NGROK_URL=${NGROK_URL}|g" .env
        sed -i '' "s|SUPABASE_SITE_URL=.*|SUPABASE_SITE_URL=${NGROK_URL}|g" .env
        sed -i '' "s|SITE_URL=.*|SITE_URL=${NGROK_URL}|g" .env
        sed -i '' "s|SITE_DOMAIN=.*|SITE_DOMAIN=${SITE_DOMAIN}|g" .env
        sed -i '' "s|SITE_PROTOCOL=.*|SITE_PROTOCOL=${SITE_PROTOCOL}|g" .env
        sed -i '' "s|SUPPRESS_EMAIL_WARNINGS=.*|SUPPRESS_EMAIL_WARNINGS=true|g" .env
        sed -i '' "s|SUPABASE_SYNC_ENABLED=.*|SUPABASE_SYNC_ENABLED=true|g" .env
    else
        # Linux/other
        sed -i "s|NGROK_URL=.*|NGROK_URL=${NGROK_URL}|g" .env
        sed -i "s|SUPABASE_SITE_URL=.*|SUPABASE_SITE_URL=${NGROK_URL}|g" .env
        sed -i "s|SITE_URL=.*|SITE_URL=${NGROK_URL}|g" .env
        sed -i "s|SITE_DOMAIN=.*|SITE_DOMAIN=${SITE_DOMAIN}|g" .env
        sed -i "s|SITE_PROTOCOL=.*|SITE_PROTOCOL=${SITE_PROTOCOL}|g" .env
        sed -i "s|SUPPRESS_EMAIL_WARNINGS=.*|SUPPRESS_EMAIL_WARNINGS=true|g" .env
        sed -i "s|SUPABASE_SYNC_ENABLED=.*|SUPABASE_SYNC_ENABLED=true|g" .env
    fi
    
    # Add any missing variables
    grep -q "NGROK_URL=" .env || echo "NGROK_URL=${NGROK_URL}" >> .env
    grep -q "SUPABASE_SITE_URL=" .env || echo "SUPABASE_SITE_URL=${NGROK_URL}" >> .env
    grep -q "SITE_URL=" .env || echo "SITE_URL=${NGROK_URL}" >> .env
    grep -q "SITE_DOMAIN=" .env || echo "SITE_DOMAIN=${SITE_DOMAIN}" >> .env
    grep -q "SITE_PROTOCOL=" .env || echo "SITE_PROTOCOL=${SITE_PROTOCOL}" >> .env
    grep -q "SUPPRESS_EMAIL_WARNINGS=" .env || echo "SUPPRESS_EMAIL_WARNINGS=true" >> .env
    grep -q "SUPABASE_SYNC_ENABLED=" .env || echo "SUPABASE_SYNC_ENABLED=true" >> .env
    
    echo -e "${GREEN}.env file updated successfully!${NC}"
else
    echo -e "${YELLOW}Creating new .env file...${NC}"
    cat > .env << EOF
NGROK_URL=${NGROK_URL}
SUPABASE_SITE_URL=${NGROK_URL}
SITE_URL=${NGROK_URL}
SITE_DOMAIN=${SITE_DOMAIN}
SITE_PROTOCOL=${SITE_PROTOCOL}
SUPPRESS_EMAIL_WARNINGS=true
SUPABASE_SYNC_ENABLED=true
EOF
    echo -e "${GREEN}.env file created successfully!${NC}"
fi

# Print configuration information
echo -e "${BLUE}Configuration:${NC}"
echo -e "${YELLOW}NGROK_URL:${NC} $NGROK_URL"
echo -e "${YELLOW}SITE_DOMAIN:${NC} $SITE_DOMAIN"
echo -e "${YELLOW}WEBHOOK URL:${NC} $NGROK_URL/auth/webhooks/supabase/"
echo -e "${YELLOW}LOCAL URL:${NC} http://127.0.0.1:8000 (also available while this script runs)"

# Run initial synchronization to ensure systems are in sync (prioritizing Supabase)
echo -e "\n${BLUE}Performing initial user synchronization...${NC}"
echo -e "${CYAN}Supabase will be treated as the source of truth${NC}"
python manage.py sync_users --direction=to-django --force > logs/initial_sync.log 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Initial user synchronization completed. See logs/initial_sync.log for details.${NC}"
else
    echo -e "${RED}Initial user synchronization failed. See logs/initial_sync.log for errors.${NC}"
fi

# Display instructions for Supabase webhook setup
echo -e "\n${BLUE}IMPORTANT: Set up the following webhook in your Supabase project:${NC}"
echo -e "${YELLOW}1. Go to your Supabase dashboard > Project Settings > API${NC}"
echo -e "${YELLOW}2. Scroll down to 'Webhooks' section${NC}"
echo -e "${YELLOW}3. Add a new webhook with the following settings:${NC}"
echo -e "   - Name: ${GREEN}django-sync${NC}"
echo -e "   - URL: ${GREEN}${NGROK_URL}/auth/webhooks/supabase/${NC}"
echo -e "   - Events: Select ${GREEN}user.created${NC}, ${GREEN}user.updated${NC}, and ${GREEN}user.deleted${NC}"
echo -e "   - Secret: ${GREEN}***REMOVED***${NC} (or the value from your SUPABASE_WEBHOOK_SECRET env var)"
echo -e "${YELLOW}4. Save the webhook${NC}"

echo -e "\n${BLUE}Testing your setup:${NC}"
echo -e "${YELLOW}1. Visit ${GREEN}${NGROK_URL}/auth/sync-status/${NC} to check connection status${NC}"
echo -e "${YELLOW}2. Use ${GREEN}${NGROK_URL}/auth/test-webhook/${NC} to test the webhook integration${NC}"

# Function to handle cleanup when the script is terminated
cleanup() {
    echo -e "\n${YELLOW}Shutting down development environment...${NC}"
    
    # Kill ngrok
    if [ ! -z "$NGROK_PID" ]; then
        echo -e "${YELLOW}Stopping ngrok...${NC}"
        kill $NGROK_PID 2>/dev/null || true
    fi
    
    # Kill any Python processes we started
    if [ ! -z "$DJANGO_PID" ]; then
        echo -e "${YELLOW}Stopping Django server...${NC}"
        kill $DJANGO_PID 2>/dev/null || true
    fi
    
    if [ ! -z "$MONITOR_PID" ]; then
        echo -e "${YELLOW}Stopping user monitor...${NC}"
        kill $MONITOR_PID 2>/dev/null || true
    fi
    
    echo -e "${GREEN}Environment shutdown complete. Goodbye!${NC}"
    exit 0
}

# Set up trap to call cleanup function when script is terminated
trap cleanup INT TERM

# Start Django server in the background
echo -e "\n${BLUE}Starting Django development server...${NC}"
python manage.py runserver 0.0.0.0:8000 > logs/django.log 2>&1 &
DJANGO_PID=$!

# Give Django a moment to start
sleep 3

# Start user monitoring in a separate window
echo -e "\n${BLUE}Starting enhanced real-time user monitoring and synchronization...${NC}"
echo -e "${CYAN}Supabase is the source of truth - Django will sync to match Supabase${NC}"
python monitor_users.py &
MONITOR_PID=$!

echo -e "\n${GREEN}✅ Development environment is running!${NC}"
echo -e "${BLUE}===================================${NC}"
echo -e "${MAGENTA}Your application is ready at:${NC}"
echo -e "${GREEN}➡ LOCAL URL: ${YELLOW}http://127.0.0.1:8000${NC}"
echo -e "${GREEN}➡ PUBLIC URL: ${YELLOW}${NGROK_URL}${NC}"
echo -e "${BLUE}===================================${NC}"
echo -e "${BLUE}Admin interface: ${YELLOW}http://127.0.0.1:8000/admin/${NC}"
echo -e "${BLUE}Sync status: ${YELLOW}http://127.0.0.1:8000/auth/sync-status/${NC}"
echo -e "\n${BLUE}Log files:${NC}"
echo -e "${YELLOW}Django server log:${NC} logs/django.log"
echo -e "${YELLOW}Webhook events log:${NC} logs/webhook.log"
echo -e "${YELLOW}User monitoring log:${NC} logs/user_monitor.log"
echo -e "${YELLOW}Synchronization log:${NC} logs/sync.log"
echo -e "\n${MAGENTA}Press Ctrl+C to stop the environment${NC}"

# Keep the script running until Ctrl+C or server stops
wait $DJANGO_PID

# Call cleanup in case the server stops on its own
cleanup 
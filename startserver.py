#!/usr/bin/env python
"""
Startup script for the Nexus application that handles:
1. Starting ngrok for a public URL
2. Starting the Django server
3. Updating Supabase webhook URLs
"""
import os
import sys
import subprocess
import time
import requests
import json
import signal
import webbrowser
import argparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def parse_arguments():
    parser = argparse.ArgumentParser(description='Start the Nexus with Supabase integration')
    parser.add_argument('--no-ngrok', action='store_true', help='Skip starting ngrok')
    parser.add_argument('--port', type=int, default=8000, help='Port for Django server')
    parser.add_argument('--no-browser', action='store_true', help='Don\'t open browser')
    parser.add_argument('--update-webhook', action='store_true', help='Update Supabase webhook URL')
    return parser.parse_args()

def start_ngrok(port):
    print("Starting ngrok to get a public URL...")
    
    # Start ngrok process
    try:
        ngrok_process = subprocess.Popen(
            ["ngrok", "http", str(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        print(f"ngrok started with PID: {ngrok_process.pid}")
        
        # Wait for ngrok to initialize
        time.sleep(2)
        
        # Get the public URL
        try:
            response = requests.get("http://localhost:4040/api/tunnels")
            tunnels = response.json()["tunnels"]
            
            if tunnels:
                # Prefer HTTPS URL
                https_url = None
                for tunnel in tunnels:
                    if tunnel["proto"] == "https":
                        https_url = tunnel["public_url"]
                        break
                
                if https_url:
                    print(f"ngrok URL: {https_url}")
                    return ngrok_process, https_url
                else:
                    public_url = tunnels[0]["public_url"]
                    print(f"ngrok URL: {public_url}")
                    return ngrok_process, public_url
        except Exception as e:
            print(f"Error getting ngrok URL: {str(e)}")
        
        return ngrok_process, None
    except Exception as e:
        print(f"Error starting ngrok: {str(e)}")
        return None, None

def update_env_file(public_url):
    """Update .env file with the ngrok URL"""
    try:
        env_path = '.env'
        env_vars = {}
        
        # Read existing .env if it exists
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        env_vars[key] = value
        
        # Update values
        env_vars['SUPABASE_SITE_URL'] = public_url
        env_vars['SITE_DOMAIN'] = public_url.replace('https://', '').replace('http://', '')
        env_vars['SITE_PROTOCOL'] = 'https' if public_url.startswith('https://') else 'http'
        
        # Write back to .env
        with open(env_path, 'w') as f:
            for key, value in env_vars.items():
                f.write(f"{key}={value}\n")
        
        print(f"Updated .env file with ngrok URL: {public_url}")
        return True
    except Exception as e:
        print(f"Error updating .env file: {str(e)}")
        return False

def update_supabase_webhook(public_url):
    """Display instructions for updating Supabase webhook URL"""
    webhook_url = f"{public_url}/auth/webhooks/supabase/"
    
    print("\n=====================================================")
    print("IMPORTANT: Update your Supabase webhook URL")
    print("=====================================================")
    print(f"Webhook URL: {webhook_url}")
    print("\nInstructions:")
    print("1. Go to your Supabase dashboard")
    print("2. Navigate to Authentication > Webhooks")
    print("3. Update the webhook URL with the one shown above")
    print("4. Save your changes")
    print("=====================================================\n")
    
    # Try to open Supabase dashboard
    try:
        supabase_url = os.environ.get('SUPABASE_URL', '')
        if supabase_url:
            dashboard_url = f"{supabase_url}/project/auth/auth-webhooks"
            print(f"Opening Supabase dashboard: {dashboard_url}")
            webbrowser.open(dashboard_url)
    except Exception as e:
        print(f"Could not open Supabase dashboard: {str(e)}")

def start_django_server(port):
    """Start the Django development server"""
    print(f"\nStarting Django server on port {port}...")
    os.environ['DJANGO_SETTINGS_MODULE'] = 'mysite.settings'
    
    try:
        # Start Django server using Python subprocess
        django_process = subprocess.Popen(
            [sys.executable, "manage.py", "runserver", f"0.0.0.0:{port}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            bufsize=1
        )
        
        print(f"Django server started with PID: {django_process.pid}")
        
        # Show Django output
        for line in iter(django_process.stdout.readline, ""):
            print(line, end="")
        
        return django_process
    except Exception as e:
        print(f"Error starting Django server: {str(e)}")
        return None

def handle_exit(ngrok_process=None, django_process=None):
    """Clean up processes on exit"""
    print("\nShutting down...")
    
    if ngrok_process and ngrok_process.poll() is None:
        print("Terminating ngrok...")
        ngrok_process.terminate()
        ngrok_process.wait(timeout=5)
    
    if django_process and django_process.poll() is None:
        print("Terminating Django server...")
        django_process.terminate()
        django_process.wait(timeout=5)
    
    print("Cleanup complete. Goodbye!")
    sys.exit(0)

def main():
    args = parse_arguments()
    ngrok_process = None
    django_process = None
    
    # Set up signal handlers for clean exit
    def signal_handler(sig, frame):
        handle_exit(ngrok_process, django_process)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Start ngrok if not disabled
        if not args.no_ngrok:
            ngrok_process, public_url = start_ngrok(args.port)
            
            if public_url:
                # Update .env file
                update_env_file(public_url)
                
                # Open admin dashboard if not disabled
                if not args.no_browser:
                    webbrowser.open("http://localhost:4040")
                
                # Update Supabase webhook if requested
                if args.update_webhook:
                    update_supabase_webhook(public_url)
        
        # Start Django server
        django_process = start_django_server(args.port)
        
        # Keep main thread alive
        while django_process and django_process.poll() is None:
            time.sleep(0.5)
        
        # If Django process ended, also end ngrok
        handle_exit(ngrok_process, None)
        
    except KeyboardInterrupt:
        handle_exit(ngrok_process, django_process)
    except Exception as e:
        print(f"Error in main process: {str(e)}")
        handle_exit(ngrok_process, django_process)

if __name__ == "__main__":
    main() 
# Task Manager with AI Automation ChatBot 📝 🤖

A Django-based task manager application with Supabase integration for authentication.

## Table of Contents
- [Prerequisites](#prerequisites)
- [Initial Setup](#initial-setup)
  - [Setting up Supabase](#setting-up-supabase)
  - [Setting up ngrok](#setting-up-ngrok)
  - [Local Environment Setup](#local-environment-setup)
- [Configuration](#configuration)
  - [Environment Variables](#environment-variables)
  - [Supabase Webhook Setup](#supabase-webhook-setup)
- [Running the Application](#running-the-application)
- [Troubleshooting](#troubleshooting)

## Prerequisites

Before you begin, ensure you have the following installed:
- Python 3.8 or higher
- pip (Python package installer)
- Git
- A text editor of your choice

## Initial Setup

### Setting up Supabase

1. **Create a Supabase Account**
   - Visit [supabase.com](https://supabase.com)
   - Click "Start your project" or "Sign Up"
   - Sign up using your GitHub account or email

2. **Create a New Project**
   - After logging in, click "New Project"
   - Choose a name for your project (e.g., "task-manager")
   - Choose a database password (save this for later)
   - Select your region (choose the closest to your location)
   - Click "Create new project"

3. **Get Your API Keys**
   - Once your project is created, go to Project Settings (gear icon)
   - Click on "API" in the sidebar
   - You'll find two important keys:
     - `anon public` key (labeled as `SUPABASE_KEY` or `SUPABASE_ANON_KEY`)
     - `service_role` key (labeled as `SUPABASE_SERVICE_KEY`)
   - Copy both keys and save them for later
   - Also copy your Supabase project URL (labeled as `SUPABASE_URL`)

   ![Supabase API Settings](docs/images/supabase_api_settings.png)
   > Note: As shown in the image, Supabase will be changing the API key names from 'anon' and 'service_role' to 'publishable' and 'secret' in Q2 2025. The functionality remains the same.

4. **Enable Email Authentication**
   - In the Supabase dashboard, go to "Authentication" → "Providers"
   - Enable "Email" provider
   - Under "SMTP Settings":
     - Toggle "Enable custom SMTP server"
     - Save the settings (we'll configure SMTP later through the application)

### Setting up ngrok

1. **Create an ngrok Account**
   - Visit [ngrok.com](https://ngrok.com)
   - Sign up for a free account
   - After signing up, you'll be taken to the setup page

2. **Install ngrok**
   - Download ngrok for your operating system from the setup page
   - Extract the downloaded file
   - Move the ngrok executable to a location in your PATH or note its location

3. **Configure ngrok**
   - Copy your authtoken from the ngrok dashboard
   - Run: `ngrok config add-authtoken YOUR_TOKEN`

### Local Environment Setup

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd Task_Manager
   ```

2. **Create and Activate Virtual Environment**
   ```bash
   # On Windows
   python -m venv venv
   venv\Scripts\activate

   # On macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

### Environment Variables

1. **Create .env File**
   - Copy the example environment file:
     ```bash
     cp .env.example .env
     ```
   - Open `.env` in your text editor

2. **Add Your Credentials**
   ```plaintext
   SUPABASE_URL=your_project_url
   SUPABASE_KEY=your_anon_key
   SUPABASE_SERVICE_KEY=your_service_role_key
   SUPABASE_WEBHOOK_SECRET=create_a_random_secret_here
   SECRET_KEY=django_secret_key_here
   ```
   Replace the placeholders with your actual values:
   - `your_project_url`: Your Supabase project URL
   - `your_anon_key`: Your Supabase anon/public key
   - `your_service_role_key`: Your Supabase service role key
   - `create_a_random_secret_here`: Create a random string for webhook verification
   - `django_secret_key_here`: Create a random string for Django's SECRET_KEY

### Supabase Webhook Setup

The webhook setup will be handled automatically when you run the application. You'll receive clear instructions in the terminal.

## Running the Application

1. **Start the Application**
   activate your virtual environment first by running this command:
   ```
   source venv/bin/activate (it might be different for Window)
   ```
   ```bash
   # Make the script executable (macOS/Linux)
   chmod +x run-dev.sh

   # Run the application
   ./run-dev.sh
   ```

2. **Follow the Terminal Instructions**
   - The script will start ngrok and Django
   - It will display your public ngrok URL
   - It will provide instructions for setting up the Supabase webhook

3. **Configure Webhook in Supabase**
   - Follow the instructions displayed in the terminal
   - Copy the webhook URL
   - Add it to your Supabase project settings

4. **Access the Application**
   - Local URL: http://127.0.0.1:8000
   - Public URL: Your ngrok URL (shown in terminal)

## Troubleshooting

### Common Issues

1. **ngrok Not Found**
   - Ensure ngrok is installed and in your PATH
   - Or specify the path to ngrok in your .env file:
     ```
     NGROK_PATH=/path/to/ngrok
     ```

2. **Email Verification Not Working**
   - Go to `/auth/setup-smtp/` in your application
   - Configure your SMTP settings
   - Test the email sending functionality

3. **Webhook Not Working**
   - Check if ngrok is running (should see URL in terminal)
   - Verify webhook URL in Supabase matches your ngrok URL
   - Check webhook secret matches in both places

4. **User Synchronization Issues**
   - Use the sync command:
     ```bash
     python manage.py sync_users --direction=both
     ```
   - Check the logs in the `logs/` directory

### Getting Help

If you encounter any issues:
1. Check the application logs in the `logs/` directory
2. Verify all environment variables are set correctly
3. Ensure Supabase and ngrok are properly configured.  
## **At Last contact Mr. DHRUV PATEL 😎**

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Based on the development roadmap in `Development/development.md`
- Built with Supabase for authentication
- Uses Django framework 
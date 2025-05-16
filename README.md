# Task Manager with AI Automation ChatBot 📝 🤖

A Django-based task manager application with Supabase integration for authentication.

---

## Table of Contents
- [Project Overview](#project-overview)
- [Prerequisites](#prerequisites)
- [Step 1: Setting Up Supabase (Authentication & SMTP)](#step-1-setting-up-supabase-authentication--smtp)
- [Step 2: Setting Up ngrok (Mac & Windows)](#step-2-setting-up-ngrok-mac--windows)
- [Step 3: Local Django Environment Setup](#step-3-local-django-environment-setup)
- [Step 4: Configuration (Environment Variables)](#step-4-configuration-environment-variables)
- [Step 5: Running the Application](#step-5-running-the-application)
- [Step 6: Supabase Webhook Setup](#step-6-supabase-webhook-setup)
- [Troubleshooting & FAQ](#troubleshooting--faq)
- [Getting Help](#getting-help)
- [License](#license)
- [🚨 Critical Setup Tips & Common Mistakes 🚨](#-critical-setup-tips--common-mistakes-)
- [✉️ How to Use a Custom Email Template in Supabase](#️-how-to-use-a-custom-email-template-in-supabase)
- [Deployment to Render](#deployment-to-render)

---

## Project Overview

This project is a full-featured task manager built with Django and enhanced with AI automation. It uses [Supabase](https://supabase.com) for user authentication and leverages [ngrok](https://ngrok.com) to make your local development server accessible on the internet for webhook and email verification flows.

---

## Prerequisites

Before you begin, make sure you have the following:
- **Python 3.8 or higher** ([Download Python](https://www.python.org/downloads/))
- **pip** (comes with Python)
- **Git** ([Download Git](https://git-scm.com/downloads))
- **A text editor** (e.g., VS Code, Sublime Text, Notepad++)
- **A Supabase account** ([Sign up here](https://supabase.com))
- **An ngrok account** ([Sign up here](https://ngrok.com))

---

## Step 1: Setting Up Supabase (Authentication & SMTP)

### 1.1 Create a Supabase Project
1. Go to [supabase.com](https://supabase.com) and sign up/log in.
2. Click **New Project**.
3. Enter a project name, strong database password, and select a region.
4. Click **Create new project**. Wait for the database to initialize (may take a few minutes).

### 1.2 Get Your Supabase API Keys
1. In your Supabase dashboard, go to **Project Settings** (gear icon).
2. Click **API** in the sidebar.
3. Copy the following:
   - **Project URL** (e.g., `https://xyzcompany.supabase.co`)
   - **anon/public key** (for client-side, called `SUPABASE_ANON_KEY`)
   - **service_role key** (for admin/server-side, called `SUPABASE_SERVICE_KEY`)

### 1.3 Enable Email Authentication
1. In the dashboard, go to **Authentication > Providers**.
2. Enable the **Email** provider.
3. (Optional but recommended) Enable **Email Confirmations** for new signups.

### 1.4 Configure Custom SMTP (for production or real email delivery)
Supabase provides a default SMTP server for testing, but you should set up your own for production or to send emails to real users.

1. Go to **Authentication > Settings > SMTP Settings**.
2. Toggle **Enable Custom SMTP**.
3. Enter your SMTP provider details (e.g., Gmail, SendGrid, AWS SES, etc.):
   - **Sender Email**: e.g., `no-reply@yourdomain.com`
   - **Sender Name**: e.g., `Task Manager`
   - **SMTP Host**: e.g., `smtp.gmail.com`
   - **SMTP Port**: e.g., `465` (SSL) or `587` (TLS)
   - **SMTP Username**: your email address or username
   - **SMTP Password**: your app password (for Gmail, you must [enable 2FA and create an app password](https://support.google.com/accounts/answer/185833))
4. Click **Save**.
5. Test by inviting a user from the **Users** tab or using the app's registration flow.

**Tip:** For Gmail, use `smtp.gmail.com` with port 465 (SSL) or 587 (TLS). You must use an [App Password](https://support.google.com/accounts/answer/185833) if 2FA is enabled.

**Troubleshooting:**
- If emails are not delivered, check your SMTP credentials, port, and that your sender email matches your SMTP account.
- For more help, see [Supabase SMTP Docs](https://supabase.com/docs/guides/auth/auth-smtp).

---

## Step 2: Setting Up ngrok (Mac & Windows)

ngrok exposes your local server to the internet, which is required for Supabase webhooks and email verification links.

### 2.1 Install ngrok

#### On Mac:
- **With Homebrew:**
  ```bash
  brew install ngrok/ngrok/ngrok
  ```
- **Without Homebrew:**
  1. Download the latest ngrok binary from [ngrok.com/download](https://ngrok.com/download).
  2. Unzip and move it to `/usr/local/bin`:
     ```bash
     sudo mv ~/Downloads/ngrok /usr/local/bin
     ```
  3. (Optional) Create a symlink if needed:
     ```bash
     sudo ln -s /usr/local/bin/ngrok /usr/bin/ngrok
     ```

#### On Windows:
- Download the latest ngrok binary from [ngrok.com/download](https://ngrok.com/download).
- Unzip it to a folder (e.g., `C:\ngrok`).
- Add the folder to your **PATH** (Control Panel > System > Advanced > Environment Variables).

### 2.2 Connect ngrok to Your Account
1. Log in to your ngrok dashboard and copy your **authtoken**.
2. In your terminal (Mac) or Command Prompt (Windows):
   ```bash
   ngrok config add-authtoken <YOUR_AUTHTOKEN>
   ```

### 2.3 Test ngrok
- Start a tunnel (for example, to port 8000):
  ```bash
  ngrok http 8000
  ```
- You should see a public URL (e.g., `https://xxxx.ngrok-free.app`).

---

## Step 3: Local Django Environment Setup

### 3.1 Clone the Repository
   ```bash
   git clone <repository-url>
   cd Task_Manager
   ```

### 3.2 Create and Activate a Virtual Environment
- **On Windows:**
   ```bash
   python -m venv venv
   venv\Scripts\activate
  ```
- **On Mac/Linux:**
  ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

### 3.3 Install Python Dependencies
   ```bash
   pip install -r requirements.txt
   ```

---

## Step 4: Configuration (Environment Variables)

### 4.1 Create Your `.env` File
1. Copy the example file:
     ```bash
     cp .env.example .env
   # On Windows, use: copy .env.example .env
     ```
2. Open `.env` in your text editor and fill in:
   - `SUPABASE_URL` (from Supabase dashboard)
   - `SUPABASE_ANON_KEY` (from Supabase dashboard)
   - `SUPABASE_SERVICE_KEY` (from Supabase dashboard)
   - `SECRET_KEY` (generate with `python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'`)
   - `SUPABASE_WEBHOOK_SECRET` (any random string)
   - SMTP settings (see your email provider)
   - Other fields as needed (see comments in `.env.example`)

**Example:**
```env
SUPABASE_URL=https://xyzcompany.supabase.co
SUPABASE_ANON_KEY=your_anon_key
   SUPABASE_SERVICE_KEY=your_service_role_key
   SECRET_KEY=django_secret_key_here
SUPABASE_WEBHOOK_SECRET=your_webhook_secret
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SENDER_EMAIL=your_email@gmail.com
SENDER_NAME=Task Manager
```

---

## Step 5: Running the Application

### 5.1 Start the Development Environment
1. **Activate your virtual environment** (see Step 3.2).
2. **Make the script executable (Mac/Linux):**
   ```bash
   chmod +x run-dev.sh
   ```
3. **Run the application:**
   ```bash
   ./run-dev.sh
   ```
   - This script will:
     - Start ngrok and Django
     - Update your `.env` with the ngrok URL
     - Print your public and local URLs
     - Provide instructions for webhook setup

**Note:** If you see an error about port 8000 being in use, stop any other server using that port or change the port in `run-dev.sh` and your Django settings.

---

## Step 6: Supabase Webhook Setup

When you run `./run-dev.sh`, the terminal will display a webhook URL (using your ngrok public URL). You must add this to your Supabase project:

1. In Supabase, go to **Project Settings > API > Webhooks**.
2. Click **Add Webhook**.
3. Enter:
   - **Name:** `django-sync`
   - **URL:** (copy from terminal, e.g., `https://xxxx.ngrok-free.app/auth/webhooks/supabase/`)
   - **Events:** Select `user.created`, `user.updated`, `user.deleted`
   - **Secret:** Use the value from your `.env` (`SUPABASE_WEBHOOK_SECRET`)
4. Save the webhook.

---

## Troubleshooting & FAQ

### ngrok Not Found
- Ensure ngrok is installed and in your PATH.
- On Windows, you may need to restart your terminal after adding ngrok to PATH.

### Email Verification Not Working
- Double-check your SMTP settings in both Supabase and your `.env` file.
- For Gmail, ensure you are using an App Password and have 2FA enabled.
- Try sending a test email from Supabase's **Users** tab.

### Webhook Not Working
- Make sure ngrok is running and the URL matches the one in Supabase.
- Check that the webhook secret matches in both places.
- Check logs in the `logs/` directory for errors.

### Port Already in Use
- Stop any other process using port 8000, or change the port in `run-dev.sh` and Django settings.

### User Synchronization Issues
   - Use the sync command:
     ```bash
     python manage.py sync_users --direction=both
     ```
- Check logs in the `logs/` directory.

### General Tips
- Always activate your virtual environment before running Python/Django commands.
- If you change `.env`, restart your server.
- For Mac users, you may need to allow apps from unidentified developers (System Preferences > Security & Privacy).
- For Windows users, run Command Prompt as Administrator for some commands.

---

## Getting Help

- Check the application logs in the `logs/` directory.
- Review your environment variables and Supabase/ngrok setup.
- Consult the following resources:
  - [Supabase Auth Docs](https://supabase.com/docs/guides/auth)
  - [Supabase SMTP Setup](https://supabase.com/docs/guides/auth/auth-smtp)
  - [ngrok Quickstart](https://ngrok.com/docs/getting-started/)
  - [Django Documentation](https://docs.djangoproject.com/en/stable/)
- If you are still stuck, contact the project maintainer (see below).

---

## License

This project is licensed under the MIT License - see the LICENSE file for details.

---

## Acknowledgments
- Based on the development roadmap in `Development/development.md`
- Built with Supabase for authentication
- Uses Django framework
- Thanks to the open source community for guides and documentation

---

## Maintainer

For further help, contact: **Mr. DHRUV PATEL 😎**

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Based on the development roadmap in `Development/development.md`
- Built with Supabase for authentication
- Uses Django framework 

---

## 🚨 Critical Setup Tips & Common Mistakes 🚨

> **Read this section carefully before you start! It will save you hours of troubleshooting.**

### 1. Virtual Environment & Dependencies
- **Always activate your virtual environment before installing dependencies or running the app.**
  - On Windows: `venv\Scripts\activate`
  - On Mac/Linux: `source venv/bin/activate`
- **Install dependencies only after activating the environment:**
  ```bash
  pip install -r requirements.txt
  ```
- If you see `ModuleNotFoundError`, your environment is probably not activated.

### 2. .env File & Keys
- **Never add extra spaces or line breaks when copy-pasting keys.**
- **Do not wrap values in quotes unless specified.**
- **Every key in `.env` must match exactly what you get from Supabase or your email provider.**
- **If you change `.env`, restart your server/script.**
- **SECRET_KEY**: Generate with:
  ```bash
  python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
  ```
- **SUPABASE_WEBHOOK_SECRET**: Make this a long, random string. It must match in both `.env` and Supabase webhook settings.

### 3. Supabase Setup
- **Enable Email Auth** in Supabase under Authentication > Providers.
- **Copy the correct keys:**
  - `SUPABASE_URL` (Project URL)
  - `SUPABASE_ANON_KEY` (anon/public key)
  - `SUPABASE_SERVICE_KEY` (service_role key)
- **If you change your Supabase SMTP or webhook settings, update your `.env` and restart the app.**

### 4. SMTP & Google App Passwords
- **For Gmail SMTP:**
  - You must enable 2FA on your Google account.
  - Generate an [App Password](https://support.google.com/accounts/answer/185833) and use it as `EMAIL_HOST_PASSWORD` and `SMTP_PASS`.
  - Do NOT use your regular Gmail password!
- **Sender email in Supabase SMTP settings must match your Gmail address.**
- **If emails are not delivered, check your spam folder and SMTP credentials.**

### 5. ngrok & Webhooks
- **ngrok URL changes every time you restart it (unless you have a paid static domain).**
- **Update your `.env` and Supabase webhook URL every time ngrok changes.**
- **If the webhook doesn't work, check that ngrok is running and the URL is correct in Supabase.**

### 6. General
- **If you get 'port already in use', stop other servers or change the port in `run-dev.sh`.**
- **Check logs in the `logs/` directory for errors.**
- **Restart your server after any configuration change.**

---

## ✉️ How to Use a Custom Email Template in Supabase

You can use your own beautiful HTML email for verification emails sent by Supabase. Here's how:

1. **Open the file:**
   - `auth_app/templates/emails/verification_email.html`
2. **Copy the entire contents** of this file.
3. **Go to your Supabase dashboard:**
   - Navigate to your project.
   - Go to **Authentication > Templates** (or **Authentication > Email Templates**).
4. **Find the 'Confirm Signup' or 'Email Verification' template.**
5. **Paste the HTML you copied** into the template editor.
6. **Replace variables as needed:**
   - Supabase uses `{{ .SiteURL }}`, `{{ .Token }}`, `{{ .Email }}` etc. You may need to adjust variable names to match Supabase's template syntax. For example:
     - Replace `{{ verify_url }}` with `{{ .ConfirmationURL }}` or the appropriate Supabase variable.
     - Replace `{{ user.email }}` with `{{ .Email }}`.
     - See [Supabase Email Template Docs](https://supabase.com/docs/guides/auth/auth-email-templates) for available variables.
7. **Preview and save the template.**
8. **Test by registering a new user.**

> **Tip:** If you see raw template variables in your email, double-check you used the correct Supabase variable names. 

## Deployment to Render

This application is configured for deployment to [Render](https://render.com/), a cloud hosting platform. The deployment strategy includes:

1. **Production Configuration**:
   - Using `mysite/production_settings.py` which extends the base settings for production
   - `Procfile` defines how to run the application using Gunicorn
   - WhiteNoise middleware for serving static files efficiently

2. **Supabase Integration**:
   - In production, Supabase integration is automatically bypassed (`BYPASS_SUPABASE = True`)
   - Users are automatically verified without requiring email verification
   - The `/auth/auto-verify-users/` endpoint is available for admin users to verify any existing unverified users

3. **Chatbot Integration**:
   - AI-powered chatbot assistant for task management
   - Accessible at `/chatbot/` endpoint
   - Uses OpenAI for natural language interaction
   - Can display task statistics and lists of tasks

4. **Database Configuration**:
   - Using SQLite in Render's persistent storage

### Initial Deployment Steps

1. Create a new Web Service on Render
2. Connect to your GitHub repository
3. Select the production branch
4. Set build command: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
5. Set start command: `gunicorn mysite.wsgi --env DJANGO_SETTINGS_MODULE=mysite.production_settings`
6. Add environment variables:
   - `SECRET_KEY`: Set to a secure random string
   - `OPENAI_API_KEY`: (Optional) Set to enable AI chatbot functionality 
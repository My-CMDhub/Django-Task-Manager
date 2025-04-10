@echo off
setlocal enabledelayedexpansion

echo Starting Task Manager Development Environment
echo ===============================================

REM Check if ngrok is installed
where ngrok >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Error: ngrok is not installed or not in your PATH
    echo Please install ngrok from https://ngrok.com/download
    exit /b 1
)

REM Check if Django is installed
python -c "import django" >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Error: Django is not installed
    echo Please run: pip install -r requirements.txt
    exit /b 1
)

REM Create a logs directory if it doesn't exist
if not exist logs mkdir logs

REM Kill any existing ngrok processes to ensure clean start
echo Checking for existing ngrok processes...
taskkill /f /im ngrok.exe >nul 2>nul

REM Start ngrok in the background
echo Starting ngrok with fresh session...
start /b ngrok http 8000
set NGROK_PID=%ERRORLEVEL%

REM Give ngrok a moment to start up
echo Waiting for ngrok to initialize...
timeout /t 3 >nul

REM Get the ngrok public URL (with retries)
set MAX_RETRIES=5
set RETRY_COUNT=0
set NGROK_URL=

:retry_loop
if defined NGROK_URL goto got_url
if %RETRY_COUNT% geq %MAX_RETRIES% goto ngrok_failed
set /a RETRY_COUNT=%RETRY_COUNT%+1
echo Waiting for ngrok URL (attempt %RETRY_COUNT% of %MAX_RETRIES%)...

REM Try to get the ngrok URL
for /f "tokens=*" %%a in ('curl -s http://localhost:4040/api/tunnels ^| findstr /c:"public_url":"https://"') do (
    for /f "tokens=2 delims=:," %%b in ('echo %%a') do (
        set NGROK_URL=%%b
        set NGROK_URL=!NGROK_URL:"https://=https://!
        set NGROK_URL=!NGROK_URL:"=!
    )
)

if not defined NGROK_URL (
    timeout /t 2 >nul
    goto retry_loop
)

goto got_url

:ngrok_failed
echo Failed to get ngrok URL after multiple attempts. Make sure ngrok is running correctly.
exit /b 1

:got_url
echo ngrok is running at: %NGROK_URL%

REM Extract domain from URL
set SITE_DOMAIN=%NGROK_URL:https://=%
set SITE_PROTOCOL=https

REM Update environment variables for the current session
set SUPABASE_SITE_URL=%NGROK_URL%
set SITE_URL=%NGROK_URL%
set SUPPRESS_EMAIL_WARNINGS=true
set SUPABASE_SYNC_ENABLED=true

REM Update .env file with new ngrok URL
if exist .env (
    echo Updating .env file with new ngrok URL...
    
    REM Create a temporary file
    type nul > .env.tmp
    
    for /f "tokens=*" %%a in (.env) do (
        set line=%%a
        set updated=0
        
        echo !line! | findstr /c:"NGROK_URL=" >nul && (
            echo NGROK_URL=%NGROK_URL%>> .env.tmp
            set updated=1
        )
        
        echo !line! | findstr /c:"SUPABASE_SITE_URL=" >nul && (
            echo SUPABASE_SITE_URL=%NGROK_URL%>> .env.tmp
            set updated=1
        )
        
        echo !line! | findstr /c:"SITE_URL=" >nul && (
            echo SITE_URL=%NGROK_URL%>> .env.tmp
            set updated=1
        )
        
        echo !line! | findstr /c:"SITE_DOMAIN=" >nul && (
            echo SITE_DOMAIN=%SITE_DOMAIN%>> .env.tmp
            set updated=1
        )
        
        echo !line! | findstr /c:"SITE_PROTOCOL=" >nul && (
            echo SITE_PROTOCOL=%SITE_PROTOCOL%>> .env.tmp
            set updated=1
        )
        
        echo !line! | findstr /c:"SUPPRESS_EMAIL_WARNINGS=" >nul && (
            echo SUPPRESS_EMAIL_WARNINGS=true>> .env.tmp
            set updated=1
        )
        
        echo !line! | findstr /c:"SUPABASE_SYNC_ENABLED=" >nul && (
            echo SUPABASE_SYNC_ENABLED=true>> .env.tmp
            set updated=1
        )
        
        if !updated! equ 0 (
            echo !line!>> .env.tmp
        )
    )
    
    REM Check for missing variables and add them
    findstr /c:"NGROK_URL=" .env.tmp >nul || echo NGROK_URL=%NGROK_URL%>> .env.tmp
    findstr /c:"SUPABASE_SITE_URL=" .env.tmp >nul || echo SUPABASE_SITE_URL=%NGROK_URL%>> .env.tmp
    findstr /c:"SITE_URL=" .env.tmp >nul || echo SITE_URL=%NGROK_URL%>> .env.tmp
    findstr /c:"SITE_DOMAIN=" .env.tmp >nul || echo SITE_DOMAIN=%SITE_DOMAIN%>> .env.tmp
    findstr /c:"SITE_PROTOCOL=" .env.tmp >nul || echo SITE_PROTOCOL=%SITE_PROTOCOL%>> .env.tmp
    findstr /c:"SUPPRESS_EMAIL_WARNINGS=" .env.tmp >nul || echo SUPPRESS_EMAIL_WARNINGS=true>> .env.tmp
    findstr /c:"SUPABASE_SYNC_ENABLED=" .env.tmp >nul || echo SUPABASE_SYNC_ENABLED=true>> .env.tmp
    
    REM Replace the original .env file
    move /y .env.tmp .env >nul
    echo .env file updated successfully!
) else (
    echo Creating new .env file...
    (
        echo NGROK_URL=%NGROK_URL%
        echo SUPABASE_SITE_URL=%NGROK_URL%
        echo SITE_URL=%NGROK_URL%
        echo SITE_DOMAIN=%SITE_DOMAIN%
        echo SITE_PROTOCOL=%SITE_PROTOCOL%
        echo SUPPRESS_EMAIL_WARNINGS=true
        echo SUPABASE_SYNC_ENABLED=true
    ) > .env
    echo .env file created successfully!
)

REM Print configuration information
echo Configuration:
echo NGROK_URL: %NGROK_URL%
echo SITE_DOMAIN: %SITE_DOMAIN%
echo WEBHOOK URL: %NGROK_URL%/auth/webhooks/supabase/
echo LOCAL URL: http://127.0.0.1:8000 (also available while this script runs)

REM Run initial synchronization
echo.
echo Performing initial user synchronization...
echo Supabase will be treated as the source of truth
python manage.py sync_users --direction=to-django --force > logs\initial_sync.log 2>&1
if %ERRORLEVEL% equ 0 (
    echo Initial user synchronization completed. See logs\initial_sync.log for details.
) else (
    echo Initial user synchronization failed. See logs\initial_sync.log for errors.
)

REM Display instructions for Supabase webhook setup
echo.
echo IMPORTANT: Set up the following webhook in your Supabase project:
echo 1. Go to your Supabase dashboard ^> Project Settings ^> API
echo 2. Scroll down to 'Webhooks' section
echo 3. Add a new webhook with the following settings:
echo    - Name: django-sync
echo    - URL: %NGROK_URL%/auth/webhooks/supabase/
echo    - Events: Select user.created, user.updated, and user.deleted
echo    - Secret: ***REMOVED*** (or the value from your SUPABASE_WEBHOOK_SECRET env var)
echo 4. Save the webhook

echo.
echo Testing your setup:
echo 1. Visit %NGROK_URL%/auth/sync-status/ to check connection status
echo 2. Use %NGROK_URL%/auth/test-webhook/ to test the webhook integration

REM Start Django server in a new window
echo.
echo Starting Django development server...
start cmd /c "python manage.py runserver 0.0.0.0:8000 > logs\django.log 2>&1"

REM Give Django a moment to start
timeout /t 3 >nul

REM Start user monitoring in a separate window
echo.
echo Starting enhanced real-time user monitoring and synchronization...
echo Supabase is the source of truth - Django will sync to match Supabase
start cmd /c "python monitor_users.py > logs\user_monitor.log 2>&1"

echo.
echo ✅ Development environment is running!
echo ===================================
echo Your application is ready at:
echo ➡ LOCAL URL: http://127.0.0.1:8000
echo ➡ PUBLIC URL: %NGROK_URL%
echo ===================================
echo Admin interface: http://127.0.0.1:8000/admin/
echo Sync status: http://127.0.0.1:8000/auth/sync-status/
echo.
echo Log files:
echo Django server log: logs\django.log
echo Webhook events log: logs\webhook.log
echo User monitoring log: logs\user_monitor.log
echo Synchronization log: logs\sync.log
echo.
echo Press Ctrl+C to stop the environment, then close all windows

REM Keep the script running until Ctrl+C or server stops
pause 
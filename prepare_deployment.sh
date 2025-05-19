#!/bin/bash
#
# Prepare Task Manager for PythonAnywhere deployment
#

echo "Preparing Task Manager for PythonAnywhere deployment..."

# Create the staticfiles directory
mkdir -p staticfiles
echo "Created staticfiles directory"

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --settings=mysite.production_settings --noinput

# Check if logs directory exists, create if not
mkdir -p logs
echo "Created logs directory"

# Create a secure SECRET_KEY (random 50-character string)
SECRET_KEY=$(python -c "import secrets; print(''.join(secrets.choice('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*(-_=+)') for i in range(50)))")
echo "Generated secure SECRET_KEY"

# Create a sample .env file for PythonAnywhere
cat > pythonanywhere.env << EOL
SECRET_KEY='${SECRET_KEY}'
DEBUG=False
DJANGO_SETTINGS_MODULE=mysite.production_settings
SITE_DOMAIN=yourusername.pythonanywhere.com
SITE_PROTOCOL=https
SUPABASE_SITE_URL=https://yourusername.pythonanywhere.com

# Add your API keys here (DO NOT COMMIT THIS FILE)
SUPABASE_URL=your-supabase-url
SUPABASE_KEY=your-supabase-key
SUPABASE_ANON_KEY=your-supabase-anon-key
SUPABASE_SERVICE_KEY=your-supabase-service-key

EOL

echo "Created sample environment file pythonanywhere.env"
echo "IMPORTANT: Update pythonanywhere.env with your actual API keys and domain name"

# Provide instructions
echo ""
echo "=== Deployment Preparation Complete ==="
echo ""
echo "Next steps:"
echo "1. Push your changes to the 'production' branch"
echo "2. Follow the instructions in docs/pythonanywhere_deployment.md"
echo "3. Upload the generated pythonanywhere.env to your PythonAnywhere server"
echo "   (but rename it to .env and don't commit it to your repository)"
echo ""
echo "IMPORTANT: Keep the pythonanywhere.env file secure and don't commit it to git"
echo ""

# Test if migrations work with production settings
echo "Testing migrations with production settings..."
python manage.py makemigrations --settings=mysite.production_settings --check
if [ $? -eq 0 ]; then
    echo "✅ Migration check successful!"
else
    echo "⚠️  Warning: Issues detected with migrations. Please fix before deploying."
fi 
release: python fix_db_path.py && python manage.py migrate --settings=mysite.production_settings
web: gunicorn mysite.wsgi --env DJANGO_SETTINGS_MODULE=mysite.production_settings
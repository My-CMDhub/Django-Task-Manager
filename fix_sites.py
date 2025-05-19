import os
import django
import sqlite3
from datetime import datetime

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
django.setup()

# Database file path
db_path = 'db.sqlite3'

# Connect to the database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. First check if django_site table exists
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='django_site';")
if not cursor.fetchone():
    print("Creating django_site table...")
    # Create the django_site table based on Django's schema
    cursor.execute('''
    CREATE TABLE django_site (
        id INTEGER NOT NULL PRIMARY KEY,
        domain VARCHAR(100) NOT NULL,
        name VARCHAR(50) NOT NULL
    );
    ''')
    
    # Create unique index on domain field
    cursor.execute('''
    CREATE UNIQUE INDEX django_site_domain_a2e37b91_uniq
    ON django_site (domain);
    ''')
    
    # Insert default site
    cursor.execute('''
    INSERT INTO django_site (id, domain, name)
    VALUES (1, 'example.com', 'example.com');
    ''')
    
    print("Default site created")
else:
    print("django_site table already exists")

# 2. Check and update django_migrations table for sites app
cursor.execute("SELECT app, name FROM django_migrations WHERE app='sites';")
existing_migrations = cursor.fetchall()
existing_migrations = [m[1] for m in existing_migrations]

needed_migrations = ['0001_initial', '0002_alter_domain_unique']
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

for migration in needed_migrations:
    if migration not in existing_migrations:
        print(f"Adding migration record for sites.{migration}")
        cursor.execute('''
        INSERT INTO django_migrations (app, name, applied)
        VALUES (?, ?, ?);
        ''', ('sites', migration, now))

# Commit all changes
conn.commit()
conn.close()

print("Sites app migration fix completed.")
print("Now you can run 'python manage.py migrate' normally.") 
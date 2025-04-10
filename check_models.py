import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')
django.setup()

from auth_app.models import User
from tasks.models import Task, Category
from django.contrib.auth.models import Group, Permission

def check_models():
    print("\n=== User Model Check ===")
    users = User.objects.all()
    print(f"Total users: {users.count()}")
    
    for user in users:
        print(f"User ID: {user.id}")
        print(f"Username: {user.username}")
        print(f"Email: {user.email}")
        print(f"Is superuser: {user.is_superuser}")
        print(f"Is staff: {user.is_staff}")
        print("---")
    
    print("\n=== Admin Groups Check ===")
    groups = Group.objects.all()
    print(f"Total groups: {groups.count()}")
    
    print("\n=== Task Model Check ===")
    tasks = Task.objects.all()
    print(f"Total tasks: {tasks.count()}")
    
    print("\n=== Category Model Check ===")
    categories = Category.objects.all()
    print(f"Total categories: {categories.count()}")
    
    print("\n=== Creating Test Data ===")
    # Create a test category if none exists
    if Category.objects.count() == 0:
        test_category = Category.objects.create(
            name="Test Category",
            description="A test category for testing tasks"
        )
        print(f"Created test category: {test_category.name}")
    else:
        test_category = Category.objects.first()
        print(f"Using existing category: {test_category.name}")
    
    # Create a test task for the first user if any exists
    if User.objects.exists() and Task.objects.filter(user=User.objects.first()).count() == 0:
        user = User.objects.first()
        task = Task.objects.create(
            title="Test Task",
            description="A test task created for testing",
            user=user,
            category=test_category,
            priority="medium",
            status="pending"
        )
        print(f"Created test task '{task.title}' for user: {user.username}")
    elif User.objects.exists():
        user = User.objects.first()
        tasks = Task.objects.filter(user=user)
        print(f"User {user.username} already has {tasks.count()} tasks")
        for task in tasks:
            print(f"- Task: {task.title}, Status: {task.status}, Priority: {task.priority}")
    else:
        print("No users found to create tasks for")

if __name__ == "__main__":
    check_models() 
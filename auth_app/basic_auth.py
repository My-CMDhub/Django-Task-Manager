from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.http import HttpResponseRedirect
from django.urls import reverse

from .models import User

def basic_login(request):
    """Simple login view without Supabase integration"""
    context = {}
    
    # Check if we're coming from registration
    if 'new_user_username' in request.session:
        context['new_user_username'] = request.session['new_user_username']
        # Clear it after use
        del request.session['new_user_username']
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            
            # Redirect to dashboard or next parameter
            next_url = request.POST.get('next', 'dashboard')
            return redirect(next_url)
        else:
            messages.error(request, "Invalid username or password.")
    
    return render(request, 'auth/basic_login.html', context)

def basic_register(request):
    """Simple registration view without Supabase or email verification"""
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        
        # Basic validation
        if not all([username, email, password1, password2]):
            messages.error(request, "All fields are required.")
            return render(request, 'auth/basic_register.html')
            
        if password1 != password2:
            messages.error(request, "Passwords don't match.")
            return render(request, 'auth/basic_register.html')
            
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
            return render(request, 'auth/basic_register.html')
            
        if User.objects.filter(email=email).exists():
            messages.error(request, "Email already registered.")
            return render(request, 'auth/basic_register.html')
        
        # Create user
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password1
                )
                
                # Mark email as verified since we're bypassing verification
                user.email_verified = True
                user.save()
                
                messages.success(request, f"Account created successfully! Please log in with your credentials.")
                
                # Set username in session for login page
                request.session['new_user_username'] = username
                
                # Redirect to login page
                return redirect('basic_login')
        except Exception as e:
            messages.error(request, f"Error creating account: {str(e)}")
    
    return render(request, 'auth/basic_register.html')

def basic_logout(request):
    """Simple logout view"""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('basic_login')

@login_required
def basic_delete_account(request):
    """Simple account deletion"""
    if request.method == 'POST':
        password = request.POST.get('password')
        
        # Verify password
        if not request.user.check_password(password):
            messages.error(request, "Incorrect password. Account not deleted.")
            return render(request, 'auth/basic_delete_account.html')
        
        try:
            with transaction.atomic():
                user = request.user
                
                # Set deleted status
                user.is_active = False
                user.deleted_at = timezone.now()
                user.save()
                
                # Log the user out
                logout(request)
                
                messages.success(request, "Your account has been deleted successfully.")
                return redirect('basic_login')
        except Exception as e:
            messages.error(request, f"Error deleting account: {str(e)}")
    
    return render(request, 'auth/basic_delete_account.html') 
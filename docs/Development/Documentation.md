# Authentication System Documentation

## Overview

This document details the implementation of our authentication system that integrates Django with Supabase. The system is designed with Supabase as the source of truth, ensuring that user data remains synchronized between both platforms.

## Features Implemented

### User Registration
- **Implemented**: ✅ 
- **Flow**:
  1. User submits registration form with email, username, and password
  2. System validates the input (email format, password strength)
  3. System checks if user exists in Supabase first
  4. User is created in Supabase with `supabase.auth.sign_up()`
  5. User is then created in Django's database with the Supabase UID
  6. Verification email is sent to the user

### Email Verification
- **Implemented**: ✅
- **Flow**:
  1. User receives verification email with secure token link
  2. Clicking the link validates the token
  3. User's email is marked as verified in both Django and Supabase
  4. User can now log in with full access

### Login
- **Implemented**: ✅
- **Flow**:
  1. User submits email and password
  2. System checks if user exists and is not deleted
  3. Authentication occurs against Django's database
  4. Failed login attempts are tracked with account lockout after 5 attempts
  5. Device information is recorded for security tracking
  6. Session management with optional "remember me" functionality

### Logout
- **Implemented**: ✅
- **Flow**:
  1. User session is invalidated
  2. User is redirected to login page

### Password Reset
- **Implemented**: ✅
- **Flow**:
  1. User requests password reset by email
  2. Secure token is generated and sent via email
  3. User sets new password using the token
  4. Password is updated in both Django and Supabase

### Account Settings
- **Implemented**: ✅
- **Features**:
  1. Update profile information
  2. Change password with current password verification
  3. View active sessions with ability to revoke access
  4. Email preferences management

### Account Deletion
- **Implemented**: ✅
- **Flow**:
  1. User requests account deletion from settings
  2. Confirmation required with password
  3. Account is soft-deleted first (marked with `deleted_at` timestamp)
  4. Account is removed from Supabase

### Real-time Synchronization
- **Implemented**: ✅
- **Mechanism**:
  1. Supabase webhooks send events to Django (`user.created`, `user.updated`, `user.deleted`)
  2. Direct database operations for immediate synchronization
  3. Periodic background checking every 60 seconds
  4. Command-line utility for manual synchronization
  5. Supabase is treated as the source of truth

## Key Components

### Django Models
- **`User` Model**: Extended Django's AbstractUser with:
  - `supabase_id`: UUID linking to Supabase
  - `email_verified`: Boolean tracking verification status
  - `failed_login_attempts`: Counter for security lockouts
  - `account_locked_until`: Timestamp for temporary lockouts
  - `deleted_at`: Timestamp for soft deletion

- **`UserProfile` Model**: Extended profile information:
  - One-to-one relationship with User
  - `supabase_uid`: Redundant link to Supabase for data integrity
  - `verified`: Boolean for email verification status

### Synchronization Tools

#### 1. Management Command
```python
python manage.py sync_users [--direction=to-django|to-supabase|both] [--force] [--email=user@example.com]
```
- `--direction`: Specifies sync direction (default: both)
- `--force`: Forces synchronization even for existing users
- `--email`: Targets a specific user by email

#### 2. Real-time Monitoring (`monitor_users.py`)
- Continuously monitors user counts in both systems
- Displays detailed discrepancy information
- Performs automatic synchronization when inconsistencies are detected
- Processes webhook events for immediate updates

#### 3. Development Environment (`run-dev.sh`)
- Sets up ngrok for webhook testing
- Configures environment variables
- Starts Django server and monitoring tools
- Provides detailed real-time feedback

### Security Measures

1. **Password Management**:
   - Secure hashing with Django's PBKDF2 algorithm
   - Password strength validation
   - Automatic lockouts after failed attempts

2. **Session Security**:
   - Device tracking
   - IP logging
   - Session expiration controls
   - Ability to terminate sessions remotely

3. **Email Security**:
   - Secure tokens for verification
   - Custom SMTP configuration
   - HTML/text email templates
   - Enhanced email headers for deliverability

4. **Data Protection**:
   - Soft deletion to prevent data loss
   - Database transaction management
   - Comprehensive error handling and logging

## Common Issues and Solutions

### 1. User Exists in Supabase But Not in Django
**Solution**: The synchronization system will automatically create the user in Django. For manual resolution:
```
python manage.py sync_users --direction=to-django --force --email=user@example.com
```

### 2. User Exists in Django But Not in Supabase
**Solution**: Since Supabase is the source of truth, these users will be soft-deleted from Django.

### 3. Mismatched User IDs
**Solution**: The system will automatically update the Django `supabase_id` field to match Supabase.

### 4. Account Lockouts
**Solution**: 
- Automatic reset after 30 minutes
- Administrative unlock: `User.objects.filter(email="user@example.com").update(account_locked_until=None, failed_login_attempts=0)`

### 5. Email Verification Issues
**Solution**:
- Users can request a new verification email from the login page
- Administrative verification: `User.objects.filter(email="user@example.com").update(email_verified=True)`

## Backend API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/login/` | POST | Authenticate user |
| `/auth/logout/` | GET | End user session |
| `/auth/register/` | POST | Create new account |
| `/auth/verify-email/<token>/` | GET | Verify email address |
| `/auth/password-reset/` | POST | Request password reset |
| `/auth/password-reset-confirm/<token>/` | POST | Confirm password reset |
| `/auth/account-settings/` | GET/POST | Manage account settings |
| `/auth/delete-account/` | POST | Delete user account |
| `/auth/resend-verification/` | POST | Resend verification email |
| `/auth/webhooks/supabase/` | POST | Receive Supabase webhooks |
| `/auth/sync-status/` | GET | Check synchronization status |
| `/auth/test-webhook/` | GET/POST | Test webhook functionality |

## Future Enhancements

1. **OAuth Integration**:
   - Social login (Google, Facebook, GitHub)
   - Single sign-on capabilities

2. **Two-Factor Authentication**:
   - App-based 2FA
   - SMS verification

3. **Enhanced Session Management**:
   - Geolocation tracking
   - Suspicious activity detection
   - Concurrent session limits

4. **Role-Based Access Control**:
   - Fine-grained permission system
   - Role inheritance
   - Dynamic permission assignment

## Troubleshooting

### Webhook Issues
1. Check ngrok URL is correctly set in Supabase dashboard
2. Verify webhook URL is accessible
3. Examine webhook logs: `logs/webhook.log`
4. Test with manual endpoint: `/auth/test-webhook/`

### Synchronization Problems
1. Check connection to Supabase in settings
2. Verify service role key has proper permissions
3. Examine synchronization logs: `logs/sync.log`
4. Run manual sync with verbose logging:
   ```
   python manage.py sync_users --direction=both --force -v 2
   ```

### Authentication Failures
1. Check for account lockouts or soft deletion
2. Verify email address is verified
3. Examine authentication logs
4. Reset password if necessary

## Maintenance Tasks

### Regular Audits
- Review soft-deleted accounts monthly
- Check for orphaned sessions
- Verify Supabase/Django synchronization state
- Review failed login attempts for potential threats

### Database Indexing
The following fields should have indexes for performance:
- `User.email`
- `User.supabase_id`
- `User.deleted_at`
- `UserProfile.supabase_uid`

### Monitoring
Monitor the following metrics:
- Daily active users
- Registration conversion rates
- Password reset frequency
- Verification email delivery rates
- Failed login patterns

## Development Guidelines

1. **Testing Authentication Changes**:
   - Use the test environment with `./run-dev.sh`
   - Verify both Django and Supabase impacts
   - Test all email flows with a test email service

2. **Making Schema Changes**:
   - Update both Django models and Supabase metadata
   - Adjust synchronization logic in `sync_users.py`
   - Update direct DB operations in `monitor_users.py`

3. **Email Template Updates**:
   - Modify templates in `templates/emails/`
   - Test with multiple email clients
   - Check both HTML and plain text versions 
## mysite:

.
├── __init__.py
├── __pycache__
│   ├── __init__.cpython-311.pyc
│   ├── __init__.cpython-313.pyc
│   ├── models.cpython-311.pyc
│   ├── models.cpython-313.pyc
│   ├── production_settings.cpython-311.pyc
│   ├── settings.cpython-311.pyc
│   ├── settings.cpython-313.pyc
│   ├── urls.cpython-311.pyc
│   ├── urls.cpython-313.pyc
│   ├── wsgi.cpython-311.pyc
│   └── wsgi.cpython-313.pyc
├── asgi.py
├── models.py
├── production_settings.py
├── pythonanywhere_wsgi.py
├── settings.py
├── templates
│   ├── dashboard.html
│   ├── home.html
│   └── includes
├── urls.py
└── wsgi.py


## chatbot_integration

.
├── INTEGRATION_GUIDE.md
├── README.md
├── __init__.py
├── __pycache__
│   ├── __init__.cpython-311.pyc
│   ├── apps.cpython-311.pyc
│   └── urls.cpython-311.pyc
├── apps.py
├── chatbot_app
│   ├── __init__.py
│   ├── __pycache__
│   │   ├── __init__.cpython-311.pyc
│   │   ├── apps.cpython-311.pyc
│   │   ├── models.cpython-311.pyc
│   │   ├── signals.cpython-311.pyc
│   │   ├── task_automation.cpython-311.pyc
│   │   ├── urls.cpython-311.pyc
│   │   ├── utils.cpython-311.pyc
│   │   └── views.cpython-311.pyc
│   ├── apps.py
│   ├── initialize.py
│   ├── management
│   │   ├── __init__.py
│   │   ├── __pycache__
│   │   │   └── __init__.cpython-311.pyc
│   │   └── commands
│   │       ├── __init__.py
│   │       └── init_chatbot.py
│   ├── migrations
│   │   ├── 0001_initial.py
│   │   ├── 0002_conversation_taskcreationrequest_created_at_and_more.py
│   │   ├── 0003_message_role.py
│   │   ├── 0004_conversation_title.py
│   │   ├── 0005_conversation_metadata.py
│   │   ├── 0006_remove_conversation_metadata_and_more.py
│   │   ├── 0007_alter_taskcreationrequest_created_task_id.py
│   │   ├── 0008_alter_taskcreationrequest_unique_together_and_more.py
│   │   ├── 0009_remove_taskcreationrequest_unique_active_task_request.py
│   │   ├── __init__.py
│   │   └── __pycache__
│   │       ├── 0001_initial.cpython-311.pyc
│   │       ├── 0002_conversation_taskcreationrequest_created_at_and_more.cpython-311.pyc
│   │       ├── 0003_message_role.cpython-311.pyc
│   │       ├── 0004_conversation_title.cpython-311.pyc
│   │       ├── 0005_conversation_metadata.cpython-311.pyc
│   │       ├── 0006_remove_conversation_metadata_and_more.cpython-311.pyc
│   │       ├── 0007_alter_taskcreationrequest_created_task_id.cpython-311.pyc
│   │       ├── 0008_alter_taskcreationrequest_unique_together_and_more.cpython-311.pyc
│   │       ├── 0009_remove_taskcreationrequest_unique_active_task_request.cpython-311.pyc
│   │       └── __init__.cpython-311.pyc
│   ├── models.py
│   ├── process_message
│   ├── signals.py
│   ├── task_automation.py
│   ├── templates
│   │   └── chatbot_app
│   │       ├── chatbot.html
│   │       └── chatbot_test.html
│   ├── tests
│   │   ├── __init__.py
│   │   ├── __pycache__
│   │   │   ├── __init__.cpython-311.pyc
│   │   │   └── test_context_awareness.cpython-311.pyc
│   │   └── test_context_awareness.py
│   ├── urls.py
│   ├── utils.py
│   └── views.py
├── check_integration.py
├── django_integration.py
├── docs
│   ├── context_awareness.md
│   └── response_patterns.md
├── requirements.txt
├── setup.sh
└── urls.py

## auth_app

.
├── __init__.py
├── admin.py
├── admin_backend.py
├── apps.py
├── backends.py
├── basic_auth.py
├── management
│   ├── __init__.py
│   └── commands
│       ├── __init__.py
│       ├── cleanup_supabase_users.py
│       ├── cleanup_users.py
│       ├── process_delayed_registrations.py
│       ├── run_scheduled_syncs.py
│       ├── runserver_with_ngrok.py
│       ├── sync_users.py
│       └── verify_clean.py
├── migrations
│   ├── 0001_initial.py
│   ├── 0002_user_account_locked_until_user_failed_login_attempts_and_more.py
│   ├── 0003_user__verification_tokens.py
│   ├── 0004_remove_user__verification_tokens_and_more.py
│   ├── 0005_usersyncschedule_alter_user_options_and_more.py
│   ├── 0006_userprofile.py
│   └── __init__.py
├── models.py
├── supabase_utils.py
├── templates
│   ├── auth
│   │   ├── account_settings.html
│   │   ├── account_sync_status.html
│   │   ├── auth_choice.html
│   │   ├── basic_delete_account.html
│   │   ├── basic_login.html
│   │   ├── basic_register.html
│   │   ├── delete_account.html
│   │   ├── email
│   │   ├── login.html
│   │   ├── password_reset.html
│   │   ├── password_reset_confirm.html
│   │   ├── register.html
│   │   ├── resend_verification.html
│   │   ├── smtp_setup.html
│   │   ├── test_domain.html
│   │   ├── test_webhook.html
│   │   └── unsubscribe.html
│   ├── base.html
│   └── emails
│       ├── verification_email.html
│       └── verification_email_text.html
├── urls.py
├── views.py
└── webhooks.py

## tasks

.
├── __init__.py
├── admin.py
├── apps.py
├── forms.py
├── management
│   ├── __init__.py
│   └── commands
│       ├── __init__.py
│       └── sync_supabase_users.py
├── migrations
│   ├── 0001_initial.py
│   ├── 0002_task_actual_hours_task_archived_at_task_dependencies_and_more.py
│   └── __init__.py
├── models.py
├── serializers.py
├── signals.py
├── templates
│   └── tasks
│       ├── project_confirm_archive.html
│       ├── project_confirm_delete.html
│       ├── project_detail.html
│       ├── project_form.html
│       ├── project_list.html
│       ├── projects
│       ├── task_confirm_delete.html
│       ├── task_detail.html
│       ├── task_form.html
│       ├── task_list.html
│       └── user_list.html
├── tests.py
├── urls.py
└── views.py

## templates:

.
├── auth
│   └── force_reset.html
├── chatbot_app
│   └── chatbot_interface.html
└── includes
    ├── chatbot_fix.js
    ├── chatbot_scripts.html
    └── sidebar.html
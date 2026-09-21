# Nexus

A web app for keeping track of tasks and projects, with a chat assistant in the corner of every page that answers questions about your own records.

![Python](https://img.shields.io/badge/Python-3.11-3776AB)
![Django](https://img.shields.io/badge/Django-4.2-092E20)
![License](https://img.shields.io/badge/License-MIT-blue)
[![Live](https://img.shields.io/badge/live-taskmanager--mztm.onrender.com-success)](https://taskmanager-mztm.onrender.com)

## What it is

A Django task manager built around a custom user model that is kept in step with Supabase Auth, so sign-up, email verification and password reset happen in Supabase while the app's own data stays in Django. On top of the usual task and project CRUD there is a chat assistant that answers questions about your own tasks by querying the database directly.

The repository is called `Django-Task-Manager`, but the code, templates and logo assets all say **Nexus**, so this README uses Nexus.

## What it does

- Tasks with status, priority, due date, tags, subtasks, dependencies, estimated vs actual hours, comments, attachments and a per-task version history.
- Projects that group tasks, with members, colour, icon, dates and an archive state instead of deletion.
- A dashboard that counts todo / in progress / completed, works out a completion rate, and lists what is due today, due this week and overdue.
- Share links: generate a token URL for one task or project, view-only or edit, revocable and optionally expiring.
- A chat widget on every page that answers "what's overdue", finds a task by name and summarises a project — read-only by design: asked to create or change something, it declines and points you at the UI.
- Sign-up, email verification, password reset and account deletion through Supabase, kept in sync with Django users by a webhook.

## How it works

Four Django apps under the `mysite` project:

- `tasks/` — the domain. `models.py` holds `Task`, `Project`, `TaskVersion`, `TimeEntry`, `ShareLink` and friends, all UUID-keyed; `views.py` holds the CRUD and bulk-action views.
- `auth_app/` — a custom `User` (`AUTH_USER_MODEL = 'auth_app.User'`) carrying `supabase_id`, `email_verified` and lockout counters, plus `backends.py` for email login and `webhooks.py`, which verifies an HMAC signature on Supabase user events and applies them locally.
- `chatbot_integration/chatbot_app/` — the assistant. `views.generate_bot_response` matches the message against intent regexes and answers from the ORM.
- `mysite/` — settings, `production_settings.py` for the Render deploy, and the dashboard view (it lives in `mysite/urls.py`).

The non-obvious part is keeping two user stores honest. A user can be created in Supabase, in Django, or in both, and the two can drift. `auth_app/webhooks.py` handles the created/updated/deleted events with retries, and `tasks/management/commands/sync_supabase_users.py` plus `mysite/supabase_utils.py` exist to reconcile whatever the webhook missed.

## Run it locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt      # requirement.txt is a pip freeze of a whole dev machine; ignore it
```

Create a `.env` in the repo root. `settings.py` loads it with `python-dotenv`. The variables the code actually reads:

```
SECRET_KEY=
SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_SERVICE_KEY=
SUPABASE_SITE_URL=http://127.0.0.1:8000
SUPABASE_WEBHOOK_SECRET=
SUPABASE_SYNC_ENABLED=true
SITE_DOMAIN=127.0.0.1:8000
SITE_PROTOCOL=http
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
OPENAI_API_KEY=
BYPASS_SUPABASE=False
```

Do not copy `.env.example` — it still contains live-looking keys rather than placeholders.

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

`manage.py` picks `mysite.settings` unless `DJANGO_ENV=production`, which switches it to `mysite.production_settings`. Docker is also wired up: `docker compose up --build` starts Postgres and gunicorn, reading the same `.env`.

Supabase email links have to reach your machine, so verification and password-reset flows need a public URL. `run-dev.sh` starts ngrok, rewrites the URL into `.env` and launches the server.

## What it doesn't do yet

- **There are no automated tests.** `tasks/tests.py` is the empty Django stub. The `test_*.py` files under `chatbot_integration/` are manual scripts that need a running server and real credentials.
- **The assistant is read-only.** `generate_bot_response` matches "create a task" / "update a task" and answers with a fixed refusal pointing you back at the UI.
- **The LLM fallback is unreachable on the pinned versions.** The final branch of `generate_bot_response` calls `openai.ChatCompletion.create`, which was removed in the `openai==1.3.0` that `requirements.txt` pins, so it throws and returns a canned reply. Everything the assistant does well, it does with regexes.
- **Production defaults to SQLite.** `production_settings.py` only switches to Postgres when `DATABASE_URL` is present, and on Render's ephemeral disk a redeploy takes the database with it.
- **Nothing runs without a `.env`.** Every credential now reads from the environment with no fallback, by design — an earlier version of this repo shipped real keys as defaults. Copy `.env.example` and fill it in.

# Cursuri Python

This is the Django foundation for a SaaS product: a Python tutor with a personal AI tutor. Phase 0 set up the project structure, configuration, a custom user model, admin and a health check. Phase 1 adds the product shell, a static demo of the learning interface on the homepage. It is presentation only: the progress, skill map, lesson, editor and tutor content on the page are placeholder data.

Phase 2 adds the curriculum engine:

- a curriculum database structure: World → Skill → Concept → Lesson
- explicit Skill and Concept prerequisites, validated to stay within one World and free of cycles
- the Python Foundations seed (11 skills, 53 concepts with learning objectives, lessons and prerequisite graphs)
- Django admin for all curriculum models and a `published_curriculum()` query helper

Phase 2B adds learner accounts:

- signup, login with username or email (case-insensitive), POST-only logout and password reset
- a learner profile (preferred name, time zone) separate from the user account
- onboarding: choose a preferred name and enroll in a published learning path (World)
- enrollments: a learner can be enrolled in any number of Worlds
- an account menu on the homepage and admin for profiles and enrollments

Phase 3 adds a domain-neutral Exercise Engine. An `Exercise` belongs to a Lesson and works the same way for any subject (Python now; languages or maths later). Two separate fields describe it:

- `response_type`: how the learner answers (`code`, `multiple_choice`, `fill_gap`, `text`, `translation`, `numeric`, `math_expression`, `speaking`, `listening`)
- `learning_mode`: which cognitive level it trains (`recognise`, `complete`, `fix`, `create`)

For example: `code` + `fix` (debug a program), `translation` + `create` (translate a sentence), `multiple_choice` + `recognise` (pick the right keyword).

`content` holds what the learner sees and is validated so it never contains answers. `evaluation_spec` holds the private answer configuration for the future evaluation engine; it is never included in `exercise_presentation()` or any template. Learners only reach exercises whose whole curriculum chain is published, in Worlds where their enrollment is active or completed (`apps/exercises/access.py`).

Phase 3P adds the first real content pack: 147 Python Foundations exercises covering all 11 skills and 53 concepts. Each skill uses all four learning modes (recognise → complete → fix → create), mostly as multiple-choice, fill-the-gap and code exercises. Every exercise has a private evaluation spec: the correct option, accepted gap answers, or code tests (`stdout` or `function` strategy) with a reference solution. The definitions live in `apps/exercises/data/python_foundations/`.

Phase 4 adds a generic, deterministic Evaluation Engine (`apps/evaluation/`). `evaluate_exercise(exercise, answer)` picks an evaluator from the exercise's `response_type` and returns an in-memory `EvaluationResult` (status, score 0.0–1.0, is_correct, a safe message and internal reason codes). Nothing is stored yet.

- Evaluated automatically now: multiple choice, fill the gap and numeric (with an optional tolerance).
- Deferred: code (the Python runner comes in Phase 4P), text rubrics, translations and maths expressions (returned as `review_required`), speaking and listening (`unsupported`).
- Learner-facing output (`evaluation_result_presentation`) never includes correct options, accepted answers, expected values or tests. A misconfigured exercise raises `EvaluationConfigurationError` instead of marking the learner wrong.
- `evaluation_spec` contracts are now validated; a published exercise needs a complete one.

**Available:** curriculum data, learner accounts, profiles, World enrollment, the Python Foundations exercises (editable in the admin) and in-memory answer evaluation.
**Not yet implemented:** saving attempts, running Python code, AI evaluation, learner progress, mastery and the AI tutor. The homepage is still the Phase 1 demo; its Run Code button is not connected.

## Stack

- Python 3.11+
- Django 5.2 (LTS)
- PostgreSQL in production, with SQLite as the zero-setup local default
- Django templates with HTMX 2.0.10, stored locally in `static/vendor/`
- Configuration through environment variables (`.env` is loaded with `python-dotenv`)
- ruff for linting and formatting

## Project layout

```
config/          Django project: settings, URLs, WSGI/ASGI, env helpers, root views
apps/accounts/   Custom user model (AUTH_USER_MODEL = "accounts.User"), signup/login/password reset
apps/curriculum/ Curriculum models, admin, selectors, seed data and seed_curriculum command
apps/learners/   Learner profiles, World enrollment, onboarding and the profile page
apps/exercises/  Exercise model, validation, safe presentation, selectors, access rules and the
                 Python Foundations exercise pack (data/ + seed_python_exercises command)
apps/evaluation/ Evaluation engine: result type, evaluator registry and evaluators
templates/       Project-level templates
static/          Project-level static files (css/, vendor/htmx.min.js)
```

## Local setup

### Windows (PowerShell)

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### macOS / Linux

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

### Curriculum and exercise data

Load or refresh the Python Foundations curriculum and its exercises after migrating (in this order):

```bash
python manage.py migrate
python manage.py seed_curriculum
python manage.py seed_python_exercises
```

Both seeds are idempotent. Records are matched by slug within their parent, so running them again updates the seeded records (repairing manual edits) without duplicating them, and they never delete records they don't define. `seed_python_exercises` stops with an error if the curriculum hasn't been seeded yet.

Once the server is running, these URLs are available:

- http://127.0.0.1:8000/: homepage, the static learning-interface demo (product shell)
- http://127.0.0.1:8000/health/: returns `{"status": "ok"}`
- http://127.0.0.1:8000/admin/: Django admin
- http://127.0.0.1:8000/accounts/signup/: create an account
- http://127.0.0.1:8000/accounts/login/: sign in with email or username
- http://127.0.0.1:8000/accounts/password-reset/: request a password reset link
- http://127.0.0.1:8000/onboarding/: choose a name and a learning path (signed-in users)
- http://127.0.0.1:8000/profile/: your profile and enrollments (signed-in users)

Logging out is a POST to `/accounts/logout/` (the account menu and profile page provide the button).

In development, password reset emails are printed to the console where `runserver` is running.

## Configuration

Every setting is read from environment variables. See [.env.example](.env.example) for the full list. Real environment variables take precedence over `.env`. Never commit `.env`.

| Variable | Default | Notes |
|---|---|---|
| `DJANGO_SECRET_KEY` | (none) | Required when `DJANGO_DEBUG=false`. When DEBUG is on and this is empty, an insecure development-only key is used. |
| `DJANGO_DEBUG` | `false` | Boolean. |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated. |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | empty | Comma-separated. Each entry **must include the scheme**, e.g. `https://example.com`. |
| `DJANGO_TIME_ZONE` | `UTC` | |
| `DJANGO_LOG_LEVEL` | `INFO` | |
| `DATABASE_URL` | SQLite `db.sqlite3` | For example `postgres://user:pass@host:5432/dbname`. |
| `DATABASE_CONN_MAX_AGE` | `60` | Seconds. `0` closes the connection after each request. |
| `DJANGO_SECURE_SSL_REDIRECT` | `true` | Only applies when DEBUG is off. |
| `DJANGO_SECURE_HSTS_SECONDS` | `0` | Only applies when DEBUG is off. Increase it gradually once HTTPS is confirmed. |
| `DJANGO_SECURE_PROXY_SSL_HEADER` | `false` | See the warning below. |
| `DJANGO_EMAIL_BACKEND` | console backend | Where password reset emails go. Use `django.core.mail.backends.smtp.EmailBackend` (plus Django's `EMAIL_*` settings) for real delivery. |
| `DJANGO_DEFAULT_FROM_EMAIL` | `Python AI Tutor <no-reply@localhost>` | Sender address for account emails. |

Booleans accept `true/false`, `1/0`, `yes/no` and `on/off`, in any case. Any other value stops startup with an error. In list values, surrounding whitespace and empty entries are ignored.

> **`DJANGO_SECURE_PROXY_SSL_HEADER`**: enable this **only** when Django runs behind a trusted reverse proxy that always sets `X-Forwarded-Proto` and removes any value sent by the client. If you enable it anywhere else, clients can make plain HTTP requests look like HTTPS.

To generate a secret key:

```bash
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

### Using PostgreSQL locally

1. Create a database and a user in PostgreSQL.
2. Set the connection URL in `.env`:
   ```
   DATABASE_URL=postgres://app_user:app_password@localhost:5432/app_db
   ```
3. Run `python manage.py migrate`.

The `psycopg[binary]` driver is already listed in `requirements.txt`.

## Development commands

```bash
python manage.py check                  # Django system checks
python manage.py makemigrations --check --dry-run   # fails if model changes lack migrations
python manage.py test                   # run the test suite
ruff check .                            # lint
ruff format .                           # format (use --check in CI)
```

## Dependencies

- `requirements.txt` lists the direct runtime dependencies with compatible version ranges.
- `requirements-dev.txt` adds the development tools.
- Neither file is a frozen lock file.

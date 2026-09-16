# Cursuri Python

This is the Django foundation for a SaaS product. Phase 1 adds learner account creation,
login, logout, and password reset on top of the Phase 0 project foundation. Course and tutor
features belong to later phases and are not included yet.

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
apps/accounts/   Custom user model (AUTH_USER_MODEL = "accounts.User")
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

Once the server is running, these URLs are available:

- http://127.0.0.1:8000/: homepage ("The application is running.")
- http://127.0.0.1:8000/health/: returns `{"status": "ok"}`
- http://127.0.0.1:8000/admin/: Django admin
- http://127.0.0.1:8000/accounts/signup/: learner registration
- http://127.0.0.1:8000/accounts/login/: login and password reset

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

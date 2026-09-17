"""Django settings, configured entirely through environment variables.

See `.env.example` for the available variables.
"""

import sys
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

from config.env import env_bool, env_int, env_list, env_str

BASE_DIR = Path(__file__).resolve().parent.parent

# Real environment variables take precedence over values in `.env`.
load_dotenv(BASE_DIR / ".env")

# --- Core ---------------------------------------------------------------------

DEBUG = env_bool("DJANGO_DEBUG", default=False)

SECRET_KEY = env_str("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG is false.")
    SECRET_KEY = "django-insecure-development-only-key-do-not-use-in-production"

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# Each entry must include the scheme, e.g. "https://example.com".
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# --- Applications -------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.accounts",
    "apps.curriculum",
    "apps.learners",
    "apps.exercises",
    "apps.evaluation",
    "apps.python_runner",
    "apps.attempts",
    "apps.learner_intelligence",
    "apps.misconceptions",
    "apps.next_action",
    "apps.ai_tutor",
    "apps.course_player",
    "apps.gamification",
    "apps.projects",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context_processors.product",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --- Database -----------------------------------------------------------------

# DATABASE_URL selects the database (e.g. postgres://...); SQLite is the local fallback.
DATABASES = {
    "default": dj_database_url.config(
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=env_int("DATABASE_CONN_MAX_AGE", default=60),
        conn_health_checks=True,
    ),
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Authentication -----------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# The test suite creates many users; a fast hasher keeps it quick. Only applies to
# `manage.py test` — every other command uses Django's default (PBKDF2) hashers.
if sys.argv[1:2] == ["test"]:
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# --- Product -------------------------------------------------------------------

# The platform brand. Courses (Worlds) carry their own titles; "AI Tutor" is a feature name.
PRODUCT_NAME = "cursuri.net"

# --- Email ---------------------------------------------------------------------

# Password reset emails print to the console unless a real backend is configured.
EMAIL_BACKEND = env_str("DJANGO_EMAIL_BACKEND") or "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = env_str("DJANGO_DEFAULT_FROM_EMAIL") or f"{PRODUCT_NAME} <no-reply@localhost>"

# --- Python code runner -------------------------------------------------------

# Learner code only ever runs inside an isolated Docker container. With the backend left
# "disabled" (the default) code exercises simply can't be checked; there is no local fallback.
# Values are validated by apps.python_runner.config when the app starts.
PYTHON_RUNNER = {
    "BACKEND": env_str("PYTHON_RUNNER_BACKEND") or "disabled",
    "IMAGE": env_str("PYTHON_RUNNER_IMAGE") or "python:3.11-slim",
    "TIMEOUT_SECONDS": env_str("PYTHON_RUNNER_TIMEOUT_SECONDS") or "3",
    "MEMORY_MB": env_str("PYTHON_RUNNER_MEMORY_MB") or "128",
    "CPUS": env_str("PYTHON_RUNNER_CPUS") or "0.5",
    "PIDS_LIMIT": env_str("PYTHON_RUNNER_PIDS_LIMIT") or "64",
    "MAX_OUTPUT_BYTES": env_str("PYTHON_RUNNER_MAX_OUTPUT_BYTES") or "65536",
    "MAX_SOURCE_BYTES": env_str("PYTHON_RUNNER_MAX_SOURCE_BYTES") or "65536",
    "DOCKER_BINARY": env_str("PYTHON_RUNNER_DOCKER_BINARY") or "docker",
}
if sys.argv[1:2] == ["test"]:
    # The normal test suite never starts containers; the opt-in Docker integration tests
    # build their own configuration.
    PYTHON_RUNNER["BACKEND"] = "disabled"

# AI tutor. Off by default; the rest of the site works without it. Values are validated by
# apps.ai_tutor.config when the app starts. Never commit a real API key.
AI_TUTOR = {
    "ENABLED": env_bool("AI_TUTOR_ENABLED", default=False),
    "OPENAI_API_KEY": env_str("OPENAI_API_KEY"),
    "OPENAI_MODEL": env_str("OPENAI_MODEL") or "gpt-5.6-luna",
    "OPENAI_TIMEOUT_SECONDS": env_str("OPENAI_TIMEOUT_SECONDS") or "20",
    "HISTORY_TURNS": env_str("AI_TUTOR_HISTORY_TURNS") or "8",
    "MAX_USER_CHARS": env_str("AI_TUTOR_MAX_USER_CHARS") or "4000",
    "MAX_OUTPUT_TOKENS": env_str("AI_TUTOR_MAX_OUTPUT_TOKENS") or "800",
    "RATE_LIMIT_PER_MINUTE": env_str("AI_TUTOR_RATE_LIMIT_PER_MINUTE") or "20",
}
if sys.argv[1:2] == ["test"]:
    # The normal test suite never calls a real provider.
    AI_TUTOR["ENABLED"] = False
    AI_TUTOR["OPENAI_API_KEY"] = ""

# --- Internationalization -----------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = env_str("DJANGO_TIME_ZONE", default="UTC")
USE_I18N = True
USE_TZ = True

# --- Static files -------------------------------------------------------------

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# --- Security -----------------------------------------------------------------

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
    SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", default=0)

# Only enable behind a trusted reverse proxy that sets X-Forwarded-Proto itself.
if env_bool("DJANGO_SECURE_PROXY_SSL_HEADER", default=False):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# --- Logging ------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "{asctime} {levelname} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": env_str("DJANGO_LOG_LEVEL", default="INFO")},
}

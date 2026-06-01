import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get('DJANGO_DEBUG') == '1'

# Secret key must come from the environment in production.
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'dev-only-insecure-key'
    else:
        raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set when DEBUG is off.")

# Render sets RENDER_EXTERNAL_HOSTNAME automatically
RENDER_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
ALLOWED_HOSTS = []
CSRF_TRUSTED_ORIGINS = []
if RENDER_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f'https://{RENDER_HOSTNAME}')
if DEBUG:
    ALLOWED_HOSTS += ['localhost', '127.0.0.1']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# One database everywhere — DATABASE_URL points at Postgres, locally and on Render.
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    raise ImproperlyConfigured("DATABASE_URL must be set.")
DATABASES = {'default': dj_database_url.parse(DATABASE_URL)}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Render terminates TLS and forwards X-Forwarded-Proto. Without this, Django sees
# every request as HTTP — which breaks CSRF origin checks (forms 403) and secure cookies.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# ── Reddit (public JSON — no credentials needed) ──────────────────────────────
# Reddit fetching uses the public /search.json endpoint with a User-Agent header.

# ── X / Twitter (optional) ────────────────────────────────────────────────────
X_BEARER_TOKEN = os.environ.get('X_BEARER_TOKEN', '')

# ── Claude / Anthropic ────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

# ── Serper ────────────────────────────────────────────────────────
SERPER_API_KEY = os.environ.get('SERPER_API_KEY', '')

# ── Digest: email (Resend HTTP API) ───────────────────────────────────────────
RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
FROM_EMAIL = os.environ.get('FROM_EMAIL', '')        # must be on a Resend-verified domain
DIGEST_TO_EMAIL = os.environ.get('DIGEST_TO_EMAIL', '')

# ── Digest: Slack ─────────────────────────────────────────────────────────────
SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL', '')

# ── Scoring ───────────────────────────────────────────────────────────────────
DEFAULT_SCORE_THRESHOLD = int(os.environ.get('SCORE_THRESHOLD', '60'))
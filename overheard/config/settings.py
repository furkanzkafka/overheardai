import os
import dj_database_url
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = (
    os.environ.get('DJANGO_SECRET_KEY')
    or os.environ.get('SESSION_SECRET')
    or 'dev-only-secret-please-set-DJANGO_SECRET_KEY'
)

DEBUG = os.environ.get('DEBUG', 'true').lower() != 'false'

ALLOWED_HOSTS = ['*']
CSRF_TRUSTED_ORIGINS = [
    f"https://{h}" for h in os.environ.get('REPLIT_DOMAINS', '').split(',') if h
]

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

_database_url = os.environ.get('DATABASE_URL', '')
DATABASES = {
    'default': dj_database_url.parse(_database_url) if _database_url else {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Reddit (public JSON — no credentials needed) ──────────────────────────────
# Reddit fetching uses the public /search.json endpoint with a User-Agent header.
# No API key or OAuth credentials are required.

# ── X / Twitter (optional) ────────────────────────────────────────────────────
X_BEARER_TOKEN = os.environ.get('X_BEARER_TOKEN', '')

# ── Claude / Anthropic ────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

# ── Digest: email ─────────────────────────────────────────────────────────────
SMTP_HOST = os.environ.get('SMTP_HOST', '')
SMTP_PORT = int(os.environ.get('SMTP_PORT', '587'))
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASS = os.environ.get('SMTP_PASS', '')
FROM_EMAIL = os.environ.get('FROM_EMAIL', '')
DIGEST_TO_EMAIL = os.environ.get('DIGEST_TO_EMAIL', '')

# ── Digest: Slack ─────────────────────────────────────────────────────────────
SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL', '')

# ── Scoring ───────────────────────────────────────────────────────────────────
DEFAULT_SCORE_THRESHOLD = int(os.environ.get('SCORE_THRESHOLD', '60'))

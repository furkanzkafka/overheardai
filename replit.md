# Overheard

A quiet AI-filtered digest of people online describing the exact problem your team solves — so you can reach out genuinely, not at scale.

## Run & Operate

- `Start application` workflow runs Django on port 8000 (the main app)
- `cd overheard && python manage.py poll` — fetch + filter + store new items (run on a schedule)
- `cd overheard && python manage.py send_digest` — email + Slack digest of new items
- `cd overheard && python manage.py migrate` — apply DB migrations after schema changes
- `cd overheard && python manage.py makemigrations core` — create new migration after model changes

## Stack

- Backend: Django 5 + PostgreSQL (dj-database-url)
- Frontend: plain HTML, CSS (no framework), vanilla JS
- AI: Anthropic Claude (claude-opus-4-5 for rubric gen, claude-haiku-4-5 for scoring)
- Reddit: PRAW (official Python wrapper)
- X (Twitter): requests against v2 API — optional, app works fully without it
- Email: SMTP via smtplib
- Slack: incoming webhook via requests

## Where things live

- `overheard/` — Django project root
  - `config/` — settings, URLs, WSGI
  - `core/` — models, views, forms, templates, fetchers, AI filter, digest, management commands
  - `static/css/style.css` — all styles (plain CSS, no framework)
  - `core/templates/` — base.html, index.html, setup.html, dashboard.html

## Architecture decisions

- Two-stage funnel: cheap keyword search (Reddit/X) → expensive AI scoring (Claude Haiku). Only scored candidates above `score_threshold` are stored.
- X module is structurally optional: missing credentials or 403 response → logs a clear message, keeps running on Reddit alone.
- `dedup_key = platform:post_id` prevents duplicates across poll runs.
- Management commands (`poll`, `send_digest`) are designed for Render cron jobs.
- Static files served by whitenoise in production; Django runserver in development.

## Product

Users paste their website URL → Claude generates a relevance rubric + keyword list → scheduled `poll` command searches Reddit/X, scores each candidate with Claude, stores matches above threshold → `send_digest` sends a clean email + Slack digest → team reviews on the Dashboard and marks items replied or ignored.

## Environment variables needed

Required:
- `DATABASE_URL` — Postgres connection string (already set by Replit)
- `ANTHROPIC_API_KEY` — for rubric generation and item scoring

Optional (app works without them):
- `X_BEARER_TOKEN` — X/Twitter API v2 bearer token
- `SLACK_WEBHOOK_URL` — incoming webhook URL
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `FROM_EMAIL`, `DIGEST_TO_EMAIL` — for email digest

## Gotchas

- Always `makemigrations core` then `migrate` after changing models.
- `python manage.py poll --dry-run` to test fetch+score without saving anything.
- Reddit "script" app credentials work without a user login (read-only search).
- X free tier may not include recent-search; 403 is handled gracefully.
- collectstatic must run before production gunicorn start.

## Pointers

- See the `pnpm-workspace` skill for workspace structure

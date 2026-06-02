import logging

import requests as http_requests
import threading

from django.conf import settings
from django.db import connection

from functools import wraps

from .digest import send_code, send_welcome
from .models import EmailVerification, MatchedItem, NotificationSettings, Topic  # EmailVerification is the new bit

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .pipeline import poll_topic
from .ai_filter import generate_rubric_and_keywords
from .forms import NotificationSettingsForm, TopicReviewForm, TopicSetupForm, TopicEmailForm
from .models import MatchedItem, NotificationSettings, Topic

logger = logging.getLogger(__name__)


def index(request):
    return render(request, 'index.html')

# ── Step 1: enter URL ────────────────────────────────────────────────────────

def setup(request):
    topics = Topic.objects.order_by('-updated_at')
    form = TopicSetupForm()

    if request.method == 'POST':
        form = TopicSetupForm(request.POST)
        if form.is_valid():
            url = form.cleaned_data['url']

            # Duplicate guard
            existing = Topic.objects.filter(url=url).first()
            if existing:
                messages.info(request, "That URL is already tracked — you can edit the rubric below.")
                return redirect('topic_review', pk=existing.pk)

            # Fetch page content
            try:
                resp = http_requests.get(url, timeout=15, headers={'User-Agent': 'Overheard/1.0'})
                resp.raise_for_status()
                page_text = resp.text[:10000]
            except Exception as exc:
                logger.warning("Failed to fetch %s: %s", url, exc)
                messages.error(request, f"Couldn't reach that URL ({exc}). Double-check it and try again.")
                return render(request, 'setup.html', {'form': form, 'topics': topics})

            # Generate rubric + keywords
            try:
                rubric, keywords = generate_rubric_and_keywords(url, page_text)
            except Exception as exc:
                logger.error("AI error for %s: %s", url, exc)
                messages.error(request, f"Claude couldn't analyse the page — is ANTHROPIC_API_KEY set? ({exc})")
                return render(request, 'setup.html', {'form': form, 'topics': topics})

            topic = Topic.objects.create(url=url, rubric=rubric, keywords=keywords, score_threshold=60)
            return redirect('topic_review', pk=topic.pk)

    return render(request, 'setup.html', {'form': form, 'topics': topics, 'step': 1})

def _bg_scan(topic_id):
    """Run the first scan in the background while the user types their code."""
    try:
        topic = Topic.objects.get(pk=topic_id)
        poll_topic(topic, max_queries=3, score_limit=10)
    except Exception:
        logger.exception("Background scan failed for topic %s", topic_id)
    finally:
        connection.close()  # threads get their own DB connection; close it

# ── Step 2: review & edit rubric/keywords ────────────────────────────────────

def topic_review(request, pk):
    topic = get_object_or_404(Topic, pk=pk)
    if request.method == 'POST':
        form = TopicReviewForm(request.POST, instance=topic)
        if form.is_valid():
            form.save()
            return redirect('topic_email', pk=topic.pk)   # advance to the email step
    else:
        form = TopicReviewForm(instance=topic)
    return render(request, 'review.html', {'topic': topic, 'form': form, 'step': 2})


def topic_delete(request, pk):
    topic = get_object_or_404(Topic, pk=pk)
    if request.method == 'POST':
        topic.delete()
        messages.success(request, "Topic deleted.")
    return redirect('setup')

@_anonymous_only
def topic_email(request, pk):
    topic = get_object_or_404(Topic, pk=pk)
    if request.method == 'POST':
        form = TopicEmailForm(request.POST, instance=topic)
        if form.is_valid():
            email = form.cleaned_data['email']
            existing = (Topic.objects
                        .filter(email__iexact=email, email_verified=True)
                        .exclude(pk=topic.pk).first())
            if existing:
                # This email already owns an account — send them back into it, not a duplicate.
                if not topic.email_verified:
                    topic.delete()          # discard the stray in-progress topic
                target = existing
            else:
                form.save()                 # attach the email to this in-progress topic
                target = topic
                threading.Thread(target=_bg_scan, args=(target.pk,), daemon=True).start()

            ev = EmailVerification.issue(target, email)
            if settings.DEBUG:
                logger.warning("DEV: verification code for %s is %s", email, ev.code)
            send_code(email, ev.code)
            return redirect('topic_verify', pk=target.pk)
    else:
        form = TopicEmailForm(instance=topic)
    return render(request, 'email.html', {'topic': topic, 'form': form, 'step': 3})

def topic_scan(request, pk):
    topic = get_object_or_404(Topic, pk=pk)
    if request.method == 'POST':
        try:
            poll_topic(topic, max_queries=3, score_limit=10)
        except Exception as exc:
            logger.error("Initial scan failed for topic %s: %s", topic.pk, exc)
        messages.success(request, "You're all set — here's what we found. We'll email you each morning.")
        return redirect('dashboard')
    return render(request, 'scanning.html', {'topic': topic})
@_anonymous_only
def topic_verify(request, pk):
    topic = get_object_or_404(Topic, pk=pk)

    if request.method == 'POST':
        if request.POST.get('action') == 'resend':
            latest = EmailVerification.latest_for(topic)
            if latest and latest.seconds_since_sent() < EmailVerification.RESEND_COOLDOWN_SECONDS:
                messages.info(request, "Hang on a few seconds before asking for another code.")
            elif topic.email:
                ev = EmailVerification.issue(topic, topic.email)
                if settings.DEBUG:
                    logger.warning("DEV: verification code for %s is %s", topic.email, ev.code)
                send_code(topic.email, ev.code)
                messages.success(request, "New code sent.")
            return redirect('topic_verify', pk=topic.pk)

        ev = EmailVerification.latest_for(topic)
        code = (request.POST.get('code') or '').strip()
        if ev is None or ev.is_expired():
            messages.error(request, "That code has expired — request a new one.")
        elif ev.attempts >= EmailVerification.MAX_ATTEMPTS:
            messages.error(request, "Too many tries. Request a fresh code.")
        elif code == ev.code:
            was_new = not topic.email_verified
            ev.consumed = True
            ev.save(update_fields=['consumed'])
            topic.email_verified = True
            topic.save(update_fields=['email_verified'])
            request.session['topic_id'] = topic.pk
            if was_new:
                try:
                    send_welcome(topic)
                except Exception:
                    logger.exception("Welcome email failed for topic %s", topic.pk)
            return redirect('dashboard')
        else:
            ev.attempts += 1
            ev.save(update_fields=['attempts'])
            messages.error(request, "That code didn't match. Try again.")

    return render(request, 'verify.html', {'topic': topic, 'step': 3, 'email': topic.email})

# ── Dashboard ────────────────────────────────────────────────────────────────

def _session_topic(request):
    """The signed-in user's verified topic, or None."""
    tid = request.session.get('topic_id')
    return Topic.objects.filter(pk=tid, email_verified=True).first() if tid else None


def _anonymous_only(view):
    """Onboarding steps are for logged-out visitors; signed-in users go to their dashboard."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if _session_topic(request):
            return redirect('dashboard')
        return view(request, *args, **kwargs)
    return wrapper

def dashboard(request):
    topic = _session_topic(request)
    if topic is None:
        return redirect('index')

    status_filter = request.GET.get('status', 'new')
    if status_filter not in [s.value for s in MatchedItem.Status]:
        status_filter = 'new'

    base = MatchedItem.objects.filter(topic=topic)
    items = base.filter(status=status_filter).order_by('-fetched_at')[:100]
    counts = {s.value: base.filter(status=s.value).count() for s in MatchedItem.Status}
    status_choices = [{'value': s.value, 'label': s.label} for s in MatchedItem.Status]

    return render(request, 'dashboard.html', {
        'topic': topic, 'items': items, 'status_filter': status_filter,
        'counts': counts, 'status_choices': status_choices,
    })
@require_POST
def item_action(request, pk):
    item = get_object_or_404(MatchedItem, pk=pk, topic_id=request.session.get('topic_id'))
    action = request.POST.get('action')
    if action in (MatchedItem.Status.REPLIED, MatchedItem.Status.IGNORED):
        item.status = action
        item.save()
    return redirect(request.POST.get('next', 'dashboard'))


# ── Settings ─────────────────────────────────────────────────────────────────

def settings_page(request):
    config = NotificationSettings.get()
    form = NotificationSettingsForm(instance=config)

    if request.method == 'POST':
        form = NotificationSettingsForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, "Settings saved.")
            return redirect('settings')

    return render(request, 'settings.html', {'form': form})

def logout(request):
    request.session.flush()
    return redirect('index')

import logging

import requests as http_requests
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .ai_filter import generate_rubric_and_keywords
from .forms import NotificationSettingsForm, TopicReviewForm, TopicSetupForm
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

    return render(request, 'setup.html', {'form': form, 'topics': topics})


# ── Step 2: review & edit rubric/keywords ────────────────────────────────────

def topic_review(request, pk):
    topic = get_object_or_404(Topic, pk=pk)

    if request.method == 'POST':
        form = TopicReviewForm(request.POST, instance=topic)
        if form.is_valid():
            form.save()
            messages.success(request, "Topic saved. Overheard will check Reddit daily and surface relevant posts here.")
            return redirect('dashboard')
    else:
        form = TopicReviewForm(instance=topic)

    return render(request, 'review.html', {'topic': topic, 'form': form})


def topic_delete(request, pk):
    topic = get_object_or_404(Topic, pk=pk)
    if request.method == 'POST':
        topic.delete()
        messages.success(request, "Topic deleted.")
    return redirect('setup')


# ── Dashboard ────────────────────────────────────────────────────────────────

def dashboard(request):
    status_filter = request.GET.get('status', 'new')
    valid_statuses = [s.value for s in MatchedItem.Status]
    if status_filter not in valid_statuses:
        status_filter = 'new'

    items = MatchedItem.objects.filter(status=status_filter).order_by('-fetched_at')[:100]
    status_choices = [{'value': s.value, 'label': s.label} for s in MatchedItem.Status]
    counts = {s.value: MatchedItem.objects.filter(status=s.value).count() for s in MatchedItem.Status}
    topics = Topic.objects.order_by('-updated_at')

    return render(request, 'dashboard.html', {
        'items': items,
        'status_filter': status_filter,
        'counts': counts,
        'status_choices': status_choices,
        'topics': topics,
    })


@require_POST
def item_action(request, pk):
    item = get_object_or_404(MatchedItem, pk=pk)
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

import logging

import requests as http_requests
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .ai_filter import generate_rubric_and_keywords
from .forms import ScheduleConfigForm, TopicEditForm, TopicSetupForm
from .models import MatchedItem, ScheduleConfig, Topic

logger = logging.getLogger(__name__)


def index(request):
    return render(request, 'index.html')


def setup(request):
    topics = Topic.objects.order_by('-updated_at')
    form = TopicSetupForm()
    schedule_form = ScheduleConfigForm(instance=ScheduleConfig.get())

    if request.method == 'POST' and 'url' in request.POST:
        form = TopicSetupForm(request.POST)
        if form.is_valid():
            url = form.cleaned_data['url']

            try:
                resp = http_requests.get(url, timeout=15, headers={'User-Agent': 'Overheard/1.0'})
                resp.raise_for_status()
                page_text = resp.text[:10000]
            except Exception as exc:
                logger.warning("Failed to fetch %s: %s", url, exc)
                messages.error(request, f"Couldn't fetch that URL: {exc}")
                return render(request, 'setup.html', {
                    'form': form, 'topics': topics, 'schedule_form': schedule_form,
                })

            try:
                rubric, keywords = generate_rubric_and_keywords(url, page_text)
            except Exception as exc:
                logger.error("AI error for %s: %s", url, exc)
                messages.error(request, f"AI step failed — is ANTHROPIC_API_KEY set? ({exc})")
                return render(request, 'setup.html', {
                    'form': form, 'topics': topics, 'schedule_form': schedule_form,
                })

            Topic.objects.create(url=url, rubric=rubric, keywords=keywords, score_threshold=60)
            messages.success(request, "Topic created — Overheard is now watching Reddit for matches.")
            return redirect('setup')

    return render(request, 'setup.html', {
        'form': form,
        'topics': topics,
        'schedule_form': schedule_form,
    })


def topic_edit(request, pk):
    topic = get_object_or_404(Topic, pk=pk)
    topics = Topic.objects.order_by('-updated_at')
    schedule_form = ScheduleConfigForm(instance=ScheduleConfig.get())
    if request.method == 'POST':
        form = TopicEditForm(request.POST, instance=topic)
        if form.is_valid():
            form.save()
            messages.success(request, "Topic updated.")
            return redirect('setup')
    else:
        form = TopicEditForm(instance=topic)
    return render(request, 'setup.html', {
        'form': form, 'topics': topics, 'editing': topic,
        'schedule_form': schedule_form,
    })


def topic_delete(request, pk):
    topic = get_object_or_404(Topic, pk=pk)
    if request.method == 'POST':
        topic.delete()
        messages.success(request, "Topic deleted.")
    return redirect('setup')


@require_POST
def schedule_save(request):
    config = ScheduleConfig.get()
    form = ScheduleConfigForm(request.POST, instance=config)
    if form.is_valid():
        form.save()
        messages.success(request, "Schedule saved.")
    else:
        for err in form.errors.values():
            messages.error(request, str(err))
    return redirect('setup')


def dashboard(request):
    status_filter = request.GET.get('status', 'new')
    valid_statuses = [s.value for s in MatchedItem.Status]
    if status_filter not in valid_statuses:
        status_filter = 'new'

    items = MatchedItem.objects.filter(status=status_filter).order_by('-fetched_at')[:100]
    status_choices = [
        {'value': s.value, 'label': s.label}
        for s in MatchedItem.Status
    ]
    counts = {s.value: MatchedItem.objects.filter(status=s.value).count() for s in MatchedItem.Status}
    return render(request, 'dashboard.html', {
        'items': items,
        'status_filter': status_filter,
        'counts': counts,
        'status_choices': status_choices,
    })


@require_POST
def item_action(request, pk):
    item = get_object_or_404(MatchedItem, pk=pk)
    action = request.POST.get('action')
    if action in (MatchedItem.Status.REPLIED, MatchedItem.Status.IGNORED):
        item.status = action
        item.save()
    next_url = request.POST.get('next', 'dashboard')
    return redirect(next_url)

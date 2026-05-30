from django.db import models


class Topic(models.Model):
    url = models.URLField(max_length=500)
    rubric = models.TextField(help_text="AI-generated relevance rubric — what the problem is, who has it, intent signals, and non-examples.")
    keywords = models.JSONField(default=list, help_text="List of search queries/keywords for Reddit/X.")
    score_threshold = models.IntegerField(default=60, help_text="Minimum AI score (0-100) to keep an item.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.url

    class Meta:
        ordering = ['-updated_at']


class MatchedItem(models.Model):
    class Platform(models.TextChoices):
        REDDIT = 'reddit', 'Reddit'
        X = 'x', 'X (Twitter)'

    class Status(models.TextChoices):
        NEW = 'new', 'New'
        REPLIED = 'replied', 'Replied'
        IGNORED = 'ignored', 'Ignored'
        SENT = 'sent', 'Sent in digest'

    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='items')
    platform = models.CharField(max_length=20, choices=Platform.choices)
    source_url = models.URLField(max_length=1000)
    author = models.CharField(max_length=300)
    text_snippet = models.TextField()
    # platform:post_id — prevents duplicates across runs
    dedup_key = models.CharField(max_length=600, unique=True)
    score = models.IntegerField()
    why_relevant = models.TextField()
    what_theyre_asking = models.TextField()
    suggested_angle = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    fetched_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"[{self.platform}] {self.author} (score={self.score})"

    class Meta:
        ordering = ['-fetched_at']


class ScheduleConfig(models.Model):
    """Singleton — always use ScheduleConfig.get() instead of creating new rows."""
    poll_interval_hours = models.IntegerField(
        default=6,
        help_text="How often (in hours) to fetch and score new posts.",
    )
    poll_enabled = models.BooleanField(default=True)
    digest_hour = models.IntegerField(
        default=8,
        help_text="Hour of day (UTC, 0–23) to send the daily digest.",
    )
    digest_enabled = models.BooleanField(default=True)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        # Live-reschedule without restart
        try:
            from . import scheduler as sched
            sched.reschedule(
                poll_hours=self.poll_interval_hours,
                digest_hour=self.digest_hour,
            )
        except Exception:
            pass

    class Meta:
        verbose_name = "Schedule config"

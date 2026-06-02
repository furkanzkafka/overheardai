import secrets
from datetime import timedelta
from django.db import models
from django.utils import timezone

class Topic(models.Model):
    url = models.URLField(max_length=500)
    rubric = models.TextField()
    keywords = models.JSONField(default=list)
    score_threshold = models.IntegerField(default=60)
    email = models.EmailField(blank=True, default='')
    email_verified = models.BooleanField(default=False)
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
        WEB = 'web', 'Web'

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


class NotificationSettings(models.Model):
    """Singleton — always access via NotificationSettings.get()"""
    digest_to_email = models.EmailField(
        blank=True, default='',
        help_text="Email address to receive the daily digest.",
    )
    slack_webhook_url = models.CharField(
        max_length=500, blank=True, default='',
        help_text="Slack incoming webhook URL.",
    )

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Notification settings"

class EmailVerification(models.Model):
    CODE_TTL_MINUTES = 10
    MAX_ATTEMPTS = 5
    RESEND_COOLDOWN_SECONDS = 30

    topic = models.ForeignKey(Topic, on_delete=models.CASCADE, related_name='verifications')
    email = models.EmailField()
    code = models.CharField(max_length=6)
    attempts = models.IntegerField(default=0)
    consumed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ['-created_at']

    @classmethod
    def issue(cls, topic, email):
        cls.objects.filter(topic=topic, consumed=False).update(consumed=True)  # retire old codes
        code = f"{secrets.randbelow(1_000_000):06d}"
        return cls.objects.create(
            topic=topic, email=email, code=code,
            expires_at=timezone.now() + timedelta(minutes=cls.CODE_TTL_MINUTES),
        )

    @classmethod
    def latest_for(cls, topic):
        return cls.objects.filter(topic=topic, consumed=False).order_by('-created_at').first()

    def is_expired(self):
        return timezone.now() > self.expires_at

    def seconds_since_sent(self):
        return (timezone.now() - self.created_at).total_seconds()
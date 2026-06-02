from django import forms
from .models import NotificationSettings, Topic


class TopicSetupForm(forms.Form):
    url = forms.URLField(
        label="Your website URL",
        widget=forms.URLInput(attrs={
            'placeholder': 'yoursite.com',
            'class': 'field-input',
            'autocomplete': 'off',
        }),
    )

    def clean_url(self):
        url = self.cleaned_data['url'].strip()
        if url and not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        return url


class TopicReviewForm(forms.ModelForm):
    keywords = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'field-input', 'id': 'kw-textarea', 'rows': 6}),
    )

    class Meta:
        model = Topic
        fields = []  # rubric stays as generated; this form only edits keywords

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and isinstance(self.instance.keywords, list):
            self.fields['keywords'].initial = '\n'.join(self.instance.keywords)

    def clean_keywords(self):
        raw = self.cleaned_data.get('keywords', '')
        return [line.strip() for line in raw.splitlines() if line.strip()]

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.keywords = self.cleaned_data['keywords']
        if commit:
            instance.save()
        return instance

class TopicEmailForm(forms.ModelForm):
    email = forms.EmailField(
        label="Your email",
        widget=forms.EmailInput(attrs={
            'class': 'field-input',
            'placeholder': 'you@yourcompany.com',
            'autocomplete': 'off',
        }),
        help_text="We'll send your morning digest here.",
    )

    class Meta:
        model = Topic
        fields = ['email']

class NotificationSettingsForm(forms.ModelForm):
    class Meta:
        model = NotificationSettings
        fields = ['digest_to_email', 'slack_webhook_url']
        widgets = {
            'digest_to_email': forms.EmailInput(attrs={'class': 'input', 'placeholder': 'you@yourcompany.com'}),
            'slack_webhook_url': forms.URLInput(attrs={'class': 'input', 'placeholder': 'https://hooks.slack.com/services/…'}),
        }
        labels = {
            'digest_to_email': 'Send digest to',
            'slack_webhook_url': 'Slack webhook URL',
        }

class TopicEmailForm(forms.ModelForm):
    email = forms.EmailField(
        label="Your email",
        widget=forms.EmailInput(attrs={
            'class': 'input input--xl',
            'placeholder': 'you@yourcompany.com',
            'autofocus': True,
        }),
        help_text="We'll send your morning digest here. Unsubscribe anytime.",
    )

    class Meta:
        model = Topic
        fields = ['email']
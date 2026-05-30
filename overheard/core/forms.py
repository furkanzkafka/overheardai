from django import forms
from .models import NotificationSettings, Topic


class TopicSetupForm(forms.Form):
    url = forms.URLField(
        label="Your website URL",
        widget=forms.URLInput(attrs={
            'placeholder': 'yoursite.com',
            'class': 'input input--xl',
            'autofocus': True,
        }),
    )

    def clean_url(self):
        url = self.cleaned_data['url'].strip()
        if url and not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        return url


class TopicReviewForm(forms.ModelForm):
    keywords = forms.CharField(
        label="Keywords",
        widget=forms.Textarea(attrs={'class': 'input', 'rows': 6}),
        help_text="One search query per line. Claude generated these — add, remove, or tweak as you see fit.",
    )

    class Meta:
        model = Topic
        fields = ['rubric', 'keywords']
        widgets = {
            'rubric': forms.Textarea(attrs={'class': 'input', 'rows': 7}),
        }
        labels = {
            'rubric': 'Relevance rubric',
        }
        help_texts = {
            'rubric': "Describes who you want to reach and what qualifies as a genuine match. Edit freely.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            kws = self.instance.keywords
            if isinstance(kws, list):
                self.fields['keywords'].initial = '\n'.join(kws)

    def clean_keywords(self):
        raw = self.cleaned_data['keywords']
        return [line.strip() for line in raw.splitlines() if line.strip()]

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.keywords = self.cleaned_data['keywords']
        if commit:
            instance.save()
        return instance


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

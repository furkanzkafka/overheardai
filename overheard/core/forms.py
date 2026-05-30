from django import forms
from .models import Topic


class TopicSetupForm(forms.Form):
    """Initial setup: just the URL. Score threshold defaults to 60."""
    url = forms.URLField(
        label="Your website URL",
        widget=forms.URLInput(attrs={
            'placeholder': 'yoursite.com',
            'class': 'input',
        }),
        help_text="Paste your homepage or product page — we'll read it to understand what you do.",
    )

    def clean_url(self):
        url = self.cleaned_data['url'].strip()
        if url and not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        return url


class TopicEditForm(forms.ModelForm):
    keywords = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'input', 'rows': 4}),
        help_text="One keyword or phrase per line.",
    )

    class Meta:
        model = Topic
        fields = ['url', 'rubric', 'keywords', 'score_threshold']
        widgets = {
            'url': forms.URLInput(attrs={'class': 'input'}),
            'rubric': forms.Textarea(attrs={'class': 'input', 'rows': 6}),
            'score_threshold': forms.NumberInput(attrs={'class': 'input input--narrow'}),
        }
        labels = {
            'score_threshold': 'Quality bar (0–100)',
        }
        help_texts = {
            'score_threshold': 'Only keep posts scoring at or above this. 60 = average match quality.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            kws = self.instance.keywords
            if isinstance(kws, list):
                self.fields['keywords'].initial = '\n'.join(kws)

    def clean_keywords(self):
        raw = self.cleaned_data['keywords']
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        return lines

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.keywords = self.cleaned_data['keywords']
        if commit:
            instance.save()
        return instance

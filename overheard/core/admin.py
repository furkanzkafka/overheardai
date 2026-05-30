from django.contrib import admin
from .models import Topic, MatchedItem


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ('url', 'score_threshold', 'created_at')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(MatchedItem)
class MatchedItemAdmin(admin.ModelAdmin):
    list_display = ('platform', 'author', 'score', 'status', 'fetched_at')
    list_filter = ('platform', 'status', 'topic')
    readonly_fields = ('fetched_at', 'sent_at', 'dedup_key')

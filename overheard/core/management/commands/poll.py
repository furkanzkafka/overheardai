"""
Management command: poll
  python manage.py poll [--topic <id>] [--dry-run]

Runs the search → score → store pipeline for all (or one) topics by
calling core.pipeline.poll_topic on each.
"""
from django.core.management.base import BaseCommand

from core.models import Topic
from core.pipeline import poll_topic


class Command(BaseCommand):
    help = "Search, score with Claude, and store matches for every topic (or one)."

    def add_arguments(self, parser):
        parser.add_argument("--topic", type=int, default=None, help="Only poll this topic ID.")
        parser.add_argument("--dry-run", action="store_true", help="Search and score but don't save.")

    def handle(self, *args, **options):
        topics = (Topic.objects.filter(pk=options["topic"])
                  if options["topic"] else Topic.objects.all())
        if not topics.exists():
            self.stdout.write(self.style.WARNING("No topics configured. Add one at /setup/"))
            return

        total_kept = 0
        for topic in topics:
            self.stdout.write(f"\nPolling topic {topic.pk}: {topic.url}")
            stats = poll_topic(topic, dry_run=options["dry_run"])
            self.stdout.write(f"  fetched {stats['fetched']}, kept {stats['kept']}")
            total_kept += stats["kept"]

        suffix = " (dry run — nothing saved)" if options["dry_run"] else ""
        self.stdout.write(self.style.SUCCESS(f"\nDone{suffix}. Kept {total_kept}."))
"""
Management command: poll
  python manage.py poll [--topic <id>] [--lookback <hours>] [--dry-run]

Runs the full fetch → AI filter → store pipeline for all (or one) topics.
Designed to be called from a Render cron job, e.g.:
  python manage.py poll
"""
import logging

from django.core.management.base import BaseCommand
from django.db import IntegrityError

from core.models import Topic, MatchedItem
from core.fetchers import fetch_reddit, fetch_x
from core.ai_filter import score_item

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Fetch new posts from Reddit (and optionally X), score them with Claude, and store matches."

    def add_arguments(self, parser):
        parser.add_argument("--topic", type=int, default=None, help="Only poll this topic ID.")
        parser.add_argument("--lookback", type=int, default=26, help="Hours to look back (default 26).")
        parser.add_argument("--dry-run", action="store_true", help="Fetch and score but don't save.")

    def handle(self, *args, **options):
        topic_id = options["topic"]
        lookback = options["lookback"]
        dry_run = options["dry_run"]

        topics = Topic.objects.filter(pk=topic_id) if topic_id else Topic.objects.all()
        if not topics.exists():
            self.stdout.write(self.style.WARNING("No topics configured. Add one at /setup/"))
            return

        total_fetched = total_kept = total_skipped = 0

        for topic in topics:
            self.stdout.write(f"\nPolling topic {topic.pk}: {topic.url}")
            keywords = topic.keywords if isinstance(topic.keywords, list) else []

            candidates = list(fetch_reddit(keywords, lookback_hours=lookback))
            candidates += list(fetch_x(keywords, lookback_hours=lookback))

            self.stdout.write(f"  {len(candidates)} candidates fetched from Reddit + X")
            total_fetched += len(candidates)

            for item in candidates:
                dedup_key = item["dedup_key"]
                if MatchedItem.objects.filter(dedup_key=dedup_key).exists():
                    total_skipped += 1
                    continue

                try:
                    result = score_item(item["text_snippet"], topic.rubric)
                except Exception as exc:
                    logger.error("Score failed for %s: %s", dedup_key, exc)
                    continue

                score = result.get("score", 0)
                self.stdout.write(
                    f"  [{item['platform']}] {item['author']!r:30} score={score:3d} "
                    + ("✓" if score >= topic.score_threshold else "✗")
                )

                if score < topic.score_threshold:
                    continue

                if dry_run:
                    total_kept += 1
                    continue

                try:
                    MatchedItem.objects.create(
                        topic=topic,
                        platform=item["platform"],
                        source_url=item["source_url"],
                        author=item["author"],
                        text_snippet=item["text_snippet"],
                        dedup_key=dedup_key,
                        score=score,
                        why_relevant=result.get("why_relevant", ""),
                        what_theyre_asking=result.get("what_theyre_asking", ""),
                        suggested_angle=result.get("suggested_angle", ""),
                    )
                    total_kept += 1
                except IntegrityError:
                    total_skipped += 1

        suffix = " (DRY RUN — nothing saved)" if dry_run else ""
        self.stdout.write(self.style.SUCCESS(
            f"\nDone{suffix}. Fetched {total_fetched}, kept {total_kept}, skipped {total_skipped} duplicates."
        ))

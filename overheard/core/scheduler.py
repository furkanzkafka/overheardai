"""
Background scheduler — runs once a day, automatically.
  - Poll: every 24 hours
  - Digest: daily at 08:00 UTC

No configuration needed. Starts with the server.
"""
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _run_poll():
    try:
        from django.db import IntegrityError
        from core.models import MatchedItem, Topic
        from core.ai_filter import score_item
        from core.fetchers import fetch_reddit, fetch_x

        topics = Topic.objects.all()
        if not topics.exists():
            logger.info("Scheduler poll: no topics configured, skipping.")
            return

        logger.info("Scheduler poll: %d topic(s).", topics.count())
        kept = 0
        for topic in topics:
            keywords = topic.keywords if isinstance(topic.keywords, list) else []
            candidates = list(fetch_reddit(keywords)) + list(fetch_x(keywords))
            for item in candidates:
                dedup_key = item["dedup_key"]
                if MatchedItem.objects.filter(dedup_key=dedup_key).exists():
                    continue
                try:
                    result = score_item(item["text_snippet"], topic.rubric)
                except Exception as exc:
                    logger.error("Score error %s: %s", dedup_key, exc)
                    continue
                score = result.get("score", 0)
                if score < topic.score_threshold:
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
                    kept += 1
                except IntegrityError:
                    pass
        logger.info("Scheduler poll done: %d new item(s) kept.", kept)
    except Exception as exc:
        logger.error("Scheduler poll failed: %s", exc, exc_info=True)


def _run_digest():
    try:
        from core.digest import send_digest
        result = send_digest()
        logger.info(
            "Digest sent: %d items, email=%s",
            result["items"], result["email"], result["slack"],
        )
    except Exception as exc:
        logger.error("Scheduler digest failed: %s", exc, exc_info=True)


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return

    _scheduler = BackgroundScheduler(daemon=True)

    # Poll once every 24 hours
    _scheduler.add_job(_run_poll, trigger=IntervalTrigger(hours=24), id="poll")

    # Digest every day at 08:00 UTC
    _scheduler.add_job(_run_digest, trigger=CronTrigger(hour=8, minute=0), id="digest")

    _scheduler.start()
    logger.info("Scheduler started — daily poll + 08:00 UTC digest.")

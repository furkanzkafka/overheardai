"""
Background scheduler — runs poll and send_digest inside the Django process.
APScheduler BackgroundScheduler keeps jobs running in a daemon thread pool.

Jobs re-read ScheduleConfig from the DB before each run so edits take effect
without a server restart.  Call reschedule() after saving ScheduleConfig to
also adjust the trigger timing immediately.
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
        from core.models import MatchedItem, ScheduleConfig, Topic
        from core.ai_filter import score_item
        from core.fetchers import fetch_reddit, fetch_x

        config = ScheduleConfig.get()
        if not config.poll_enabled:
            return

        topics = Topic.objects.all()
        if not topics.exists():
            logger.info("Scheduler poll: no topics, skipping.")
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
        logger.info("Scheduler poll done: %d kept.", kept)
    except Exception as exc:
        logger.error("Scheduler poll failed: %s", exc, exc_info=True)


def _run_digest():
    try:
        from core.digest import send_digest
        from core.models import ScheduleConfig

        config = ScheduleConfig.get()
        if not config.digest_enabled:
            return

        logger.info("Scheduler: sending digest.")
        result = send_digest()
        logger.info(
            "Digest sent: %d items, email=%s, slack=%s",
            result["items"], result["email"], result["slack"],
        )
    except Exception as exc:
        logger.error("Scheduler digest failed: %s", exc, exc_info=True)


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return

    try:
        from core.models import ScheduleConfig
        config = ScheduleConfig.get()
        poll_hours = config.poll_interval_hours
        digest_hour = config.digest_hour
    except Exception:
        poll_hours = 6
        digest_hour = 8

    _scheduler = BackgroundScheduler(daemon=True)

    _scheduler.add_job(
        _run_poll,
        trigger=IntervalTrigger(hours=poll_hours),
        id="poll",
        replace_existing=True,
    )
    _scheduler.add_job(
        _run_digest,
        trigger=CronTrigger(hour=digest_hour, minute=0),
        id="digest",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(
        "Scheduler started — poll every %dh, digest at %02d:00 UTC.",
        poll_hours, digest_hour,
    )


def reschedule(poll_hours: int | None = None, digest_hour: int | None = None):
    """Live-update trigger timing after ScheduleConfig is saved."""
    global _scheduler
    if _scheduler is None:
        return
    try:
        if poll_hours is not None:
            _scheduler.reschedule_job("poll", trigger=IntervalTrigger(hours=poll_hours))
        if digest_hour is not None:
            _scheduler.reschedule_job("digest", trigger=CronTrigger(hour=digest_hour, minute=0))
        logger.info(
            "Scheduler rescheduled — poll every %sh, digest at %sh UTC.",
            poll_hours, digest_hour,
        )
    except Exception as exc:
        logger.error("Reschedule failed: %s", exc)

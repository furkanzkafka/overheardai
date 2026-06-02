import logging
from urllib.parse import urlparse

from .ai_filter import score_item
from .models import MatchedItem
from .search import search_google

logger = logging.getLogger(__name__)

RECENCY = "qdr:w"          # Google/Serper "past week"
MAX_TEXT = 4000            # cap stored/scored text


def _subreddit(url: str) -> str:
    """.../r/AskNYC/comments/... -> 'AskNYC'."""
    parts = urlparse(url).path.strip("/").split("/")
    return parts[1] if len(parts) >= 2 and parts[0] == "r" else ""


def poll_topic(topic, max_queries=None, score_limit=None, dry_run=False) -> dict:
    keywords = [k for k in (topic.keywords or []) if k]
    if max_queries:
        keywords = keywords[:max_queries]

    # 1. Gather + dedupe candidate URLs — Reddit only, last week.
    candidates, seen = [], set()
    for query in keywords:
        scoped = f"site:reddit.com {query}"
        try:
            results = search_google(scoped, num=10, tbs=RECENCY)
        except Exception as exc:
            logger.error("Serper search failed for %r: %s", scoped, exc)
            continue
        for r in results:
            url = r.get("link", "")
            if url and url not in seen:
                seen.add(url)
                candidates.append(r)

    if score_limit:
        candidates = candidates[:score_limit]

    # 2. Score each on its title + snippet (content fetch is blocked by Reddit, so
    #    we judge from the search preview, with the subreddit as a location cue).
    fetched, kept = len(candidates), 0
    for r in candidates:
        url = r["link"]
        dedup_key = f"web:{topic.pk}:{url}"
        if MatchedItem.objects.filter(dedup_key=dedup_key).exists():
            continue

        subreddit = _subreddit(url)
        text = f'{r.get("title", "")} — {r.get("snippet", "")}'.strip(" —")[:MAX_TEXT]
        if not text:
            continue

        try:
            result = score_item(text, topic.rubric, subreddit=subreddit)
        except Exception as exc:
            logger.error("Scoring failed for %s: %s", url, exc)
            continue
        if result.get("score", 0) < topic.score_threshold:
            continue

        if dry_run:
            kept += 1
            logger.info("KEPT(dry) score=%s r/%s %s", result.get("score"), subreddit, url)
            continue

        MatchedItem.objects.create(
            topic=topic,
            platform=MatchedItem.Platform.REDDIT,
            source_url=url,
            author=f"r/{subreddit}" if subreddit else "reddit.com",
            text_snippet=text,
            dedup_key=dedup_key,
            score=result["score"],
            why_relevant=result.get("why_relevant", ""),
            what_theyre_asking=result.get("what_theyre_asking", ""),
            suggested_angle=result.get("suggested_angle", ""),
        )
        kept += 1

    logger.info("poll_topic: topic %s fetched %d kept %d", topic.pk, fetched, kept)
    return {"fetched": fetched, "kept": kept}
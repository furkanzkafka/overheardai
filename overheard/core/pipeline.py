import logging
from urllib.parse import urlparse

from .ai_filter import score_item
from .models import MatchedItem
from .search import search_google

logger = logging.getLogger(__name__)


def poll_topic(topic, max_queries=None, score_limit=None, dry_run=False) -> dict:
    keywords = [k for k in (topic.keywords or []) if k]
    if max_queries:
        keywords = keywords[:max_queries]

    # 1. gather + dedupe candidates by URL
    candidates, seen = [], set()
    for query in keywords:
        try:
            results = search_google(query, num=10)
        except Exception as exc:
            logger.error("Serper search failed for %r: %s", query, exc)
            continue
        for r in results:
            url = r.get("link", "")
            if url and url not in seen:
                seen.add(url)
                candidates.append(r)

    if score_limit:
        candidates = candidates[:score_limit]

    # 2. score + store
    fetched, kept = len(candidates), 0
    for r in candidates:
        url = r["link"]
        dedup_key = f"web:{topic.pk}:{url}"
        if MatchedItem.objects.filter(dedup_key=dedup_key).exists():
            continue
        snippet = f"{r.get('title', '')} — {r.get('snippet', '')}".strip(" —")
        try:
            result = score_item(snippet, topic.rubric)
        except Exception as exc:
            logger.error("Scoring failed for %s: %s", url, exc)
            continue
        if result.get("score", 0) < topic.score_threshold:
            continue
        if dry_run:
            kept += 1
            continue
        MatchedItem.objects.create(
            topic=topic, platform=MatchedItem.Platform.WEB,
            source_url=url, author=urlparse(url).netloc.replace("www.", ""),
            text_snippet=snippet, dedup_key=dedup_key,
            score=result["score"],
            why_relevant=result.get("why_relevant", ""),
            what_theyre_asking=result.get("what_theyre_asking", ""),
            suggested_angle=result.get("suggested_angle", ""),
        )
        kept += 1

    logger.info("poll_topic: topic %s fetched %d kept %d", topic.pk, fetched, kept)
    return {"fetched": fetched, "kept": kept}
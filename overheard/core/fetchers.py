"""
Fetchers for Reddit and X (Twitter).

Reddit: uses PRAW with OAuth "script" app credentials.
X: uses bearer-token auth on v2 recent-search endpoint.
    This module is OPTIONAL — if X credentials are missing or the endpoint
    returns an access error, the error is logged and fetching continues on
    Reddit alone.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Generator

from django.conf import settings

logger = logging.getLogger(__name__)


# ── Reddit ────────────────────────────────────────────────────────────────────

def _reddit_client():
    import praw
    return praw.Reddit(
        client_id=settings.REDDIT_CLIENT_ID,
        client_secret=settings.REDDIT_CLIENT_SECRET,
        user_agent=settings.REDDIT_USER_AGENT,
    )


def fetch_reddit(keywords: list[str], lookback_hours: int = 26) -> Generator[dict, None, None]:
    """
    Yield candidate dicts for each keyword query:
      platform, dedup_key, source_url, author, text_snippet
    Skips items older than lookback_hours.
    """
    if not settings.REDDIT_CLIENT_ID or not settings.REDDIT_CLIENT_SECRET:
        logger.warning("Reddit credentials not configured — skipping Reddit fetch.")
        return

    reddit = _reddit_client()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    for query in keywords:
        logger.info("Reddit search: %r", query)
        try:
            results = reddit.subreddit("all").search(
                query,
                sort="new",
                time_filter="day",
                limit=25,
            )
            for submission in results:
                created = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)
                if created < cutoff:
                    continue
                # Prefer selftext if it exists; fall back to title
                body = (submission.selftext or submission.title)[:2000]
                yield {
                    "platform": "reddit",
                    "dedup_key": f"reddit:{submission.id}",
                    "source_url": f"https://reddit.com{submission.permalink}",
                    "author": str(submission.author) if submission.author else "[deleted]",
                    "text_snippet": body,
                }

            # Also check top-level comments
            for submission in reddit.subreddit("all").search(
                query, sort="new", time_filter="day", limit=10
            ):
                try:
                    submission.comments.replace_more(limit=0)
                    for comment in submission.comments.list()[:10]:
                        created = datetime.fromtimestamp(comment.created_utc, tz=timezone.utc)
                        if created < cutoff:
                            continue
                        yield {
                            "platform": "reddit",
                            "dedup_key": f"reddit:{comment.id}",
                            "source_url": f"https://reddit.com{comment.permalink}",
                            "author": str(comment.author) if comment.author else "[deleted]",
                            "text_snippet": comment.body[:2000],
                        }
                except Exception as exc:
                    logger.debug("Comment fetch error: %s", exc)

        except Exception as exc:
            logger.error("Reddit search failed for %r: %s", query, exc)


# ── X (Twitter) — OPTIONAL ────────────────────────────────────────────────────

_X_SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"


def fetch_x(keywords: list[str], lookback_hours: int = 26) -> Generator[dict, None, None]:
    """
    Yield candidate dicts from X v2 recent-search.
    If credentials are absent or the endpoint returns a non-200, logs clearly
    and yields nothing — the poll command will continue on Reddit alone.
    """
    bearer = settings.X_BEARER_TOKEN
    if not bearer:
        logger.info("X_BEARER_TOKEN not set — skipping X fetch.")
        return

    import requests
    headers = {"Authorization": f"Bearer {bearer}"}
    start_time = (
        datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    for query in keywords:
        # X search query: exclude retweets to reduce noise
        x_query = f"{query} -is:retweet lang:en"
        params = {
            "query": x_query,
            "max_results": 20,
            "start_time": start_time,
            "tweet.fields": "author_id,created_at,text",
            "expansions": "author_id",
            "user.fields": "username",
        }
        try:
            resp = requests.get(_X_SEARCH_URL, headers=headers, params=params, timeout=15)
            if resp.status_code == 403:
                logger.warning(
                    "X API returned 403 — your access tier may not include recent-search. "
                    "Skipping X fetch for the rest of this run."
                )
                return
            if resp.status_code != 200:
                logger.error("X API error %d: %s", resp.status_code, resp.text[:200])
                continue

            data = resp.json()
            users = {u["id"]: u["username"] for u in data.get("includes", {}).get("users", [])}
            for tweet in data.get("data", []):
                yield {
                    "platform": "x",
                    "dedup_key": f"x:{tweet['id']}",
                    "source_url": f"https://x.com/i/web/status/{tweet['id']}",
                    "author": users.get(tweet["author_id"], tweet["author_id"]),
                    "text_snippet": tweet["text"][:2000],
                }
        except Exception as exc:
            logger.error("X search failed for %r: %s", query, exc)

"""
Fetchers for Reddit and X (Twitter).

Reddit: uses Reddit's public JSON search endpoint — no credentials required.
  Just a well-formed User-Agent header; works anonymously at Reddit's free rate limit.

X: uses bearer-token auth on v2 recent-search endpoint.
  OPTIONAL — if X credentials are missing or the endpoint returns an access
  error, the error is logged and fetching continues on Reddit alone.
"""
import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Generator

import requests as http_requests
from django.conf import settings

logger = logging.getLogger(__name__)

_REDDIT_BASE = "https://www.reddit.com"
_REDDIT_HEADERS = {
    "User-Agent": "Overheard/1.0 (read-only digest tool)",
    "Accept": "application/json",
}


# ── Reddit (public JSON — zero credentials needed) ─────────────────────────────

def fetch_reddit(keywords: list[str], lookback_hours: int = 26) -> Generator[dict, None, None]:
    """
    Yield candidate dicts for each keyword query using Reddit's public JSON API.
    No OAuth credentials required — just a User-Agent header.

    Yields dicts with: platform, dedup_key, source_url, author, text_snippet.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

    # ── Posts ──
    for query in keywords:
        logger.info("Reddit public search (posts): %r", query)
        url = f"{_REDDIT_BASE}/search.json"
        params = {"q": query, "sort": "new", "t": "day", "limit": 25, "type": "link"}
        try:
            resp = http_requests.get(url, headers=_REDDIT_HEADERS, params=params, timeout=15)
            if resp.status_code == 429:
                logger.warning("Reddit rate-limited — waiting 10 s.")
                time.sleep(10)
                resp = http_requests.get(url, headers=_REDDIT_HEADERS, params=params, timeout=15)
            resp.raise_for_status()

            for child in resp.json().get("data", {}).get("children", []):
                post = child.get("data", {})
                created = datetime.fromtimestamp(post.get("created_utc", 0), tz=timezone.utc)
                if created < cutoff:
                    continue
                body = (post.get("selftext") or post.get("title", ""))[:2000]
                yield {
                    "platform": "reddit",
                    "dedup_key": f"reddit:{post.get('id', '')}",
                    "source_url": f"https://reddit.com{post.get('permalink', '')}",
                    "author": post.get("author", "[deleted]"),
                    "text_snippet": body,
                }
        except Exception as exc:
            logger.error("Reddit post fetch failed for %r: %s", query, exc)

        # Be polite: Reddit asks for ~1 req/s from unauthenticated clients
        time.sleep(1)

    # ── Comments ──
    for query in keywords:
        logger.info("Reddit public search (comments): %r", query)
        url = f"{_REDDIT_BASE}/search.json"
        params = {"q": query, "sort": "new", "t": "day", "limit": 15, "type": "comment"}
        try:
            resp = http_requests.get(url, headers=_REDDIT_HEADERS, params=params, timeout=15)
            if resp.status_code == 429:
                time.sleep(10)
                resp = http_requests.get(url, headers=_REDDIT_HEADERS, params=params, timeout=15)
            resp.raise_for_status()

            for child in resp.json().get("data", {}).get("children", []):
                comment = child.get("data", {})
                created = datetime.fromtimestamp(comment.get("created_utc", 0), tz=timezone.utc)
                if created < cutoff:
                    continue
                body = comment.get("body", "")[:2000]
                if not body:
                    continue
                yield {
                    "platform": "reddit",
                    "dedup_key": f"reddit:{comment.get('id', '')}",
                    "source_url": f"https://reddit.com{comment.get('permalink', '')}",
                    "author": comment.get("author", "[deleted]"),
                    "text_snippet": body,
                }
        except Exception as exc:
            logger.error("Reddit comment fetch failed for %r: %s", query, exc)

        time.sleep(1)


# ── X (Twitter) — OPTIONAL ────────────────────────────────────────────────────

_X_SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"


def fetch_x(keywords: list[str], lookback_hours: int = 26) -> Generator[dict, None, None]:
    """
    Yield candidate dicts from X v2 recent-search.
    If credentials are absent or the endpoint returns a non-200, logs clearly
    and yields nothing — the poll command continues on Reddit alone.
    """
    bearer = settings.X_BEARER_TOKEN
    if not bearer:
        logger.info("X_BEARER_TOKEN not set — skipping X fetch.")
        return

    headers = {"Authorization": f"Bearer {bearer}"}
    start_time = (
        datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    for query in keywords:
        params = {
            "query": f"{query} -is:retweet lang:en",
            "max_results": 20,
            "start_time": start_time,
            "tweet.fields": "author_id,created_at,text",
            "expansions": "author_id",
            "user.fields": "username",
        }
        try:
            resp = http_requests.get(_X_SEARCH_URL, headers=headers, params=params, timeout=15)
            if resp.status_code == 403:
                logger.warning(
                    "X API returned 403 — access tier may not include recent-search. "
                    "Skipping X for this run."
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

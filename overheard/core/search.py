"""Serper (google.serper.dev) — simple Google search. One env var: SERPER_API_KEY."""
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)
_SERPER_URL = "https://google.serper.dev/search"


def search_google(query: str, num: int = 10) -> list[dict]:
    """Return organic results: [{title, link, snippet, ...}, ...]."""
    key = settings.SERPER_API_KEY
    if not key:
        logger.warning("SERPER_API_KEY not set — returning no results.")
        return []
    resp = requests.post(
        _SERPER_URL,
        headers={"X-API-KEY": key, "Content-Type": "application/json"},
        json={"q": query, "num": num},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("organic", [])
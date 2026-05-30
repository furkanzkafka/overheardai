"""
Claude-powered helpers:
  - generate_rubric_and_keywords: called once at onboarding
  - score_item: called per candidate during the poll
"""
import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


def _client():
    import anthropic
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)


def generate_rubric_and_keywords(url: str, page_text: str) -> tuple[str, list[str]]:
    """
    Given a site URL and its text content, return (rubric, keywords).
    rubric: multi-paragraph string describing relevance criteria.
    keywords: list of search strings for Reddit/X.
    """
    client = _client()
    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1500,
        messages=[{
            "role": "user",
            "content": (
                "You are helping a small team monitor social media for genuine help-seeking "
                "conversations related to their product or service.\n\n"
                f"Given this website URL and content excerpt, generate:\n"
                "1. A relevance rubric describing: the core problem the site solves and who has it; "
                "the intent signals that indicate a genuine need (not just curiosity); and two or three "
                "examples of posts that look relevant but aren't.\n"
                "2. A list of 10-14 concise search queries/keywords optimised for Reddit and X searches.\n\n"
                f"Website URL: {url}\n"
                f"Content (excerpt, up to 10 000 chars):\n{page_text}\n\n"
                "Respond with JSON ONLY, no markdown, in this exact shape:\n"
                '{"rubric": "...", "keywords": ["...", "..."]}'
            ),
        }],
    )
    raw = response.content[0].text.strip()
    data = json.loads(raw)
    return data["rubric"], data["keywords"]


def score_item(text_snippet: str, rubric: str) -> dict:
    """
    Score a single candidate post/comment against the rubric.
    Returns a dict with: score, why_relevant, what_theyre_asking, suggested_angle.
    """
    client = _client()
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": (
                "Score the following social media post against the relevance rubric below.\n\n"
                f"RUBRIC:\n{rubric}\n\n"
                f"POST:\n{text_snippet}\n\n"
                "Return JSON ONLY (no markdown) with these keys:\n"
                '{"score": 0-100, "why_relevant": "...", "what_theyre_asking": "...", "suggested_angle": "..."}\n'
                "score is 0 if completely irrelevant, 100 if a perfect match.\n"
                "why_relevant: one sentence on why this person's situation matches the rubric.\n"
                "what_theyre_asking: one sentence summarising what help they want.\n"
                "suggested_angle: one sentence on how the team could genuinely help."
            ),
        }],
    )
    raw = response.content[0].text.strip()
    return json.loads(raw)

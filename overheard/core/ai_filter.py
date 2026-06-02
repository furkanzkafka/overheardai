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

def _parse_json(raw: str) -> dict:
    """Pull the JSON object out even if the model wraps it in ```fences``` or adds stray text."""
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end > start:
            return json.loads(raw[start:end + 1])
        raise

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
    data = _parse_json(raw)
    return data["rubric"], data["keywords"]


def score_item(text_snippet: str, rubric: str, subreddit: str = "") -> dict:
    """Score one Reddit post (title + snippet) against the rubric; North America only."""
    client = _client()
    sub_line = f"SUBREDDIT: r/{subreddit}\n" if subreddit else ""
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=500,
        messages=[{
            "role": "user",
            "content": (
                "Score the following Reddit post against the relevance rubric below.\n\n"
                f"RUBRIC:\n{rubric}\n\n"
                "HARD LOCATION RULE: this product serves North America (US & Canada) only. "
                "If the post is clearly about somewhere else (India, UK, Australia, etc.), score it 0 "
                "no matter how well the topic fits. Use the subreddit and the text as location cues.\n\n"
                f"{sub_line}"
                f"POST:\n{text_snippet}\n\n"
                "Return JSON ONLY (no markdown, no preamble) with these keys:\n"
                '{"score": 0-100, "why_relevant": "...", "what_theyre_asking": "...", "suggested_angle": "..."}\n'
                "score is 0 if irrelevant or outside North America, 100 if a perfect match.\n"
                "why_relevant: one sentence on why this person's situation matches the rubric.\n"
                "what_theyre_asking: one sentence on what help they want.\n"
                "suggested_angle: one sentence on how the team could genuinely help."
            ),
        }],
    )
    return _parse_json(response.content[0].text.strip())

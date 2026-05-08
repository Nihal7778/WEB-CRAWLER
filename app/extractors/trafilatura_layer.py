"""
Trafilatura extraction layer — primary content extractor.

Trafilatura uses ML-trained heuristics to strip nav/footer/ads and pull
the main article body. It also extracts title, author, and publication
date when available. This is our highest-quality source for body text.

Returns a dict with whatever fields it could extract — None for misses.
Never raises on bad input; logs error and returns empty dict.
"""

from typing import Optional, TypedDict

import trafilatura
from trafilatura.settings import use_config


class TrafilaturaResult(TypedDict, total=False):
    title: Optional[str]
    description: Optional[str]
    author: Optional[str]
    published_date: Optional[str]
    language: Optional[str]
    body_text: str


# Configure trafilatura: faster, less noisy. Disable signal-based timeouts
# (don't work in worker threads / async contexts).
_CONFIG = use_config()
_CONFIG.set("DEFAULT", "EXTRACTION_TIMEOUT", "0")


def extract(html: str, url: Optional[str] = None) -> TrafilaturaResult:
    """Extract title, body, and metadata using trafilatura.

    Args:
        html: Full HTML document as a string.
        url: Optional source URL — helps trafilatura resolve relative links.

    Returns:
        Dict with extracted fields. Missing fields are simply absent
        from the dict (caller must use .get()).
    """
    if not html:
        return {}

    result: TrafilaturaResult = {}

    # Pull structured metadata (title, author, date, etc.)
    try:
        meta = trafilatura.extract_metadata(html, default_url=url)
        if meta:
            md = meta.as_dict()
            result["title"] = md.get("title") or None
            result["description"] = md.get("description") or None
            result["author"] = md.get("author") or None
            result["published_date"] = md.get("date") or None
            # trafilatura returns 2-letter language codes (e.g. "en")
            result["language"] = md.get("language") or None
    except Exception as e:
        # Don't crash — just log and continue. Other layers may fill in.
        result["_meta_error"] = str(e)  # type: ignore[typeddict-unknown-key]

    # Pull cleaned body text. Disable comments/tables to keep it focused.
    try:
        body = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=False,
            no_fallback=False,        # let trafilatura's fallback run
            favor_precision=True,     # prefer cleaner text over more text
            config=_CONFIG,
        )
        result["body_text"] = body or ""
    except Exception as e:
        result["body_text"] = ""
        result["_body_error"] = str(e)  # type: ignore[typeddict-unknown-key]

    return result
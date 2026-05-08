"""
Extruct extraction layer — structured data.

Extruct pulls explicit metadata the page author declared:
- OpenGraph (og:* meta tags)
- Twitter Cards (twitter:* meta tags)
- JSON-LD (<script type="application/ld+json">)
- Microdata, RDFa (we ignore these — rarely useful)

These signals are the most reliable because they're declarations,
not inferences. og:type="product" beats any heuristic.
"""

from typing import Any, Optional, TypedDict

import extruct


class ExtructResult(TypedDict, total=False):
    og_data: dict[str, Any]
    twitter_data: dict[str, Any]
    json_ld: list[dict[str, Any]]


def extract(html: str, url: Optional[str] = None) -> ExtructResult:
    """Extract OpenGraph, Twitter Card, and JSON-LD data.

    Args:
        html: Full HTML document as a string.
        url: Base URL for resolving relative references inside structured data.

    Returns:
        Dict with og_data, twitter_data, json_ld. Empty containers if
        nothing was found or extraction failed.
    """
    if not html:
        return {"og_data": {}, "twitter_data": {}, "json_ld": []}

    result: ExtructResult = {
        "og_data": {},
        "twitter_data": {},
        "json_ld": [],
    }

    try:
        data = extruct.extract(
            html,
            base_url=url,
            syntaxes=["opengraph", "json-ld", "microdata"],
            uniform=True,  # normalize output shape across syntaxes
        )
    except Exception:
        # Extruct can throw on malformed HTML/JSON-LD; degrade gracefully.
        return result

    # OpenGraph — extruct returns a list of dicts (one per og: namespace).
    # Flatten into a single dict; later entries win on conflicts.
    og_list = data.get("opengraph") or []
    flat_og: dict[str, Any] = {}
    for og_block in og_list:
        if isinstance(og_block, dict):
            for k, v in og_block.items():
                if k == "@context":
                    continue
                flat_og[k] = v
    result["og_data"] = flat_og

    # Twitter Cards — extruct doesn't have a dedicated parser, but Twitter
    # tags appear in OG output under "twitter:*" keys. Split them out.
    twitter_data = {k: v for k, v in flat_og.items() if k.startswith("twitter:")}
    result["twitter_data"] = twitter_data

    # JSON-LD — list of structured data blocks (Article, Product, etc.).
    json_ld = data.get("json-ld") or []
    if isinstance(json_ld, list):
        result["json_ld"] = [b for b in json_ld if isinstance(b, dict)]

    return result
"""
Heuristic classifier — fast deterministic short-circuit.

Looks at URL patterns and structured metadata for unambiguous signals
that let us skip the expensive ML stages. Roughly 30-40% of pages
match a heuristic and never need embedding/LLM.

Returns None if no rule matches; caller falls through to embedding.
"""

from typing import Any, Optional
from urllib.parse import urlparse

from app.schemas import Topic, TopicSource


# URL pattern → category. Order matters — first match wins.
# Patterns are checked as substrings against the URL path.
URL_PATTERNS: list[tuple[str, str, float]] = [
    # (url_substring, category, confidence)
    ("/dp/", "Ecommerce > Product Page", 0.95),
    ("/product/", "Ecommerce > Product Page", 0.92),
    ("/p/", "Ecommerce > Product Page", 0.85),
    ("/products/", "Ecommerce > Product Page", 0.92),
    ("/listing/", "Ecommerce > Product Page", 0.85),
    ("/shop/", "Ecommerce > Product Page", 0.80),
]

# Domain → category. For well-known sites with consistent content type.
DOMAIN_PATTERNS: dict[str, tuple[str, float]] = {
    "amazon.com": ("Ecommerce > Product Page", 0.95),
    "amazon.co.uk": ("Ecommerce > Product Page", 0.95),
    "ebay.com": ("Ecommerce > Product Page", 0.95),
    "walmart.com": ("Ecommerce > Product Page", 0.92),
    "bestbuy.com": ("Ecommerce > Product Page", 0.92),
    "etsy.com": ("Ecommerce > Product Page", 0.92),
}

# OpenGraph og:type → category. Strongest signal — page author declared it.
OG_TYPE_PATTERNS: dict[str, tuple[str, float]] = {
    "product": ("Ecommerce > Product Page", 0.95),
    "product.item": ("Ecommerce > Product Page", 0.95),
    "article": ("News > Technology", 0.40),  # weak — needs further classification, but flags it as article
    "video.movie": ("Entertainment > Movies", 0.90),
    "video.tv_show": ("Entertainment > TV and Streaming", 0.90),
    "music.song": ("Entertainment > Music", 0.90),
    "music.album": ("Entertainment > Music", 0.90),
    "book": ("Education > Reference", 0.70),
}

# Schema.org @type from JSON-LD → category.
SCHEMA_TYPE_PATTERNS: dict[str, tuple[str, float]] = {
    "Product": ("Ecommerce > Product Page", 0.95),
    "Recipe": ("Lifestyle > Food and Cooking", 0.92),
    "Movie": ("Entertainment > Movies", 0.90),
    "MusicAlbum": ("Entertainment > Music", 0.90),
    "VideoGame": ("Entertainment > Gaming", 0.90),
    "MedicalCondition": ("Health > Medical", 0.92),
    "MedicalProcedure": ("Health > Medical", 0.92),
}


def _normalize_domain(host: str) -> str:
    """Drop 'www.' and lowercase."""
    host = host.lower()
    return host[4:] if host.startswith("www.") else host


def classify(
    url: str,
    og_data: Optional[dict[str, Any]] = None,
    json_ld: Optional[list[dict[str, Any]]] = None,
) -> Optional[Topic]:
    """Return a Topic if any heuristic matches; None otherwise.

    Checks in priority order:
    1. og:type meta tag (strongest — page author declared)
    2. JSON-LD @type
    3. Domain known pattern (e.g. amazon.com)
    4. URL path pattern (e.g. /dp/, /product/)
    """
    og_data = og_data or {}
    json_ld = json_ld or []

    # 1. og:type
    og_type = og_data.get("og:type")
    if isinstance(og_type, str):
        og_type_lower = og_type.lower()
        if og_type_lower in OG_TYPE_PATTERNS:
            label, conf = OG_TYPE_PATTERNS[og_type_lower]
            # Skip "article" — it's too weak to be a final answer.
            if og_type_lower != "article":
                return Topic(topic=label, confidence=conf, source=TopicSource.HEURISTIC)

    # 2. JSON-LD @type
    for block in json_ld:
        block_type = block.get("@type")
        if isinstance(block_type, list):
            block_type = block_type[0] if block_type else None
        if isinstance(block_type, str) and block_type in SCHEMA_TYPE_PATTERNS:
            label, conf = SCHEMA_TYPE_PATTERNS[block_type]
            return Topic(topic=label, confidence=conf, source=TopicSource.HEURISTIC)

    # 3. Domain match
    try:
        parsed = urlparse(url)
        host = _normalize_domain(parsed.netloc)
        if host in DOMAIN_PATTERNS:
            label, conf = DOMAIN_PATTERNS[host]
            return Topic(topic=label, confidence=conf, source=TopicSource.HEURISTIC)
    except Exception:
        pass

    # 4. URL path patterns
    url_lower = url.lower()
    for pattern, label, conf in URL_PATTERNS:
        if pattern in url_lower:
            return Topic(topic=label, confidence=conf, source=TopicSource.HEURISTIC)

    return None
"""
Classifier orchestrator.

Three-stage classification pipeline:
1. Heuristic: URL patterns + og:type + JSON-LD. Short-circuit on match.
2. KeyBERT: Extract top-N keyword topics from body text.
3. Embedding: Cosine similarity against pre-embedded IAB taxonomy.

The classifier always returns at least keyword topics (even on heuristic
match) because keywords are useful regardless of category. The category
label comes from heuristic OR embedding — never both.
"""

from typing import Any, Optional

from app.classifiers import (
    embedding_classifier,
    heuristic,
    keybert_topics,
)
from app.schemas import Topic


def classify_page(
    url: str,
    title: Optional[str],
    description: Optional[str],
    body_text: str,
    og_data: Optional[dict[str, Any]] = None,
    json_ld: Optional[list[dict[str, Any]]] = None,
) -> tuple[list[Topic], list[str]]:
    """Run the full classification pipeline.

    Args:
        url: The page URL (used by heuristic).
        title: Page title.
        description: Page description.
        body_text: Cleaned body text (from extractor).
        og_data: OpenGraph dict (from extractor).
        json_ld: JSON-LD blocks (from extractor).

    Returns:
        (topics, errors) — topics is a list of Topic objects, errors is
        a list of non-fatal issues.
    """
    errors: list[str] = []
    all_topics: list[Topic] = []

    # Stage 1: Heuristic. If matched, we have a category but still want keywords.
    heuristic_topic = heuristic.classify(url, og_data=og_data, json_ld=json_ld)
    if heuristic_topic:
        all_topics.append(heuristic_topic)

    # Stage 2: KeyBERT keyword topics. Always run — useful free-form tags.
    try:
        keyword_topics = keybert_topics.extract_topics(title, description, body_text)
        all_topics.extend(keyword_topics)
    except Exception as e:
        errors.append(f"keybert: {e}")
        keyword_topics = []

    # Stage 3: Embedding similarity classifier. Skip if heuristic already matched
    # — saves ~50ms per ecommerce/product page.
    if heuristic_topic is None:
        try:
            embedding_topics = embedding_classifier.classify(
                title, description, keyword_topics=keyword_topics
            )
            all_topics.extend(embedding_topics)
        except Exception as e:
            errors.append(f"embedding: {e}")

    return all_topics, errors
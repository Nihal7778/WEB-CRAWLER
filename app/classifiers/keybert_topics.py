"""
KeyBERT topic extractor.

Pulls top-N semantically meaningful keywords from page body text.
These become the "topics" portion of the response (free-form, not
mapped to a taxonomy).

Uses sentence-transformers under the hood; the model is loaded once
at module import and reused across requests.
"""

from functools import lru_cache
from typing import Optional

from keybert import KeyBERT

from app.schemas import Topic, TopicSource

# Model name — same model is reused by embedding_classifier.py.
# Apache-2.0 licensed, 384-dim embeddings, ~90MB on disk.
MODEL_NAME = "all-MiniLM-L6-v2"

# Truncate body before embedding. KeyBERT runtime grows with token count.
# 5000 chars covers the meaningful content of most articles without lag.
MAX_BODY_CHARS = 5_000

# Number of keywords to return.
TOP_N = 5


@lru_cache(maxsize=1)
def _get_model() -> KeyBERT:
    """Lazy-init the KeyBERT model. Cached so re-imports don't reload."""
    return KeyBERT(model=MODEL_NAME)


def extract_topics(
    title: Optional[str],
    description: Optional[str],
    body_text: str,
) -> list[Topic]:
    """Extract top-N keyphrases as Topics.

    Args:
        title: Page title (boosts relevance — title words tend to be on-topic).
        description: Page description.
        body_text: Cleaned main body text from extractor.

    Returns:
        List of Topic objects with source=KEYWORD. Empty list if no
        usable text or extraction fails.
    """
    # Combine title + description + body. Title/desc have signal density;
    # body provides volume. Truncate to keep latency bounded.
    parts = [title or "", description or "", body_text or ""]
    combined = " ".join(p for p in parts if p)
    combined = combined[:MAX_BODY_CHARS].strip()

    if len(combined) < 50:
        return []

    try:
        model = _get_model()
        # Extract 1-2 word phrases. MMR diversifies results so we don't
        # get five variations of the same word.
        raw = model.extract_keywords(
            combined,
            keyphrase_ngram_range=(1, 2),
            stop_words="english",
            use_mmr=True,
            diversity=0.5,
            top_n=TOP_N,
        )
    except Exception:
        return []

    # KeyBERT returns [(phrase, score), ...]. Score is cosine similarity (0-1).
    return [
        Topic(topic=phrase, confidence=float(score), source=TopicSource.KEYWORD)
        for phrase, score in raw
        if phrase  # filter empties
    ]
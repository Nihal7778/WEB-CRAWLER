"""
Embedding-similarity classifier.

Classifies the page into one of the IAB taxonomy labels by:
1. Pre-embedding the taxonomy descriptions once at startup.
2. Embedding the page (title + description + keywords) at request time.
3. Returning top-K labels by cosine similarity.

Reuses the same all-MiniLM-L6-v2 model that KeyBERT uses, so we ship
one model file. ~10-50ms per page on CPU.
"""

from functools import lru_cache
from typing import Optional

import numpy as np
from sentence_transformers import SentenceTransformer

from app.classifiers.taxonomy import TAXONOMY
from app.schemas import Topic, TopicSource

MODEL_NAME = "all-MiniLM-L6-v2"
TOP_K = 3
MIN_CONFIDENCE = 0.30  # below this, we don't return the label


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    """Lazy-load the embedder. Cached for reuse across calls."""
    return SentenceTransformer(MODEL_NAME)


@lru_cache(maxsize=1)
def _get_taxonomy_embeddings() -> tuple[list[str], np.ndarray]:
    """Pre-embed the taxonomy descriptions once.

    Returns:
        (labels, embeddings_matrix) — labels[i] corresponds to embeddings_matrix[i].
        Embeddings are L2-normalized so cosine sim = dot product.
    """
    model = _get_model()
    labels = [label for label, _ in TAXONOMY]
    descriptions = [desc for _, desc in TAXONOMY]
    embeddings = model.encode(
        descriptions,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return labels, embeddings


def warmup() -> None:
    """Force model + taxonomy embedding at startup, not at first request.

    Call this from FastAPI's startup event so the first /crawl call
    isn't blocked by ~3s of model loading + taxonomy encoding.
    """
    _get_model()
    _get_taxonomy_embeddings()


def classify(
    title: Optional[str],
    description: Optional[str],
    keyword_topics: Optional[list[Topic]] = None,
) -> list[Topic]:
    """Return top-K taxonomy labels by cosine similarity.

    Args:
        title: Page title.
        description: Page description.
        keyword_topics: Optional list of KeyBERT topics to enrich the query.
                        Their phrases are concatenated into the embedding input.

    Returns:
        List of Topic objects with source=EMBEDDING, sorted by confidence
        descending. Empty list if nothing usable to embed or all scores
        below MIN_CONFIDENCE.
    """
    # Build the query string from whatever signals we have.
    parts: list[str] = []
    if title:
        parts.append(title)
    if description:
        parts.append(description)
    if keyword_topics:
        parts.extend(t.topic for t in keyword_topics)

    query = " ".join(parts).strip()
    if not query:
        return []

    try:
        model = _get_model()
        labels, taxonomy_embeddings = _get_taxonomy_embeddings()

        # Embed the query (normalized so cosine = dot product).
        query_emb = model.encode(
            [query],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )[0]

        # Cosine similarity = matrix-vector dot product.
        scores = taxonomy_embeddings @ query_emb  # shape: (N_labels,)

        # Top-K indices, descending.
        top_idx = np.argsort(-scores)[:TOP_K]
    except Exception:
        return []

    results: list[Topic] = []
    for idx in top_idx:
        score = float(scores[idx])
        if score < MIN_CONFIDENCE:
            continue
        results.append(
            Topic(
                topic=labels[idx],
                confidence=round(score, 3),
                source=TopicSource.EMBEDDING,
            )
        )
    return results
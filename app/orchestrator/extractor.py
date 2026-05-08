"""
Extractor orchestrator.

Runs all extraction layers in sequence and merges their outputs into
the unified PageMetadata + PageContent models.

Layers run in order: trafilatura → extruct → bs4. Each layer is independent
and degrades gracefully — if one fails or returns nothing, the others fill
the gaps. The merger applies precedence rules to combine results.
"""

from typing import Optional

from app.extractors import bs4_layer, extruct_layer, trafilatura_layer
from app.extractors.merger import merge
from app.schemas import PageContent, PageMetadata


def extract_page(
    html: str,
    url: Optional[str] = None,
) -> tuple[PageMetadata, PageContent, list[str]]:
    """Run all extraction layers and merge the results.

    Args:
        html: Raw HTML from the fetcher.
        url: Source URL (helps trafilatura/extruct resolve relative refs).

    Returns:
        (metadata, content, errors) — errors is a list of non-fatal issues
        encountered during extraction (empty if everything went smoothly).
    """
    errors: list[str] = []

    if not html:
        errors.append("extractor: empty HTML, nothing to extract")
        return PageMetadata(), PageContent(), errors

    # Layer 1: trafilatura (primary)
    traf = trafilatura_layer.extract(html, url=url)
    if "_meta_error" in traf:
        errors.append(f"trafilatura metadata: {traf['_meta_error']}")
    if "_body_error" in traf:
        errors.append(f"trafilatura body: {traf['_body_error']}")

    # Layer 2: extruct (structured data)
    ext = extruct_layer.extract(html, url=url)

    # Layer 3: bs4 (fallback for misses)
    bs = bs4_layer.extract(html)

    # Merge with precedence rules.
    metadata, content = merge(traf, ext, bs)

    return metadata, content, errors
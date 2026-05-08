"""
Merger — combines outputs from all extraction layers into PageMetadata + PageContent.

Precedence rules (most reliable wins):
- title:          trafilatura > og:title > BS4 <title>
- description:    trafilatura > og:description > BS4 meta description
- author:         trafilatura > json-ld > og:author
- published_date: trafilatura > og:article:published_time > json-ld
- language:       trafilatura > BS4 html[lang]
- canonical_url:  BS4 (trafilatura doesn't extract this)
- body_text:      trafilatura only (others don't produce body text)

The merger is pure — no I/O, no parsing. Just dict combination logic.
This makes it trivially testable.
"""

from typing import Any

from app.schemas import PageContent, PageMetadata


def _first_non_empty(*values: Any) -> Any:
    """Return the first value that is truthy (not None, not empty string)."""
    for v in values:
        if v:
            return v
    return None


def merge(
    trafilatura_result: dict[str, Any],
    extruct_result: dict[str, Any],
    bs4_result: dict[str, Any],
) -> tuple[PageMetadata, PageContent]:
    """Merge layer outputs into the unified Pydantic models.

    Args:
        trafilatura_result: dict from trafilatura_layer.extract()
        extruct_result: dict from extruct_layer.extract()
        bs4_result: dict from bs4_layer.extract()

    Returns:
        (PageMetadata, PageContent) tuple ready to drop into CrawlResponse.
    """
    og = extruct_result.get("og_data", {}) or {}
    twitter = extruct_result.get("twitter_data", {}) or {}
    json_ld = extruct_result.get("json_ld", []) or []

    # Pull commonly-needed fields from JSON-LD if present.
    # JSON-LD authors can be a string, dict, or list — normalize.
    json_ld_author: str | None = None
    json_ld_date: str | None = None
    for block in json_ld:
        if json_ld_author is None:
            author_field = block.get("author")
            if isinstance(author_field, str):
                json_ld_author = author_field
            elif isinstance(author_field, dict):
                json_ld_author = author_field.get("name")
            elif isinstance(author_field, list) and author_field:
                first = author_field[0]
                if isinstance(first, dict):
                    json_ld_author = first.get("name")
                elif isinstance(first, str):
                    json_ld_author = first
        if json_ld_date is None:
            json_ld_date = block.get("datePublished") or block.get("dateCreated")

    metadata = PageMetadata(
        title=_first_non_empty(
            trafilatura_result.get("title"),
            og.get("og:title"),
            bs4_result.get("title"),
        ),
        description=_first_non_empty(
            trafilatura_result.get("description"),
            og.get("og:description"),
            bs4_result.get("description"),
        ),
        author=_first_non_empty(
            trafilatura_result.get("author"),
            json_ld_author,
            og.get("og:author"),
        ),
        published_date=_first_non_empty(
            trafilatura_result.get("published_date"),
            og.get("og:article:published_time"),
            json_ld_date,
        ),
        language=_first_non_empty(
            trafilatura_result.get("language"),
            bs4_result.get("language"),
        ),
        canonical_url=_first_non_empty(
            bs4_result.get("canonical_url"),
            og.get("og:url"),
        ),
        og_data=og,
        twitter_data=twitter,
        json_ld=json_ld,
    )

    body_text = trafilatura_result.get("body_text") or ""
    content = PageContent(
        body_text=body_text,
        word_count=len(body_text.split()) if body_text else 0,
    )

    return metadata, content
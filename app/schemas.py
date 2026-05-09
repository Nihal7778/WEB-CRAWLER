"""
Pydantic schemas — the API contract.

This is the single source of truth for the data shape produced by the
crawler. The same schema is:
- Returned by the FastAPI /crawl endpoint (Phase 3)
- Stored in DynamoDB at billion scale (Part 2 production)
- Served by the read API to clients (Part 2 production)

Schema evolution rule: additive only. Never remove fields, never change
types. New fields get a default value so old records remain valid.
Bump SCHEMA_VERSION when adding fields.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, HttpUrl, field_validator


SCHEMA_VERSION = 1


# Enums — closed sets of valid values


class CrawlStatus(str, Enum):
    """Outcome of a crawl request.

    SUCCESS  — full extraction completed, all stages ran cleanly
    PARTIAL  — fetch worked but content suggests bot/captcha page,
               or one extraction layer failed but others succeeded
    FAILED   — fetch failed entirely (timeout, DNS error, 5xx)
    """
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class TopicSource(str, Enum):
    """Provenance for a classified topic.

    HEURISTIC  — matched URL pattern or og:type rule (cheapest, most reliable)
    EMBEDDING  — MiniLM cosine similarity vs pre-embedded label taxonomy
    KEYWORD    — KeyBERT-extracted phrase (used when no category matched)
    LLM        — fallback LLM call on low-confidence pages (rare)
    """
    HEURISTIC = "heuristic"
    EMBEDDING = "embedding"
    KEYWORD = "keyword"
    LLM = "llm"



# Request model

class CrawlRequest(BaseModel):
    """POST /crawl request body."""
    url: HttpUrl = Field(..., description="Absolute URL to crawl")

    # Optional knobs — sensible defaults for the demo
    include_raw_html: bool = Field(
        False,
        description="Include raw HTML in response (large; off by default)",
    )
    classify: bool = Field(
        True,
        description="Run topic classification (turn off for metadata-only)",
    )


# Sub-models — composed into CrawlResponse

class PageMetadata(BaseModel):
    """Structured metadata extracted from the page.

    All fields optional because real-world pages are inconsistent —
    we surface whatever was extractable and leave the rest as None.
    """
    title: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    published_date: Optional[str] = None  
    language: Optional[str] = None       
    canonical_url: Optional[str] = None

    # Structured data from the page (often richer than meta tags)
    og_data: dict = Field(default_factory=dict, description="OpenGraph properties")
    twitter_data: dict = Field(default_factory=dict, description="Twitter Card properties")
    json_ld: list[dict] = Field(default_factory=list, description="JSON-LD structured data blocks")


class PageContent(BaseModel):
    """Cleaned main content of the page."""
    body_text: str = ""
    word_count: int = 0
    raw_html: Optional[str] = None  # only populated if request.include_raw_html=True

    @field_validator("word_count")
    @classmethod
    def _word_count_non_negative(cls, v: int) -> int:
        return max(0, v)


class Topic(BaseModel):
    """A single classified topic or category.

    `topic` is the human-readable label.
    `confidence` is 0.0–1.0; calibration depends on `source`.
    `source` records which classifier produced this topic (provenance for debugging).
    """
    topic: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    source: TopicSource



# Top-level response model — the contract


class CrawlResponse(BaseModel):
    """Unified response for POST /crawl.

    This shape is the API contract. Downstream consumers (the read API,
    analytics jobs, dashboards) depend on it. Treat field changes as
    breaking and use SCHEMA_VERSION to migrate.
    """
    # Versioning
    schema_version: int = SCHEMA_VERSION

    # Request echoes
    url: str = Field(..., description="Final URL after redirects")
    requested_url: str = Field(..., description="Original URL from the request")

    # Outcome
    status: CrawlStatus
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    fetch_status_code: int = 0  # HTTP status from the fetch (0 if no response)

    # Extracted data
    metadata: PageMetadata = Field(default_factory=PageMetadata)
    content: PageContent = Field(default_factory=PageContent)
    topics: list[Topic] = Field(default_factory=list)

    # Diagnostics
    bot_blocked: bool = Field(
        False,
        description="True if response looked like a captcha/anti-bot page",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Non-fatal issues encountered during processing",
    )
    latency_ms: int = Field(0, ge=0, description="End-to-end processing time")

    model_config = {
        "json_schema_extra": {
            "example": {
                "schema_version": 1,
                "url": "https://blog.rei.com/camp/how-to-introduce-your-indoorsy-friend-to-the-outdoors/",
                "requested_url": "http://blog.rei.com/camp/how-to-introduce-your-indoorsy-friend-to-the-outdoors/",
                "status": "success",
                "fetched_at": "2026-05-07T12:00:00Z",
                "fetch_status_code": 200,
                "metadata": {
                    "title": "How to Introduce Your Indoorsy Friend to the Outdoors",
                    "description": "Tips for sharing your love of the outdoors...",
                    "author": "REI Co-op",
                    "language": "en",
                    "og_data": {"og:type": "article"},
                },
                "content": {
                    "body_text": "If you've been camping for years...",
                    "word_count": 1245,
                },
                "topics": [
                    {"topic": "Outdoor Activities > Camping", "confidence": 0.91, "source": "embedding"},
                    {"topic": "camping", "confidence": 0.87, "source": "keyword"},
                    {"topic": "outdoors", "confidence": 0.82, "source": "keyword"},
                ],
                "bot_blocked": False,
                "errors": [],
                "latency_ms": 612,
            }
        }
    }



# Health check response (used by /health endpoint in Phase 3)

class HealthResponse(BaseModel):
    status: str = "ok"
    schema_version: int = SCHEMA_VERSION
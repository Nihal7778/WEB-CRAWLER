"""
FastAPI application — entry point for the crawler service.

Endpoints:
  GET  /health   — liveness probe (no work; returns service info)
  POST /crawl    — main extraction endpoint

Lifecycle:
  - On startup: configure logging + warm up ML models (loads MiniLM
    once so first request isn't blocked by model download/load).
  - On shutdown: nothing to clean up; httpx clients are per-request.

Pipeline (per /crawl request):
  fetch → bot-detect → extract → classify → assemble CrawlResponse
"""

import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.orchestrator.classifier import classify_page
from app.classifiers import embedding_classifier
from app.config import (
    MAX_BODY_CHARS_RESPONSE,
    SERVICE_NAME,
    SERVICE_VERSION,
)
from app.orchestrator.extractor import extract_page
from app.fetcher import fetch_html
from app.schemas import (
    SCHEMA_VERSION,
    CrawlRequest,
    CrawlResponse,
    CrawlStatus,
    HealthResponse,
)
from app.utils.bot_detection import detect_bot_page
from app.utils.logging import configure_logging, get_logger

logger = get_logger(__name__)



# App lifecycle — warm models at startup to avoid first-request latency spikes. If warmup fails, we log but keep

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: configure logging and warm up the embedder.

    Warming up costs ~3s but avoids that latency on the first request.
    """
    configure_logging()
    logger.info(
        "service starting",
        extra={"service": SERVICE_NAME, "version": SERVICE_VERSION},
    )

    try:
        embedding_classifier.warmup()
        logger.info("embedding model loaded")
    except Exception as e:
        # Don't crash — service still works without classification.
        logger.error("embedding warmup failed", extra={"error": str(e)})

    yield

    logger.info("service shutting down")


app = FastAPI(
    title="BrightEdge Crawler",
    description="URL → metadata + topic classification service",
    version=SERVICE_VERSION,
    lifespan=lifespan,
)

# Permissive CORS — fine for a public demo. Tighten in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)



# endpoints

@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    """Liveness probe. Returns 200 if the service is up."""
    return HealthResponse(status="ok", schema_version=SCHEMA_VERSION)


@app.post("/crawl", response_model=CrawlResponse, tags=["crawler"])
async def crawl(request: CrawlRequest) -> CrawlResponse:
    """Fetch a URL, extract metadata, classify topics. Returns CrawlResponse.

    The endpoint never throws on content-level failures — it returns a
    structured response with `status: "failed"` or `"partial"` instead.
    Only protocol-level issues (e.g. invalid URL format) raise HTTPException.
    """
    started = time.monotonic()
    requested_url = str(request.url)

    logger.info("crawl start", extra={"url": requested_url})

    # ─── Stage 1: Fetch ───────────────────────────────────────
    fetch_result = fetch_html(requested_url)

    if not fetch_result.ok:
        # Hard fetch failure — return a structured failed response.
        elapsed_ms = int((time.monotonic() - started) * 1000)
        logger.warning(
            "crawl failed at fetch",
            extra={"url": requested_url, "error": fetch_result.error},
        )
        return CrawlResponse(
            url=fetch_result.url,
            requested_url=requested_url,
            status=CrawlStatus.FAILED,
            fetched_at=datetime.now(timezone.utc),
            fetch_status_code=fetch_result.status_code,
            errors=[f"fetch: {fetch_result.error or 'unknown error'}"],
            latency_ms=elapsed_ms,
        )

    html = fetch_result.html
    final_url = fetch_result.url
    fetch_status_code = fetch_result.status_code

    # Stage 2: Bot detection
    bot_check = detect_bot_page(html, status_code=fetch_status_code)

    # Stage 3: Extract
    metadata, content, ext_errors = extract_page(html, url=final_url)

    # ─── Stage 4: Classify (skip if request opted out) ────────
    topics = []
    cls_errors: list[str] = []
    if request.classify and not bot_check.is_bot_page:
        topics, cls_errors = classify_page(
            url=final_url,
            title=metadata.title,
            description=metadata.description,
            body_text=content.body_text,
            og_data=metadata.og_data,
            json_ld=metadata.json_ld,
        )

    # ─── Stage 5: Assemble response ───────────────────────────
    # Determine status from what actually happened.
    if bot_check.is_bot_page:
        status = CrawlStatus.PARTIAL
    elif ext_errors and not metadata.title:
        # Couldn't even pull a title — treat as partial.
        status = CrawlStatus.PARTIAL
    else:
        status = CrawlStatus.SUCCESS

    # Truncate body for response payload (full text was already used internally).
    if content.body_text and len(content.body_text) > MAX_BODY_CHARS_RESPONSE:
        content.body_text = content.body_text[:MAX_BODY_CHARS_RESPONSE] + "..."

    # Optional raw HTML inclusion.
    if request.include_raw_html:
        content.raw_html = html

    # Collect non-fatal issues from all stages.
    errors = list(ext_errors) + list(cls_errors)
    if bot_check.is_bot_page and bot_check.reason:
        errors.append(f"bot detection: {bot_check.reason}")

    elapsed_ms = int((time.monotonic() - started) * 1000)

    logger.info(
        "crawl complete",
        extra={
            "url": final_url,
            "status": status.value,
            "topics_count": len(topics),
            "latency_ms": elapsed_ms,
            "bot_blocked": bot_check.is_bot_page,
        },
    )

    return CrawlResponse(
        url=final_url,
        requested_url=requested_url,
        status=status,
        fetched_at=datetime.now(timezone.utc),
        fetch_status_code=fetch_status_code,
        metadata=metadata,
        content=content,
        topics=topics,
        bot_blocked=bot_check.is_bot_page,
        errors=errors,
        latency_ms=elapsed_ms,
    )
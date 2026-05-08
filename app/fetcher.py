"""
Phase 1: Network layer.

Fetches raw HTML from a URL with realistic browser headers to avoid
basic anti-bot detection (Amazon, Cloudflare, etc.).

Design notes:
- Sync httpx for Phase 1
- UA rotation across realistic Chrome/Firefox/Safari strings
- Full header set — anti-bot systems check header *combinations*, not just UA
- Returns final URL (post-redirect) because Amazon redirects through tracking
- Returns partial result on failure rather than raising — caller decides
"""

import random
from dataclasses import dataclass
from typing import Optional

import httpx

# realistic UAs — rotated per request. Keep recent (2024+) to avoid
# detection of stale UA strings used by old scrapers.
USER_AGENTS = [
    # chrome on windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # chrome on mac OS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
    "Gecko/20100101 Firefox/121.0",
    # safari on mac OS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]

# Timeout config: separate connect vs read because slow servers shouldn't
# stall a worker. Connect timeout shorter than read.
DEFAULT_TIMEOUT = httpx.Timeout(connect=10.0, read=15.0, write=10.0, pool=5.0)
DEFAULT_MAX_REDIRECTS = 5


@dataclass
class FetchResult:
    """Container for fetch output. Avoids returning bare tuples."""
    url: str                 # final url after redirects
    status_code: int         # http status
    html: str                # response body (may be empty on failure)
    content_type: str        # from content type header
    error: Optional[str]     # only on failure
    ok: bool                 # convenience: true if 2xx and html non empty


def _build_headers() -> dict:
    """
    Realistic header set matching what a real browser sends.

    Anti-bot systems fingerprint header combinations + ordering.
    Missing common headers (Accept-Language, DNT) is a strong bot signal.
    """
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }


def fetch_html(
    url: str,
    timeout: httpx.Timeout = DEFAULT_TIMEOUT,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
) -> FetchResult:
    """
    Fetch raw HTML from a URL.

    Returns FetchResult with `ok=True` only on 2xx + non-empty HTML.
    On any failure, returns FetchResult with `ok=False` and `error` populated
    instead of raising — caller decides how to handle.

    Args:
        url: Absolute URL to fetch (must include scheme).
        timeout: httpx Timeout config.
        max_redirects: Cap on redirect chain length.

    Returns:
        FetchResult
    """
    headers = _build_headers()

    try:
        with httpx.Client(
            headers=headers,
            timeout=timeout,
            follow_redirects=True,
            max_redirects=max_redirects,
            http2=False,  # keep simple for phase 1
        ) as client:
            response = client.get(url)

        return FetchResult(
            url=str(response.url),
            status_code=response.status_code,
            html=response.text,
            content_type=response.headers.get("content-type", ""),
            error=None,
            ok=(200 <= response.status_code < 300 and bool(response.text)),
        )

    except httpx.TimeoutException as e:
        return FetchResult(
            url=url, status_code=0, html="", content_type="",
            error=f"Timeout: {e}", ok=False,
        )
    except httpx.TooManyRedirects as e:
        return FetchResult(
            url=url, status_code=0, html="", content_type="",
            error=f"Redirect loop: {e}", ok=False,
        )
    except httpx.RequestError as e:
        # covers dns failures, connection refused, ssl errors, etc.
        return FetchResult(
            url=url, status_code=0, html="", content_type="",
            error=f"Request error: {type(e).__name__}: {e}", ok=False,
        )
    except Exception as e:
        # belt-and-suspenders catch-all so the worker never crashes.
        return FetchResult(
            url=url, status_code=0, html="", content_type="",
            error=f"Unexpected error: {type(e).__name__}: {e}", ok=False,
        )
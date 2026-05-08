"""
Bot/captcha page detection.

A successful HTTP 200 doesn't mean we got real content. Sites like Amazon,
Cloudflare-protected pages, and Akamai-protected pages return 200 with an
anti-bot challenge page in the body.

This module inspects fetched HTML for signals that suggest a bot page:
- Suspiciously small response for a content-rich URL
- Known anti-bot phrases ("verify you are human", "automated access", etc.)
- Known anti-bot page titles ("Robot Check", "Just a moment...", etc.)

We don't fail the request when this triggers — we set a flag and continue.
Partial metadata may still be extractable from the bot page (page title
sometimes leaks the original product name).
"""

from dataclasses import dataclass
from typing import Optional


# Threshold below which a response is "suspiciously small" for a content page.
# Real article/product pages are typically 50KB+. Bot pages are usually <15KB.
SMALL_RESPONSE_THRESHOLD = 15_000

# Phrases that strongly indicate an anti-bot challenge.
# Lowercased; we lowercase the HTML before matching.
BOT_PHRASES = (
    "verify you are human",
    "verify you're human",
    "are you a robot",
    "are you a human",
    "automated access",
    "please complete the captcha",
    "captcha verification",
    "solve the captcha",
    "just a moment",                       # Cloudflare
    "checking your browser",               # Cloudflare
    "enable javascript and cookies",       # Cloudflare
    "request unsuccessful",                # Akamai
    "access denied",
    "discuss automated access",            # Amazon
    "to discuss automated access to amazon",
    "robot check",                          # Amazon
    "sorry, we just need to make sure",    # Amazon
    "pardon our interruption",             # Distil/Imperva
    "press and hold",                      # PerimeterX
    "blocked by",
)

# Title patterns that indicate a bot page even when body checks miss.
BOT_TITLE_PATTERNS = (
    "robot check",
    "just a moment",
    "access denied",
    "attention required",  # Cloudflare
    "captcha",
    "are you human",
)


@dataclass
class BotDetectionResult:
    """Outcome of bot-page detection."""
    is_bot_page: bool
    reason: Optional[str] = None  # human-readable why, populated only if is_bot_page=True


def detect_bot_page(
    html: str,
    status_code: int = 200,
    title: Optional[str] = None,
) -> BotDetectionResult:
    """Heuristically determine if a response is an anti-bot/captcha page.

    Args:
        html: The full response body (HTML text).
        status_code: HTTP status code from the fetch.
        title: Optional page title if already extracted (cheaper to pass it in
               than re-parse here).

    Returns:
        BotDetectionResult with is_bot_page True if any signal triggers.

    Design notes:
        Order matters — we check cheap signals first (size, status code)
        before scanning the HTML body. Body scan is the expensive step.
    """
    # Empty body — not a bot page, just a failed fetch.
    if not html:
        return BotDetectionResult(is_bot_page=False)

    # 503 Service Unavailable is a common anti-bot response.
    # Combined with a small body, very high confidence it's a challenge page.
    if status_code == 503 and len(html) < SMALL_RESPONSE_THRESHOLD:
        return BotDetectionResult(
            is_bot_page=True,
            reason=f"503 with small body ({len(html)} bytes)",
        )

    # Title check — fastest and most reliable when present.
    if title:
        title_lower = title.lower()
        for pattern in BOT_TITLE_PATTERNS:
            if pattern in title_lower:
                return BotDetectionResult(
                    is_bot_page=True,
                    reason=f"bot title pattern: '{pattern}'",
                )

    # Body phrase scan — lowercase once, scan all phrases.
    # We only scan the first 50KB to keep this O(constant) on huge pages.
    html_sample = html[:50_000].lower()
    for phrase in BOT_PHRASES:
        if phrase in html_sample:
            return BotDetectionResult(
                is_bot_page=True,
                reason=f"bot phrase: '{phrase}'",
            )

    # Suspiciously small response with no other signals — soft indicator.
    # We flag it as a bot page only if the response is *very* small.
    # Anything >5KB without a phrase match is probably a thin but real page
    # (404 page, redirect landing page, etc.) — don't false-positive on those.
    if len(html) < 5_000:
        return BotDetectionResult(
            is_bot_page=True,
            reason=f"response too small ({len(html)} bytes)",
        )

    return BotDetectionResult(is_bot_page=False)
"""
BeautifulSoup fallback layer — fills meta tags trafilatura missed.

This runs last as a safety net. Common cases where it helps:
- Sites with non-standard <meta> tags trafilatura's metadata parser missed
- Pages where trafilatura crashed but BS4 can still parse
- Canonical URL detection (trafilatura sometimes misses this)
- Twitter-specific meta tags not caught by extruct

Uses lxml parser — 10x faster than the default html.parser.
"""

from typing import Optional, TypedDict

from bs4 import BeautifulSoup


class BS4Result(TypedDict, total=False):
    title: Optional[str]
    description: Optional[str]
    canonical_url: Optional[str]
    language: Optional[str]


def extract(html: str) -> BS4Result:
    """Pull commonly-missed meta tags via BeautifulSoup.

    Args:
        html: Full HTML document as a string.

    Returns:
        Dict with whatever was found. Empty dict on parse failure.
    """
    if not html:
        return {}

    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:
        return {}

    result: BS4Result = {}

    # <title>
    if soup.title and soup.title.string:
        result["title"] = soup.title.string.strip()

    # <meta name="description">
    desc_tag = soup.find("meta", attrs={"name": "description"})
    if desc_tag and desc_tag.get("content"):
        result["description"] = desc_tag["content"].strip()

    # <link rel="canonical">
    canonical_tag = soup.find("link", attrs={"rel": "canonical"})
    if canonical_tag and canonical_tag.get("href"):
        result["canonical_url"] = canonical_tag["href"].strip()

    # <html lang="en">
    html_tag = soup.find("html")
    if html_tag and html_tag.get("lang"):
        result["language"] = html_tag["lang"].strip().split("-")[0].lower()

    return result
"""
One-time: save fetched HTML to tests/fixtures/ for offline testing in Phase 2.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.fetcher import fetch_html

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

TARGETS = {
    "amazon_toaster.html": (
        "http://www.amazon.com/Cuisinart-CPT-122-Compact-2-SliceToaster/dp/"
        "B009GQ034C/ref=sr_1_1?s=kitchen&ie=UTF8&qid=1431620315&sr=1-1"
        "&keywords=toaster"
    ),
    "rei_blog.html": (
        "http://blog.rei.com/camp/how-to-introduce-your-indoorsy-friend-to-"
        "the-outdoors/"
    ),
    "cnn_article.html": (
        "https://www.cnn.com/2025/09/23/tech/google-study-90-percent-tech-"
        "jobs-ai"
    ),
}

for filename, url in TARGETS.items():
    print(f"Fetching {filename}...")
    result = fetch_html(url)
    if result.ok:
        (FIXTURES_DIR / filename).write_text(result.html, encoding="utf-8")
        print(f"  ✓ Saved {len(result.html):,} chars to {filename}")
    else:
        print(f"  ✗ Failed: {result.error}")
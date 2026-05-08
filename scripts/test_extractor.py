"""
Sanity check: run the extractor on saved fixtures.
Run from repo root: python -m scripts.test_extractor
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.orchestrator.extractor import extract_page

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

CASES = [
    ("rei_blog.html", "http://blog.rei.com/camp/how-to-introduce-your-indoorsy-friend-to-the-outdoors/"),
    ("cnn_article.html", "https://www.cnn.com/2025/09/23/tech/google-study-90-percent-tech-jobs-ai"),
    ("amazon_toaster.html", "http://www.amazon.com/Cuisinart-CPT-122-Compact-2-SliceToaster/dp/B009GQ034C"),
]


def summarize(filename: str, url: str) -> None:
    path = FIXTURES / filename
    if not path.exists():
        print(f"  ✗ Missing fixture: {filename}")
        return

    html = path.read_text(encoding="utf-8")
    metadata, content, errors = extract_page(html, url=url)

    print(f"\n{'─' * 70}")
    print(f"  {filename}")
    print(f"{'─' * 70}")
    print(f"  title         : {metadata.title}")
    print(f"  description   : {(metadata.description or '')[:100]}...")
    print(f"  author        : {metadata.author}")
    print(f"  published_date: {metadata.published_date}")
    print(f"  language      : {metadata.language}")
    print(f"  canonical_url : {metadata.canonical_url}")
    print(f"  og_data keys  : {list(metadata.og_data.keys())[:5]}")
    print(f"  json_ld blocks: {len(metadata.json_ld)}")
    print(f"  body words    : {content.word_count}")
    print(f"  body preview  : {content.body_text[:200]}...")
    print(f"  errors        : {errors}")


print("=" * 70)
print("Extractor sanity check")
print("=" * 70)

for filename, url in CASES:
    summarize(filename, url)

print("\n" + "=" * 70)
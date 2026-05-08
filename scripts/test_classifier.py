"""
Sanity check: run the full extraction + classification pipeline on fixtures.
Run from repo root: python -m scripts.test_classifier
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.orchestrator.classifier import classify_page
from app.orchestrator.extractor import extract_page

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

CASES = [
    ("rei_blog.html", "http://blog.rei.com/camp/how-to-introduce-your-indoorsy-friend-to-the-outdoors/"),
    ("cnn_article.html", "https://www.cnn.com/2025/09/23/tech/google-study-90-percent-tech-jobs-ai"),
    ("amazon_toaster.html", "http://www.amazon.com/Cuisinart-CPT-122-Compact-2-SliceToaster/dp/B009GQ034C"),
]


def run_one(filename: str, url: str) -> None:
    path = FIXTURES / filename
    if not path.exists():
        print(f"  ✗ Missing fixture: {filename}")
        return

    html = path.read_text(encoding="utf-8")
    metadata, content, ext_errors = extract_page(html, url=url)

    topics, cls_errors = classify_page(
        url=url,
        title=metadata.title,
        description=metadata.description,
        body_text=content.body_text,
        og_data=metadata.og_data,
        json_ld=metadata.json_ld,
    )

    print(f"\n{'─' * 70}")
    print(f"  {filename}")
    print(f"{'─' * 70}")
    print(f"  title : {metadata.title}")
    print(f"  topics:")
    for t in topics:
        print(f"    [{t.source.value:<10}] {t.confidence:.3f}  {t.topic}")
    if cls_errors:
        print(f"  errors: {cls_errors}")


print("=" * 70)
print("Classifier sanity check (will load MiniLM model on first run, ~30s)")
print("=" * 70)

for filename, url in CASES:
    run_one(filename, url)

print("\n" + "=" * 70)
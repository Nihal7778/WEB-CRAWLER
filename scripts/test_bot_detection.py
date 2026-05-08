"""
Sanity check: bot detection on saved fixtures.
Run from repo root: python -m scripts.test_bot_detection
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.utils.bot_detection import detect_bot_page

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"

CASES = [
    ("amazon_toaster.html", True),   # expect bot page
    ("rei_blog.html", False),        # expect real content
    ("cnn_article.html", False),     # expect real content
]

print("=" * 70)
print("Bot detection sanity check")
print("=" * 70)

for filename, expected_bot in CASES:
    path = FIXTURES / filename
    if not path.exists():
        print(f"  ✗ Missing fixture: {filename}")
        continue

    html = path.read_text(encoding="utf-8")
    result = detect_bot_page(html)

    marker = "✓" if result.is_bot_page == expected_bot else "✗"
    expected_str = "bot" if expected_bot else "real"
    actual_str = "bot" if result.is_bot_page else "real"

    print(f"  {marker} {filename:<25} expected={expected_str:<5} got={actual_str:<5} reason={result.reason or '-'}")

print("=" * 70)
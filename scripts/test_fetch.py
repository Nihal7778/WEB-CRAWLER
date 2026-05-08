"""
Phase 1 smoke test.

Hits all 3 test URLs from the assignment PDF and prints summary +
preview of HTML so we can manually verify the network layer works.

Run from repo root:
    python -m scripts.test_fetch
"""

import sys
from pathlib import Path

# Make `app` importable when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.fetcher import fetch_html

TEST_URLS = [
    # E-commerce — will likely hit anti-bot. Known limitation, documented.
    "http://www.amazon.com/Cuisinart-CPT-122-Compact-2-SliceToaster/dp/"
    "B009GQ034C/ref=sr_1_1?s=kitchen&ie=UTF8&qid=1431620315&sr=1-1"
    "&keywords=toaster",
    # Blog / outdoor content
    "http://blog.rei.com/camp/how-to-introduce-your-indoorsy-friend-to-the-outdoors/",
    # News article
    "https://www.cnn.com/2025/09/23/tech/google-study-90-percent-tech-jobs-ai",
]

PREVIEW_CHARS = 500


def print_separator(char: str = "=", width: int = 80) -> None:
    print(char * width)


def run() -> None:
    print_separator()
    print(f"Phase 1 Network Layer Smoke Test — {len(TEST_URLS)} URLs")
    print_separator()

    results_summary = []

    for i, url in enumerate(TEST_URLS, 1):
        print(f"\n[{i}/{len(TEST_URLS)}] Fetching: {url[:80]}...")
        print_separator("-")

        result = fetch_html(url)

        print(f"  Status code  : {result.status_code}")
        print(f"  Final URL    : {result.url[:80]}...")
        print(f"  Content-Type : {result.content_type}")
        print(f"  HTML length  : {len(result.html):,} chars")
        print(f"  OK           : {result.ok}")
        if result.error:
            print(f"  Error        : {result.error}")

        if result.html:
            preview = result.html[:PREVIEW_CHARS].replace("\n", " ")
            print(f"\n  Preview (first {PREVIEW_CHARS} chars):")
            print(f"  {preview}...")

        results_summary.append({
            "url": url[:60],
            "ok": result.ok,
            "status": result.status_code,
            "size": len(result.html),
        })

    # Final summary table
    print()
    print_separator()
    print("SUMMARY")
    print_separator()
    for r in results_summary:
        status_marker = "✓" if r["ok"] else "✗"
        print(
            f"  {status_marker}  status={r['status']:<4}  "
            f"size={r['size']:>10,}  {r['url']}..."
        )
    print_separator()

    successful = sum(1 for r in results_summary if r["ok"])
    print(f"\n{successful}/{len(results_summary)} URLs fetched successfully.\n")


if __name__ == "__main__":
    run()


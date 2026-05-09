import json
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.orchestrator.classifier import classify_page
from app.orchestrator.extractor import extract_page
from app.fetcher import fetch_html
from app.utils.bot_detection import detect_bot_page
from poc.queue_client import (
    delete_crawl_message,
    receive_crawl_message,
)
from poc.storage import build_record, put_html, put_metadata, url_hash

_print_lock = threading.Lock()


def _log(worker_id: int, msg: str) -> None:
    with _print_lock:
        print(f"[worker-{worker_id}] {msg}")


def process_url(worker_id: int, url: str) -> dict:
    started = time.monotonic()

    fetch_result = fetch_html(url)
    if not fetch_result.ok:
        return {
            "url": url,
            "status": "failed",
            "error": fetch_result.error,
            "latency_ms": int((time.monotonic() - started) * 1000),
        }

    html = fetch_result.html
    final_url = fetch_result.url
    fetched_at = datetime.now(timezone.utc)

    bot_check = detect_bot_page(html, status_code=fetch_result.status_code)

    metadata, content, ext_errors = extract_page(html, url=final_url)

    topics = []
    cls_errors = []
    if not bot_check.is_bot_page:
        topics, cls_errors = classify_page(
            url=final_url,
            title=metadata.title,
            description=metadata.description,
            body_text=content.body_text,
            og_data=metadata.og_data,
            json_ld=metadata.json_ld,
        )

    if bot_check.is_bot_page:
        status = "partial"
    elif ext_errors and not metadata.title:
        status = "partial"
    else:
        status = "success"

    crawl_response = {
        "schema_version": 1,
        "url": final_url,
        "status": status,
        "fetch_status_code": fetch_result.status_code,
        "metadata": {
            "title": metadata.title,
            "description": metadata.description,
            "language": metadata.language,
        },
        "content": {
            "word_count": content.word_count,
        },
        "topics": [
            {"topic": t.topic, "confidence": t.confidence, "source": t.source.value}
            for t in topics
        ],
        "bot_blocked": bot_check.is_bot_page,
        "errors": list(ext_errors) + list(cls_errors),
    }

    s3_key = put_html(url_hash(url), html, fetched_at)
    record = build_record(url, final_url, crawl_response, s3_key)
    put_metadata(record)

    return {
        "url": url,
        "status": status,
        "topics_count": len(topics),
        "bot_blocked": bot_check.is_bot_page,
        "latency_ms": int((time.monotonic() - started) * 1000),
        "s3_key": s3_key,
    }


def run_worker(worker_id: int, stop_event: threading.Event) -> None:
    idle_polls = 0
    while not stop_event.is_set():
        msg = receive_crawl_message(wait_seconds=2)
        if msg is None:
            idle_polls += 1
            if idle_polls >= 3:
                _log(worker_id, "no messages, exiting")
                return
            continue
        idle_polls = 0
        url = msg["body"]["url"]
        try:
            result = process_url(worker_id, url)
            delete_crawl_message(msg["receipt_handle"])
            _log(
                worker_id,
                f"{result['status']:<8} {result['latency_ms']:>5}ms  {url[:70]}",
            )
        except Exception as e:
            _log(worker_id, f"ERROR processing {url}: {e}")
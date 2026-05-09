import gzip
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from poc.aws_clients import (
    DDB_TABLE,
    S3_BUCKET,
    get_dynamodb_resource,
    get_s3,
)


def url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _s3_key(url_h: str, fetched_at: datetime) -> str:
    return f"{fetched_at.year}/{fetched_at.month:02d}/{url_h[:2]}/{url_h}.html.gz"


def put_html(url_h: str, html: str, fetched_at: datetime) -> str:
    s3 = get_s3()
    key = _s3_key(url_h, fetched_at)
    body = gzip.compress(html.encode("utf-8", errors="replace"))
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=key,
        Body=body,
        ContentType="text/html",
        ContentEncoding="gzip",
    )
    return key


def get_html(s3_key: str) -> str:
    s3 = get_s3()
    obj = s3.get_object(Bucket=S3_BUCKET, Key=s3_key)
    return gzip.decompress(obj["Body"].read()).decode("utf-8", errors="replace")


def _to_ddb(value):
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, list):
        return [_to_ddb(v) for v in value]
    if isinstance(value, dict):
        return {k: _to_ddb(v) for k, v in value.items()}
    return value


def put_metadata(record: dict) -> None:
    table = get_dynamodb_resource().Table(DDB_TABLE)
    table.put_item(Item=_to_ddb(record))


def get_metadata(url: str) -> Optional[dict]:
    table = get_dynamodb_resource().Table(DDB_TABLE)
    res = table.get_item(Key={"url_hash": url_hash(url)})
    return res.get("Item")


def build_record(
    url: str,
    final_url: str,
    crawl_response_json: dict,
    s3_key: Optional[str],
) -> dict:
    return {
        "url_hash": url_hash(url),
        "url": url,
        "final_url": final_url,
        "s3_key": s3_key,
        "last_crawled": datetime.now(timezone.utc).isoformat(),
        "schema_version": crawl_response_json.get("schema_version", 1),
        "status": crawl_response_json.get("status"),
        "title": crawl_response_json.get("metadata", {}).get("title"),
        "description": crawl_response_json.get("metadata", {}).get("description"),
        "language": crawl_response_json.get("metadata", {}).get("language"),
        "word_count": crawl_response_json.get("content", {}).get("word_count", 0),
        "topics": [
            {
                "topic": t["topic"],
                "confidence": t["confidence"],
                "source": t["source"],
            }
            for t in crawl_response_json.get("topics", [])
        ],
        "bot_blocked": crawl_response_json.get("bot_blocked", False),
        "fetch_status_code": crawl_response_json.get("fetch_status_code", 0),
        "errors": crawl_response_json.get("errors", []),
    }
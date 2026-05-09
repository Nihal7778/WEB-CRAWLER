import json
from typing import Iterator, Optional

from poc.aws_clients import (
    CRAWL_QUEUE,
    CLASSIFY_QUEUE,
    get_queue_url,
    get_sqs,
)


def push_crawl_message(url: str) -> None:
    sqs = get_sqs()
    sqs.send_message(
        QueueUrl=get_queue_url(CRAWL_QUEUE),
        MessageBody=json.dumps({"url": url}),
    )


def push_classify_message(url_hash: str, payload: dict) -> None:
    sqs = get_sqs()
    sqs.send_message(
        QueueUrl=get_queue_url(CLASSIFY_QUEUE),
        MessageBody=json.dumps({"url_hash": url_hash, **payload}),
    )


def receive_crawl_message(wait_seconds: int = 2) -> Optional[dict]:
    sqs = get_sqs()
    res = sqs.receive_message(
        QueueUrl=get_queue_url(CRAWL_QUEUE),
        MaxNumberOfMessages=1,
        WaitTimeSeconds=wait_seconds,
        VisibilityTimeout=60,
    )
    msgs = res.get("Messages", [])
    if not msgs:
        return None
    msg = msgs[0]
    return {
        "body": json.loads(msg["Body"]),
        "receipt_handle": msg["ReceiptHandle"],
    }


def delete_crawl_message(receipt_handle: str) -> None:
    sqs = get_sqs()
    sqs.delete_message(
        QueueUrl=get_queue_url(CRAWL_QUEUE),
        ReceiptHandle=receipt_handle,
    )


def queue_depth(queue_name: str = CRAWL_QUEUE) -> int:
    sqs = get_sqs()
    res = sqs.get_queue_attributes(
        QueueUrl=get_queue_url(queue_name),
        AttributeNames=["ApproximateNumberOfMessages"],
    )
    return int(res["Attributes"]["ApproximateNumberOfMessages"])
import os
import boto3

ENDPOINT_URL = os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566")
REGION = os.getenv("AWS_REGION", "us-east-1")

CRAWL_QUEUE = "brightedge-crawl-queue"
CRAWL_DLQ = "brightedge-crawl-dlq"
CLASSIFY_QUEUE = "brightedge-classify-queue"
S3_BUCKET = "brightedge-raw"
DDB_TABLE = "brightedge-metadata"


def _common_kwargs():
    kwargs = {"region_name": REGION}
    if ENDPOINT_URL:
        kwargs["endpoint_url"] = ENDPOINT_URL
        kwargs["aws_access_key_id"] = "test"
        kwargs["aws_secret_access_key"] = "test"
    return kwargs


def get_sqs():
    return boto3.client("sqs", **_common_kwargs())


def get_s3():
    return boto3.client("s3", **_common_kwargs())


def get_dynamodb_resource():
    return boto3.resource("dynamodb", **_common_kwargs())


def get_queue_url(name: str) -> str:
    sqs = get_sqs()
    return sqs.get_queue_url(QueueName=name)["QueueUrl"]
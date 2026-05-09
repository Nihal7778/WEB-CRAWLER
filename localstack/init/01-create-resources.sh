#!/bin/bash
set -e

ENDPOINT="http://localhost:4566"
REGION="us-east-1"

echo "Creating SQS queues..."
awslocal sqs create-queue --queue-name brightedge-crawl-dlq --region $REGION
awslocal sqs create-queue --queue-name brightedge-crawl-queue --region $REGION
awslocal sqs create-queue --queue-name brightedge-classify-queue --region $REGION

echo "Creating S3 bucket..."
awslocal s3 mb s3://brightedge-raw --region $REGION

echo "Creating DynamoDB table..."
awslocal dynamodb create-table \
    --table-name brightedge-metadata \
    --attribute-definitions AttributeName=url_hash,AttributeType=S \
    --key-schema AttributeName=url_hash,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region $REGION

echo "Resources created."
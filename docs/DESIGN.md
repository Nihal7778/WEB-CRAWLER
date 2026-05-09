# BrightEdge Crawler — System Design
 
**Live Demo:** https://web-crawler-pn8j.onrender.com/docs  
**Schema Version:** 1  

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Part 1 — Core Crawler Service](#2-part-1--core-crawler-service)
3. [Part 2 — Distributed Architecture](#3-part-2--distributed-architecture)
4. [Unified Data Schema](#4-unified-data-schema)
5. [Capacity Planning & SLO Math](#5-capacity-planning--slo-math)
6. [SLOs and SLAs](#6-slos-and-slas)
7. [Storage Design](#7-storage-design)
8. [Classification Pipeline](#8-classification-pipeline)
9. [Cost Optimization](#9-cost-optimization)
10. [Monitoring & Observability](#10-monitoring--observability)
11. [Component Tradeoffs](#11-component-tradeoffs)
12. [Proof of Concept — LocalStack](#12-proof-of-concept--localstack)
13. [Future Optimizations](#13-future-optimizations)

---

## 1. Executive Summary

This document describes the design of a URL crawling and topic classification service built for BrightEdge. The system accepts URLs, fetches their HTML content, extracts structured metadata and classifies each page into human-readable topics using a hybrid ML pipeline.

Part 1 delivers a fully working single-service implementation deployed publicly on Render. It proves the extraction and classification logic on real URLs including e-commerce product pages, news articles and outdoor lifestyle content.

Part 2 describes the distributed architecture required to operate this pipeline at billion URL scale, designed for reliability, cost efficiency and horizontal scalability. A local proof of concept using LocalStack validates the distributed design before committing to cloud spend — see Section 12.

The central design principle throughout is **scale-by-swap**: every component built in Part 1 maps directly to a production equivalent in Part 2. Swapping the in-process function call for an SQS message, the local file for an S3 object or the synchronous response for a DynamoDB write requires no changes to the extraction and classification logic
inside each component.

---

## 2. Part 1 — Core Crawler Service

### 2.1 Architecture

A single containerized FastAPI service handling one URL per request synchronously. Deployed on Render via Docker. No queues, no databases, no async workers — the full pipeline runs in a single request-response cycle.

![Distributed Architecture](images/Distributed%20system.drawio.png)


### 2.2 Component responsibilities

**Fetcher** — retrieves raw HTML using `httpx` with realistic browser headers (User-Agent rotation, Sec-Fetch-*, Accept-Language). Separate connect (10s) and read (15s) timeouts prevent slow servers from stalling workers. Returns a structured `FetchResult` on failure rather than raising, keeping error policy in the caller.

**Bot detector** — inspects response size and body for known anti-bot phrases (Amazon, Cloudflare, Akamai, PerimeterX). Returns
`status: "partial"` rather than failing when a captcha page is detected. Amazon's anti-bot response is the demonstrating example: the service identifies it, flags it correctly, and returns the heuristic category (`Ecommerce > Product Page`) from the domain pattern.

**Extractor** — three layers in priority order. Trafilatura is the primary tool, using ML-trained heuristics to strip nav/footer/ads. Extruct pulls explicit structured data (OpenGraph, JSON-LD). BeautifulSoup fills gaps for non-standard meta tags. The merger applies precedence rules to combine all three outputs into a unified `PageMetadata` object.

**Classifier** — three stages. Heuristic checks URL patterns and og:type first; a domain match (amazon.com) or path match (/dp/) short-circuits the pipeline at ~5ms with no model inference. For everything else, KeyBERT extracts top-N keyphrases using sentence-transformer embeddings. These keyphrases are fed with the title and description into the MiniLM embedding classifier, which computes cosine similarity against a pre-embedded IAB taxonomy and returns the top-K category matches.

**Schema** — a versioned Pydantic `CrawlResponse` model is the API contract. The same schema is used in Part 1 responses, stored in DynamoDB in Part 2 and served by the read API. It includes metadata, body text, topics with confidence + source provenance, bot detection flag and a non-fatal errors array.

### 2.3 Failure handling

The service follows a degrade-don't-crash principle. Every stage returns a structured partial result on failure rather than raising an exception. A timeout returns `status: "failed"`. A captcha page returns `status: "partial"` with whatever was extractable. A failed LLM call(if enabled) degrades to keyword-only topics. The API never returns HTTP 500 for content-level failures but only for protocol-level issues like malformed request bodies.

### 2.4 Deployment

Single Docker container on Render free tier. Multi-stage Dockerfile: builder stage installs all dependencies and pre-downloads the MiniLM model; runtime stage copies only the venv and model cache, keeping the final image lean. The MiniLM model is baked into the image at build time to avoid 30-second first-request latency in production.

---

## 3. Part 2 — Distributed Architecture

### 3.1 System overview

### 3.2 Write path — detailed

**Ingestion**

A Lambda function reads URL lists from S3 (text file) or MySQL query results. Before enqueuing, it computes `sha256(canonical_url)` and checks DynamoDB for an existing record with a `last_crawled` timestamp within the past 30 days. URLs that pass dedup are pushed to an SQS queue partitioned by `hash(domain) % N_partitions`. Partitioning by domain keeps URLs for the same site on the same workers, enabling accurate per-domain rate limiting without cross-worker coordination.

URL canonicalization happens at ingestion: strip tracking parameters (`?utm_*`, `?ref=`), normalize trailing slashes, lowercase the host. This alone eliminates 15–25% of apparent duplicates from typical URL lists.

**Crawler fleet**

ECS Fargate Spot workers autoscale on SQS queue depth. Each worker runs the same Docker image as Part 1 — the fetcher, extractor and bot detector are identical code paths. The only difference is the trigger: instead of an HTTP request, the worker pulls a message from SQS.

Per-domain rate limiting is enforced via Redis atomic increment with TTL. Before fetching, the worker increments a counter keyed by `domain:minute` and checks against a configured limit (default: 1 req/sec/domain, configurable per domain tier). A `429` response from a domain triggers exponential backoff and message visibility extension rather than requeueing.

Robots.txt responses are cached in Redis with a 24-hour TTL. Parsing happens once per domain per day — not per URL. Disallowed paths are checked before fetch; disallowed URLs return a structured skip result written to DynamoDB with `status: "robots_disallowed"`.

Failed URLs (network error, 5xx, bot block) are retried up to 5 times with exponential backoff. After 5 attempts, the message moves to a dead letter Queue for manual review. Common DLQ contents: anti-bot blocks, JS-required SPAs, dead links.

**Storage writes**

After a successful fetch, the worker writes three outputs:

1. Raw HTML compressed with gzip to S3: `s3://brightedge-raw/{year}/{month}/{url_hash}.html.gz`

2. Extracted metadata to DynamoDB with `url_hash` as partition key.
   Fields: url, title, description, author, published_date, language,
   og_data, json_ld, body_text (truncated to 10KB), word_count,
   fetch_status_code, bot_blocked, schema_version, last_crawled.

3. A classification task message to the classify SQS queue containing
   `(url_hash, title, description, body_text)`. This decouples crawl
   throughput from classification throughput — the classifier fleet can
   scale independently.

**Classifier fleet**

Separate Fargate on-demand workers (not Spot — they hold LLM API connections mid-call) consume from the classify queue. Each worker runs the same classification pipeline as Part 1: heuristic → KeyBERT → MiniLM embedding similarity. Classification results are written back to the existing DynamoDB record as a `topics` field update.

Workers batch 20 URLs per cycle. KeyBERT and MiniLM run on batched input, which is significantly faster than one-at-a-time inference. At billion scale this batching is the primary cost lever on the classification side.

### 3.3 Read path — detailed

Read traffic is completely decoupled from the write path. The write path can be slow, backlogged, or reprocessing without affecting read API availability.

**CloudFront** caches popular URL metadata responses at the edge for 1 hour. Cache hits never reach Lambda or DynamoDB — this handles the "hot URL" problem (top 1% of URLs receiving the majority of read traffic) for free.

**API Gateway + Lambda** handles cache misses. Lambda is the right choice for the read API because read traffic is bursty (not sustained), Lambda autoscales to millions of concurrent requests and there is no idle cost.

**Redis (ElastiCache)** provides a sub-millisecond cache layer for URLs that are hot but not yet warmed in CloudFront. The Lambda function checks Redis before hitting DynamoDB. Cache TTL: 1 hour for successful results, 5 minutes for `status: "failed"` results.

**DynamoDB** is the source of truth. Point lookups by `url_hash` return single-digit millisecond responses at any scale. No scans, no table traversals — only `GetItem` calls by primary key.

---

## 4. Unified Data Schema

The same Pydantic `CrawlResponse` schema defined in Part 1 is used throughout the entire system. This is a deliberate architectural choice: the extraction logic produces a typed object; the API serializes it to JSON; DynamoDB stores it as a JSON document; the read API deserializes it back. No translation layer required at any boundary.

Schema evolution follows additive-only rules. New fields are added with default values so existing DynamoDB records remain valid without migration. The `schema_version` field enables the read API to handle multiple versions simultaneously during rollouts.

DynamoDB primary key: `url_hash = sha256(canonical_url)`.
Secondary index: `content_hash = sha256(body_text[:10000])` for
cross-URL dedup (different URLs, identical content).

---

## 5. Capacity Planning & SLO Math

### Input assumptions

- 1 billion URLs per month
- Average page size: 500KB HTML, approx 5KB metadata after extraction
- Crawl window: 30 days (can drain faster with more workers)
- ~30% dedup rate (duplicate/recently-crawled URLs skipped at ingestion)
- Effective unique URLs to crawl: ~700M/month

### Throughput math
700M URLs / 30 days = 23.3M URLs/day
23.3M / 86,400 sec  = 270 URLs/sec sustained throughput
Per worker: 1 URL / 3.5s = ~17 URLs/min = ~1,000 URLs/hour
Workers needed: 270 / (1000/3600) = 270 / 0.28 ≈ 1,000 workers
With 1,000 Fargate Spot workers:
1,000 × 17 URLs/min = 17,000 URLs/min
700M / 17,000       = ~41,000 min = ~28 days
With 1,500 workers: ~19 days
With 2,000 workers: ~14 days — comfortable within the 30-day window


Real bottleneck is not compute — it is per-domain politeness. Amazon, CNN and other high-volume domains each appear millions of times in the URL list. Per-domain rate limiting (1 req/sec) caps throughput on hot domains regardless of worker count.

### Storage math
Raw HTML (gzipped, ~100KB avg compressed):
700M × 100KB = 70TB/month raw
→ S3 Standard: $0.023/GB × 70,000GB = $1,610/month
→ Transition to S3-IA after 30 days: $0.0125/GB → $875/month
→ Glacier after 90 days: $0.004/GB → $280/month
Metadata (DynamoDB, ~5KB avg per record):
700M × 5KB = 3.5TB
DynamoDB on-demand writes: $1.25/M writes × 700M = $875/month
DynamoDB storage: $0.25/GB × 3,500GB = $875/month
Total storage per month: ~$3,500


### Cost summary

| Component | Monthly cost |
|---|---|
| Fargate Spot (2000 workers × avg 15 days) | ~$14,000 |
| S3 raw HTML (tiered lifecycle) | ~$3,500 |
| DynamoDB (writes + storage) | ~$1,750 |
| SQS, Lambda, CloudFront, Redis | ~$2,000 |
| Classification workers (Fargate on-demand) | ~$3,000 |
| **Total** | **~$24,250/month** |

LLM cost: **$0** in the default path. LLM is reserved for low-confidence
fallback (~10% of pages) and is batched 20 URLs per call. At 70M fallback
pages × $0.0001/call = **~$700/month** if enabled.

---

## 6. SLOs and SLAs

| Metric | SLO | Measurement |
|---|---|---|
| Crawl freshness P95 | < 24h from ingestion to stored | CloudWatch queue age |
| API availability | 99.9% monthly | Route53 health checks |
| API read latency P99 | < 200ms | CloudWatch Lambda duration |
| Crawl success rate | ≥ 95% of non-disallowed URLs | DLQ size / total enqueued |
| Classification confidence avg | ≥ 0.40 | Sampled DynamoDB records |
| Bot block rate | < 10% of total crawls | DynamoDB status distribution |

**SLA** (external commitment): 99.5% availability on the read API, < 500ms
P99 latency. The read path (CloudFront → Lambda → DynamoDB) is
independently deployable and has no dependency on crawl pipeline health.

---

## 7. Storage Design

### Why S3 + DynamoDB and not a single database

Raw HTML and structured metadata have fundamentally different access patterns. Raw HTML is written once, rarely read (only for reprocessing) and grows unboundedly. DynamoDB is optimized for the actual read pattern: point lookup by URL hash. Storing raw HTML in DynamoDB would be expensive (DynamoDB charges by item size) and wasteful (items would exceed the 400KB limit for large pages).

S3 lifecycle policies automatically move data through cost tiers as it ages, which is exactly the right behavior for a crawler: fresh HTML is accessed during initial processing, then effectively cold forever.

### DynamoDB key design

Partition key: `url_hash = sha256(canonical_url)` — uniform distribution across partitions, no hot key problem.

Global Secondary Index: `content_hash = sha256(body_text[:10000])` — enables deduplication of syndicated content. Two different URLs with identical body text can share a single classification result without re-running the ML pipeline.

### S3 partition strategy
s3://brightedge-raw/
└── {year}/
└── {month}/
└── {domain_prefix_2}/    # e.g. "am" for amazon
└── {url_hash}.html.gz



The `domain_prefix_2` partition avoids S3 list-request hotspots when bulk-listing objects for a reprocessing job. Athena can query this structure efficiently for analytics without a separate data warehouse.

---

## 8. Classification Pipeline

### Design philosophy

The key distinction from naive LLM-per-URL classification is the separation of two sub-problems: closed-set classification (map to a known taxonomy label) and open-vocabulary topic extraction (emit human-readable keyphrases). These optimize differently and should use different tools.

Page → Heuristic (URL + og:type + JSON-LD @type)
│ match → return category (skip remaining stages, ~5ms)
│
└─ no match →
KeyBERT → top-N keywords (open-vocabulary topics)
│
└─► MiniLM cosine similarity vs pre-embedded IAB labels
│ confidence ≥ 0.40 → return category
│
└─ confidence < 0.40 → LLM fallback (batched)
(future: replace with fine-tuned distilBERT)


### Cost profile at scale

| Stage | % of pages | Cost/1K pages | Cost at 1B pages |
|---|---|---|---|
| Heuristic | ~40% | $0 | $0 |
| KeyBERT + MiniLM | ~50% | <$0.01 | ~$5,000 |
| LLM fallback | ~10% | ~$0.10 | ~$10,000 |

Total classification cost at 1B pages: **~$15,000/month** worst case.
With fine-tuned distilBERT replacing LLM fallback (Phase 3+ roadmap):
**~$2,000/month**.

### Why not LLM-per-URL

An LLM-per-URL approach using gpt-4o-mini costs ~$0.0001/page. At 1B pages that is $100,000/month in LLM spend alone — 4x the total system cost of our hybrid approach. The embedding-similarity classifier achieves comparable accuracy on the 90% of pages that fall clearly within the taxonomy, reserving the LLM for the genuinely ambiguous 10%.

---

## 9. Cost Optimization

Five levers ordered by impact:

**1. Dedup + incremental crawling (50-70% cost reduction)**
Skip URLs crawled within 30 days (dedup at ingestion). Use
`If-Modified-Since` headers for conditional re-fetches (server returns
304, no body transferred, no extraction required). Parse `sitemap.xml`
`<lastmod>` to identify changed content before crawling.

**2. Two-tier classifier with fine-tuning roadmap (98% LLM cost reduction)**
Current: heuristic + MiniLM embedding, LLM only on low-confidence 10%.
Phase 3: fine-tune distilBERT on LLM-labeled examples — after 100K
labeled records, the fine-tuned model replaces LLM fallback at ~1/50th
the cost per inference.

**3. Fargate Spot for crawlers (70% compute cost reduction)**
Crawlers are interruption-tolerant: a failed crawl requeues automatically.
Fargate Spot pricing is 70% below on-demand. Classifier workers use
on-demand because they hold LLM API connections mid-call — interruption
would waste token spend.

**4. S3 lifecycle tiering + gzip compression (85% storage cost reduction)**
Compress HTML before write (~5-10x compression ratio). Lifecycle:
Standard → IA (30d) → Glacier Deep Archive (90d). Old HTML is almost
never re-read unless a reprocessing job is triggered.

**5. Tiered proxy strategy (80% proxy cost reduction)**
Datacenter proxies ($0.50/GB) for 90% of domains. Residential proxies
($8/GB) only for domains that actively fingerprint datacenter IPs
(Amazon, Cloudflare-protected sites). Domain classification at ingestion
routes to the appropriate proxy tier.

---

## 10. Monitoring & Observability

### Metrics (CloudWatch)

| Metric | Alarm threshold | Why |
|---|---|---|
| SQS crawl queue depth | > 10M messages | Backlog growing faster than workers drain it |
| SQS DLQ size | > 10,000 messages | Systematic failure pattern |
| ECS task failure rate | > 5% | Worker crashes |
| DynamoDB write throttles | > 100/min | Capacity issue |
| Lambda P99 latency | > 500ms | Read API SLO breach |
| Classification confidence avg | < 0.35 | Taxonomy drift or model degradation |
| Bot block rate | > 15% | IP reputation issue, rotate proxies |

### Dashboards

Three CloudWatch dashboards:

**Write path dashboard:** SQS queue depth over time, crawl success/failure
rate, per-domain block rate, ECS task count, S3 write rate, DynamoDB
write capacity.

**Read path dashboard:** CloudFront cache hit rate, Lambda invocation count
and duration, Redis cache hit rate, DynamoDB read capacity.

**Cost dashboard:** Daily spend by service (ECS, S3, DynamoDB, SQS, Lambda),
cost per million URLs crawled, LLM fallback rate (key cost driver).

### Logging

Structured JSON logs (implemented in Part 1) ship to CloudWatch Logs.
Every log line includes: timestamp, level, service name, request URL,
stage, latency, and any error context. Log sampling: 100% for errors and
warnings, 10% for successful crawls (cost control at scale).

### Tracing

AWS X-Ray traces the full request path from API Gateway through Lambda
to DynamoDB for the read path. Latency breakdowns reveal whether P99
breaches are from Lambda cold starts, Redis misses, or DynamoDB.

---

## 11. Component Tradeoffs

### Queue: SQS vs Kafka

SQS was chosen because it is fully managed, scales automatically, and
has native DLQ support. Kafka (via MSK) offers higher throughput per
partition, true message ordering, and replay capability. We would migrate
to Kafka if the system requires event replay for reprocessing historical
crawls or if throughput exceeds ~10,000 messages/sec sustained — neither
applies in Phase 1 or Phase 2.

### Metadata store: DynamoDB vs PostgreSQL

DynamoDB was chosen because the access pattern is a single-key point
lookup (`url_hash → metadata`). There are no JOIN requirements, no
complex queries, and DynamoDB's autoscaling handles billion-row workloads
without schema migrations. PostgreSQL would be the right choice if
analytical queries across the metadata table became a primary workload
(e.g., "count all English-language articles published in 2024") — for
that use case, the S3 + Athena analytics path is more cost-effective than
either option.

### Crawler workers: Fargate Spot vs EC2 Spot

Fargate Spot was chosen for operational simplicity: no AMI management,
no capacity reservation, no instance type decisions. EC2 Spot on
i4i-class instances would be ~10–15% cheaper at sustained high utilization
and offers local NVMe storage for temporary HTML buffering. We would
revisit this at Phase 3+ scale when the operational cost of managing EC2
capacity is justified by the savings.

### Classification: Embedding similarity vs LLM-per-URL

The embedding-similarity approach was chosen because it costs ~$0.01/1K
pages versus ~$100/1K pages for LLM-per-URL at scale. Quality is
comparable for the 90% of pages that fall clearly within the taxonomy.
The LLM is retained as a fallback for the genuinely ambiguous 10%,
batched 20 URLs per call to minimize token overhead.

---

## 12. Proof of Concept — LocalStack

### Purpose

Before committing to real AWS infrastructure, we validate the distributed
architecture using LocalStack — a Docker-based tool that provides
real AWS API endpoints (SQS, S3, DynamoDB, Lambda, CloudWatch) running
locally. The same `boto3` code that runs against LocalStack runs
unchanged against real AWS. The only difference is the `endpoint_url`
parameter in the AWS client configuration.

This approach proves the architecture is sound before spending money,
catches IAM permission and API compatibility issues early, and gives any
reviewer a runnable demonstration of the full distributed pipeline without
AWS credentials.

## localstack
docker-compose up
├── LocalStack container (SQS + S3 + DynamoDB + CloudWatch Logs)
└── Redis container (rate limiting + robots cache)


On startup, an init script creates:
- SQS queue: `brightedge-crawl-queue`
- SQS DLQ: `brightedge-crawl-dlq`
- S3 bucket: `brightedge-raw`
- DynamoDB table: `brightedge-metadata` (PK: `url_hash`)

### POC pipeline

urls.txt
│
▼
ingester.py          → pushes URLs to SQS (via boto3 → LocalStack)
│
▼
worker.py (N threads) → pulls from SQS
→ calls existing fetcher.py + extractor.py + classifier.py
→ writes HTML to LocalStack S3
→ writes metadata to LocalStack DynamoDB
│
▼
lookup.py            → queries DynamoDB by URL, prints results


### What the POC proves

| Architectural decision | Validated by POC |
|---|---|
| SQS partitioning by domain hash | Checked via message attributes |
| DynamoDB write on successful crawl | Verified via lookup.py |
| S3 HTML storage | Object exists in LocalStack S3 |
| Worker fault tolerance (message requeue on failure) | Simulated by killing a worker mid-crawl |
| DLQ on 5-failure URLs | Invalid URLs added to urls.txt to trigger DLQ |
| Per-domain rate limiting via Redis | Observed in worker logs |
| Same boto3 code paths as production | endpoint_url is the only config diff |

### Migration to real AWS

Switching from LocalStack to real AWS requires one change:

```python
# app/aws_clients.py

import os
import boto3

LOCALSTACK_ENDPOINT = os.getenv("AWS_ENDPOINT_URL")  # set in .env for local

def get_sqs():
    return boto3.client("sqs", endpoint_url=LOCALSTACK_ENDPOINT)

def get_s3():
    return boto3.client("s3", endpoint_url=LOCALSTACK_ENDPOINT)

def get_dynamodb():
    return boto3.resource("dynamodb", endpoint_url=LOCALSTACK_ENDPOINT)
```

Set `AWS_ENDPOINT_URL=http://localhost:4566` in `.env` for LocalStack.
Unset it in production. No other code changes required.

### Implementation status

LocalStack POC is planned for implementation after the public demo
(Part 1) and design documentation (Part 2) are complete. The
infrastructure-as-code files (`docker-compose.yml`, `init.sh`, `ingester.py`,
`worker.py`, `lookup.py`) are scoped and ready for implementation. The
`app/` module code (fetcher, extractor, classifier) requires zero changes
to run against LocalStack — they are pure Python functions with no AWS
dependency.

---

## 13. Future Optimizations

Ordered by implementation priority for Phase 3+:

**Fine-tuned distilBERT classifier** — after 100K LLM-labeled examples,
fine-tune distilBERT on the classification task. Replaces LLM fallback
entirely. Expected: 98% LLM cost reduction, comparable accuracy,
~25ms inference on CPU.

**Go/Rust crawler workers** — Python's GIL limits async I/O concurrency.
Rewriting the fetcher in Go (`colly`) or Rust (`reqwest`) achieves
5–10x throughput per worker with 1/3 the memory footprint. Same Docker
image contract; only the binary changes.

**ONNX + INT8 quantized MiniLM** — export the MiniLM model to ONNX and
run INT8 quantization via ONNX Runtime. Expected: 3–4x inference speedup,
75% memory reduction, negligible accuracy loss. No code changes in
`embedding_classifier.py` — swap the model loader.

**ScyllaDB over DynamoDB** — at sustained billion-row write loads, ScyllaDB
on i4i EC2 Spot instances costs 2–3x less than DynamoDB on-demand.
Migration path: DynamoDB Streams → Kafka → ScyllaDB dual-write during
transition, then cut over. Application code changes limited to the
`aws_clients.py` adapter layer.

**curl-impersonate + tiered proxies** — `curl-impersonate` matches the
TLS fingerprint of a real Chrome browser, defeating Cloudflare and
Akamai fingerprinting without residential proxies. Residential proxies
reserved for the ~5% of domains that inspect TLS AND validate IP
reputation. Expected: 80% proxy cost reduction.

---

*Document version 1.0 — covers Part 1 deployed service and Part 2
distributed design. LocalStack POC implementation in progress.*


**Architecture diagrams:** 
- [Core Crawler](/Web Crawler/images/Core crawler.drawio.png)
- [Distributed Architecture](/images/Distributed system.drawio.png)

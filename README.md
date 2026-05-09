# BrightEdge Crawler

A URL crawling and topic classification service. Accepts any URL, extracts
structured metadata, and classifies the page into human-readable topics.

**Live demo:** https://web-crawler-pn8j.onrender.com/docs

---

## What it does

- Fetches any URL with realistic browser headers and anti-bot handling
- Extracts title, description, author, date, OpenGraph, JSON-LD
- Classifies pages using a hybrid pipeline:
  - Heuristic (URL pattern + og:type) — free, deterministic
  - KeyBERT — semantic keyword extraction
  - MiniLM cosine similarity — IAB taxonomy classification
- Returns a unified JSON response with metadata, body text, and topics

---

## Quick start

### Try the live API

```bash
curl -X POST https://web-crawler-pn8j.onrender.com/crawl \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://blog.rei.com/camp/how-to-introduce-your-indoorsy-friend-to-the-outdoors/"}'
```

Or open the Swagger UI:
https://web-crawler-pn8j.onrender.com/docs

**Note:** The service runs on Render free tier and may take ~30s to wake up after inactivity. Subsequent requests are fast.

---

## Run locally

### Requirements

- Python 3.11+
- Docker Desktop (for LocalStack POC)

### Setup

```bash
git clone https://github.com/Nihal7778/brightedge-crawler.git
cd brightedge-crawler

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```

### Start the API

```bash
uvicorn app.main:app --reload --port 8000
```

API available at `http://localhost:8000`
Swagger UI at `http://localhost:8000/docs`

### Run with Docker

```bash
docker build -f deploy/Dockerfile -t brightedge-crawler:latest .
docker run -p 8000:8000 brightedge-crawler:latest
```

---

## Run the LocalStack POC

Demonstrates the full distributed pipeline (SQS + S3 + DynamoDB + Redis)
running locally without AWS credentials.

### Requirements

- Docker Desktop running

### Start infrastructure

```bash
docker compose -f localstack/docker-compose.yml up -d
```

Wait ~15 seconds for LocalStack to initialize, then verify:
```bash
docker logs brightedge-localstack | grep "Resources created"
```

### Run the pipeline

```bash
# Push URLs to SQS queue
python -m poc.ingester

# Start 5 crawler workers
python -m poc.run_pipeline

# Look up a crawled URL from DynamoDB
python -m poc.lookup --url https://blog.rei.com/camp/how-to-introduce-your-indoorsy-friend-to-the-outdoors/

# Verify S3 contains the raw HTML
docker exec brightedge-localstack awslocal s3 ls s3://brightedge-raw --recursive
```

### Tear down

```bash
docker compose -f localstack/docker-compose.yml down
```

### What it proves

| Claim | Validated by |
|---|---|
| URL ingest → SQS → worker flow | `ingester.py` → `run_pipeline.py` |
| Raw HTML stored in S3 (gzipped) | `aws s3 ls` shows `.html.gz` objects |
| Metadata stored in DynamoDB | `lookup.py` returns full record |
| Per-domain rate limiting via Redis | Worker logs show timing |
| Same code runs against real AWS | Only `AWS_ENDPOINT_URL` differs |

---

## Project structure
app/
├── main.py                  # FastAPI entry point
├── fetcher.py               # HTTP fetch with UA rotation
├── extractor.py             # Extraction orchestrator
├── classifier.py            # Classification orchestrator
├── schemas.py               # Pydantic models (API contract)
├── config.py                # Environment config
├── extractors/
│   ├── trafilatura_layer.py # Primary: title, body, author
│   ├── extruct_layer.py     # OpenGraph, JSON-LD
│   ├── bs4_layer.py         # Fallback meta tags
│   └── merger.py            # Combines all layers
├── classifiers/
│   ├── heuristic.py         # URL + og:type rules
│   ├── keybert_topics.py    # Keyword extraction
│   ├── embedding_classifier.py  # MiniLM IAB taxonomy
│   └── taxonomy.py          # IAB label list
└── utils/
├── bot_detection.py     # Captcha page detection
└── logging.py           # Structured logging
localstack/
├── docker-compose.yml       # LocalStack + Redis
└── init/
└── 01-create-resources.sh
poc/
├── ingester.py              # urls.txt → SQS
├── worker.py                # SQS → fetch → extract → classify → store
├── run_pipeline.py          # Spawns N workers
├── lookup.py                # DynamoDB point lookup
├── storage.py               # S3 + DynamoDB operations
├── queue_client.py          # SQS operations
└── urls.txt                 # Test URLs
docs/
├── DESIGN.md                # Part 2: distributed system design
├── POC_PLAN.md              # Part 3: phased rollout plan
├── core_crawler_architecture.png
└── distributed_architecture.png
deploy/
├── Dockerfile
└── docker-compose.yml


---

## API reference

### `GET /health`

```json
{"status": "ok", "schema_version": 1}
```

### `POST /crawl`

**Request:**
```json
{
  "url": "https://example.com",
  "include_raw_html": false,
  "classify": true
}
```

**Response:**
```json
{
  "schema_version": 1,
  "url": "https://example.com",
  "requested_url": "https://example.com",
  "status": "success",
  "fetched_at": "2026-05-08T05:51:43Z",
  "fetch_status_code": 200,
  "metadata": {
    "title": "Page title",
    "description": "Page description",
    "author": "Author name",
    "published_date": "2025-01-01",
    "language": "en",
    "canonical_url": "https://example.com",
    "og_data": {},
    "twitter_data": {},
    "json_ld": []
  },
  "content": {
    "body_text": "Main content...",
    "word_count": 450
  },
  "topics": [
    {"topic": "Outdoors > Hiking", "confidence": 0.465, "source": "embedding"},
    {"topic": "friend hike", "confidence": 0.622, "source": "keyword"}
  ],
  "bot_blocked": false,
  "errors": [],
  "latency_ms": 927
}
```

**Status values:**

| Status | Meaning |
|---|---|
| `success` | Full extraction and classification completed |
| `partial` | Bot/captcha page detected, limited metadata extracted |
| `failed` | Fetch failed (timeout, DNS error, 5xx) |

---

## Design documentation

Full system design and POC plan in `docs/`:

- [`DESIGN.md`](docs/DESIGN.md) — distributed architecture for 1B URLs/month
- [`POC_PLAN.md`](docs/POC_PLAN.md) — phased rollout plan with LocalStack POC

---

## Test URLs from assignment

```bash
# E-commerce (bot detected, heuristic classification)
curl -X POST https://web-crawler-pn8j.onrender.com/crawl \
  -H 'Content-Type: application/json' \
  -d '{"url": "http://www.amazon.com/Cuisinart-CPT-122-Compact-2-SliceToaster/dp/B009GQ034C"}'

# Outdoor blog (full extraction + embedding classification)
curl -X POST https://web-crawler-pn8j.onrender.com/crawl \
  -H 'Content-Type: application/json' \
  -d '{"url": "http://blog.rei.com/camp/how-to-introduce-your-indoorsy-friend-to-the-outdoors/"}'

# News article (full extraction + embedding classification)
curl -X POST https://web-crawler-pn8j.onrender.com/crawl \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://www.cnn.com/2025/09/23/tech/google-study-90-percent-tech-jobs-ai"}'
```

---

## AI tools used

Per the assignment guidelines, the following AI tools were used during
development:

| Tool | Usage |
|---|---|
| **Claude (Anthropic)** | Architecture design, ideas generation, development assistance, documentation |
| **Qodo** |  assisted with test validation during development,code reviews |

All architectural decisions, component selection rationale, and
tradeoff analysis were reviewed and validated by the developer.
The classification approach (heuristic + KeyBERT + MiniLM embedding
similarity) was chosen based on the research paper provided in the
assignment brief on production-ready ML classification architectures.

---

## Environment variables

Copy `.env.example` to `.env` and fill in values:

```bash
cp .env.example .env
```

| Variable | Default | Description |
|---|---|---|
| `ENV` | `dev` | `dev` or `prod` |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_FORMAT` | `console` | `console` (dev) or `json` (prod) |
| `PORT` | `8000` | Server port |
| `MAX_BODY_CHARS_RESPONSE` | `10000` | Body text truncation in response |
| `AWS_ENDPOINT_URL` | (unset) | Set to `http://localhost:4566` for LocalStack |



## .env.example
# App
ENV=dev
LOG_LEVEL=INFO
LOG_FORMAT=console
PORT=8000
MAX_BODY_CHARS_RESPONSE=10000

# Set this for LocalStack. Unset (or delete) for real AWS.
# AWS_ENDPOINT_URL=http://localhost:4566


# BrightEdge Crawler — Proof of Concept Plan

**Author:** Nihal  
**Service:** `brightedge-crawler`  
**Live Demo:** https://web-crawler-pn8j.onrender.com/docs  
**GitHub:** https://github.com/Nihal7778/brightedge-crawler  

---

## Table of Contents

1. [Overview](#1-overview)
2. [Phase Breakdown](#2-phase-breakdown)
3. [Known Blockers & Risks](#3-known-blockers--risks)
4. [Estimates & Timeline](#4-estimates--timeline)
5. [LocalStack POC](#5-localstack-poc)
6. [Quality Gates](#6-quality-gates)
7. [Release Plan](#7-release-plan)
8. [Evaluation Criteria](#8-evaluation-criteria)

---

## 1. Overview

The proof of concept follows a four-phase delivery model. Each phase has a defined scope, a measurable exit criterion and a clear mapping to the production architecture described in `DESIGN.md`.

The guiding principle is **scale-by-swap**: Phase 0 proves the core logic works on a single URL. Each subsequent phase replaces one local component with its production equivalent — queue, storage, workers — without changing the extraction and classification logic inside each component.

Phase 0 (the Part 1 demo) is already live at:
`https://web-crawler-pn8j.onrender.com/docs`

The LocalStack POC (Section 5) is the bridge between Phase 0 and
Phase 1 — it proves the distributed design works before committing
to real cloud spend.

Architecture references:
![Core Crawler Architecture](images/Core%20crawler.drawio.png)

---

## 2. Phase Breakdown

### Phase 0 — Single URL Demo (complete)

**Scope:** Single synchronous FastAPI service. One URL in, one
`CrawlResponse` JSON out. No queues, no databases, no workers.

**What it proves:**
- Fetch layer handles real-world URLs including anti-bot responses
- Three-layer extraction pipeline (trafilatura + extruct + BS4)
  produces consistent structured output
- Hybrid classifier (heuristic + KeyBERT + MiniLM) returns accurate
  topics without LLM dependency
- Pydantic schema is the stable contract across all future phases

**Deliverables:**
- Live public endpoint: `https://web-crawler-pn8j.onrender.com`
- Swagger UI for interactive testing: `/docs`
- Docker image deployable on any cloud provider

**Exit criteria:**
- `/health` returns 200
- REI blog URL returns `status: "success"`, title populated, topics include `Outdoors > Hiking`
- Amazon URL returns `status: "partial"`, `bot_blocked: true`, heuristic topic `Ecommerce > Product Page`
- CNN URL returns `status: "success"`, author populated, topics include `News > Technology`

**Status: COMPLETE**

---

### Phase 1 — LocalStack POC (next, approx 2 weeks / 1 engineer)

**Scope:** Run the full distributed pipeline locally using LocalStack to mock AWS services. Proves the architecture before cloud spend.

**What it proves:**
- SQS message flow (ingest → crawl queue → classify queue)
- S3 HTML storage and retrieval
- DynamoDB metadata writes and point-lookup reads
- Per-domain rate limiting via Redis
- Worker fault tolerance (message requeue, DLQ on 5 failures)
- Same boto3 code runs unchanged against real AWS

**Infrastructure (docker-compose):**

Services:
localstack:
image: localstack/localstack:3.x
ports: 4566
services: sqs, s3, dynamodb, logs
redis:
image: redis:7-alpine
ports: 6379
Init script creates:
SQS:      brightedge-crawl-queue (+ DLQ)
brightedge-classify-queue (+ DLQ)
S3:       brightedge-raw
DynamoDB: brightedge-metadata (PK: url_hash)


**New files (zero changes to existing app/ code):**
localstack/
docker-compose.yml       AWS service mocks
init/
01-create-resources.sh Creates queues, bucket, table on startup
poc/
aws_clients.py           boto3 clients with LocalStack endpoint_url
ingester.py              urls.txt → SQS
worker.py                SQS → fetch → extract → classify → S3 + DynamoDB
lookup.py                DynamoDB point lookup by URL
run_pipeline.py          Orchestrator: spawns N workers, drains queue
urls.txt                 20 test URLs across ecommerce, news, outdoors


**How to run:**
```bash
docker-compose -f localstack/docker-compose.yml up -d
python -m poc.ingester        # loads urls.txt → SQS
python -m poc.run_pipeline    # starts 5 workers, drains queue
python -m poc.lookup --url https://blog.rei.com/...
```

**Expected output:**
Loaded 20 URLs into queue
Started 5 workers
[worker-1] crawled https://blog.rei.com/... → 7 topics → 2.4s → S3 ✓ DynamoDB ✓
[worker-3] crawled https://cnn.com/...      → 8 topics → 3.1s → S3 ✓ DynamoDB ✓
[worker-2] crawled https://amazon.com/...   → bot_blocked=True → DynamoDB ✓
...
────────────────────────────────────────────
Summary:  18/20 success   2 partial (bot)
Avg latency: 2.8s/URL    Total: 14.3s (5 workers)
Top categories: Outdoors (6), News (5), Ecommerce (4), Tech (3)
────────────────────────────────────────────
**Exit criteria:**
- [ ] 18/20 URLs successfully crawled and stored
- [ ] DynamoDB records queryable by `url_hash` via `lookup.py`
- [ ] S3 contains compressed HTML for each successful crawl
- [ ] Failed URLs land in DLQ after 5 retries
- [ ] Switching `AWS_ENDPOINT_URL` from LocalStack to real AWS
  requires zero code changes

**Estimated effort:** 2 weeks, 1 engineer

---

### Phase 2 — MVP on AWS (1M URLs, ~4 weeks / 1-2 engineers)

**Scope:** Deploy the distributed architecture to real AWS. Process
1 million URLs end-to-end. Validate SLOs at meaningful scale.

**What changes from Phase 1:**
- LocalStack → real SQS, S3, DynamoDB, Lambda, ElastiCache
- `docker-compose` → ECS Fargate Spot crawler fleet (10 workers)
- `run_pipeline.py` → ECS task definitions with autoscaling
- `poc/aws_clients.py` → production IAM roles, no endpoint_url override
- CloudWatch dashboards live (write + read + cost)

**Infrastructure additions:**
- VPC with private subnets for ECS workers
- ECR repository for crawler Docker image
- ECS cluster with Fargate Spot capacity provider
- ElastiCache Redis (cache.t3.micro for rate limiting)
- API Gateway + Lambda for read path
- CloudFront distribution in front of API Gateway
- IAM roles: crawler-worker-role, classifier-worker-role, lambda-read-role

**What stays the same:**
- app/ code (fetcher, extractor, classifier) — zero changes
- Pydantic schema — zero changes
- Docker image — same image, same entrypoint

**Exit criteria:**
- [ ] 1M URLs processed with < 5% failure rate
- [ ] DynamoDB contains 950K+ valid metadata records
- [ ] API P99 latency < 200ms under 100 concurrent requests
- [ ] CloudWatch alarms configured and tested
- [ ] SLOs met for 1 consecutive week

**Estimated effort:** 4 weeks, 1–2 engineers

---

### Phase 3 — Production (1B URLs/month, ~8 weeks / 2 engineers + 1 SRE)

**Scope:** Full production hardening. Billion-URL throughput. Full
observability. Multi-AZ availability. Cost optimization.

**What changes from Phase 2:**
- 10 ECS workers → 2,000 Fargate Spot workers (autoscaled)
- Basic logging → full CloudWatch + X-Ray tracing
- Single region → multi-AZ within region
- On-demand DynamoDB → provisioned with autoscaling
- No proxy → tiered proxy strategy (datacenter + residential)
- Static taxonomy → versioned taxonomy with drift monitoring
- Manual deployment → CI/CD pipeline (GitHub Actions → ECR → ECS)

**Infrastructure additions:**
- Application Load Balancer for read API
- WAF on API Gateway (rate limiting per client)
- S3 lifecycle policies (Standard → IA → Glacier)
- AWS Backup for DynamoDB point-in-time recovery
- Secrets Manager for proxy credentials and API keys
- Config Service for feature flags (e.g. LLM fallback toggle)

**Exit criteria:**
- [ ] 700M URLs/month processed (effective after 30% dedup)
- [ ] All SLOs met (see DESIGN.md Section 6) for 4 consecutive weeks
- [ ] Runbooks complete for all known failure modes
- [ ] Canary deployment pipeline tested
- [ ] Cost per million URLs within 10% of projection (~$24/1M)

**Estimated effort:** 6–8 weeks, 2 engineers + 1 SRE

---

## 3. Known Blockers & Risks

### High severity

**Anti-bot defenses (Amazon, Cloudflare, Akamai)**
- What: Major e-commerce and news sites return captcha pages or 403s
  for datacenter IPs regardless of User-Agent headers
- Impact: 5–30% of high-value domains may be uncrawlable with basic setup
- Mitigation Phase 1: Detect and flag bot pages (already implemented).
  Document partial results.
- Mitigation Phase 2: `curl-impersonate` for TLS fingerprint matching.
  Datacenter proxy pool for IP rotation.
- Mitigation Phase 3: Tiered residential proxy pool for hostile domains.
  Domain tier classification at ingestion routes to appropriate proxy.
- Remaining risk: Amazon has sophisticated CAPTCHA that survives most
  mitigations without browser automation. Playwright worker fleet is a
  Phase 3+ project.

**JavaScript-rendered pages (SPAs)**
- What: React/Vue/Angular SPAs return near-empty HTML to a basic httpx
  request. The real content loads via JavaScript after page load.
- Impact: ~15–20% of modern websites are SPAs. Trafilatura extracts
  near-nothing from them.
- Mitigation: Separate Playwright worker fleet, triggered when
  body_word_count < 50 on a non-bot page. Playwright is ~10x slower
  and more expensive than httpx — keep it as an exception path.
- Timeline: Phase 2 (limited domains), Phase 3 (general rollout)

### Medium severity

**Robots.txt compliance at scale**
- What: Every domain has its own robots.txt with different crawl rules.
  Fetching robots.txt for every URL adds latency and load on origin servers.
- Mitigation: Cache robots.txt per domain in Redis (24-hour TTL).
  Parse once, check many times. Respect `Crawl-delay` directives.
- Risk: Redis eviction under memory pressure causes re-fetches. Set
  appropriate maxmemory policy (allkeys-lru).

**Classification taxonomy drift**
- What: New content categories emerge (new technology, new industries)
  that don't map cleanly to the existing IAB taxonomy.
- Mitigation: Monitor average confidence score. Below 0.35 sustained
  over 7 days triggers taxonomy review. LLM fallback handles edge cases
  in the interim. Quarterly editorial review of taxonomy coverage.

**Hot domain rate limiting**
- What: Amazon, CNN, Reddit appear millions of times in URL lists.
  Per-domain rate limits mean these domains are always the bottleneck.
- Mitigation: Configurable per-domain rate limits. Higher limits for
  domains that explicitly permit higher crawl rates. Domain-tier
  classification at ingestion spreads URLs evenly across time windows.

**LLM cost at scale**
- What: LLM fallback at 10% of 1B URLs = 100M LLM calls. At
  $0.0001/call = $10,000/month just for fallback classification.
- Mitigation: Batch 20 URLs per LLM call (10x cost reduction). Long-term:
  fine-tune distilBERT on LLM-labeled data (98% cost reduction).
  Track fallback rate as a first-class cost metric.

### Low severity (but real)

**Legal / Terms of Service compliance**
- Robots.txt is respected by default (implemented). ToS violations
  vary by site — consult legal before crawling authenticated content
  or sites with explicit anti-scraping ToS.

**Schema migration**
- Additive-only evolution is the policy. Any future breaking change
  requires a migration job to backfill existing DynamoDB records before
  deploying the new schema version.

**Docker image size**
- Current image: ~2GB (driven by PyTorch dependency from
  sentence-transformers). Use `torch==2.x+cpu` wheel to reduce to ~1GB.
  Phase 3: ONNX-quantized MiniLM eliminates PyTorch entirely (~200MB image).

---

## 4. Estimates & Timeline

All estimates assume 1 engineer unless noted. Buffer is included (25%).


Phase 0 (complete)     0 weeks    Already deployed
Phase 1 (LocalStack)   2 weeks    1 engineer
Week 1: docker-compose + init scripts + ingester + worker
Week 2: lookup CLI + integration testing + documentation
Phase 2 (AWS MVP)      4 weeks    1-2 engineers
Week 1: VPC + ECR + ECS task definitions + IAM roles
Week 2: SQS + DynamoDB + S3 + ElastiCache on real AWS
Week 3: Read API (Lambda + API Gateway + CloudFront)
Week 4: CloudWatch dashboards + alarms + load test 1M URLs
Phase 3 (Production)   8 weeks    2 engineers + 1 SRE
Week 1-2: Autoscaling + multi-AZ + proxy integration
Week 3-4: CI/CD pipeline + canary deploy + feature flags
Week 5-6: Playwright worker fleet + SPA handling
Week 7-8: Cost optimization + runbooks + SLO review



**Total calendar time (sequential):** ~14 weeks, 1–2 engineers
**Total calendar time (Phase 2+3 parallel with 2 engineers):** ~10 weeks

### Trivial (known, low uncertainty)

- HTML parsing and metadata extraction (done)
- FastAPI endpoint (done)
- Docker containerization (done)
- SQS message publish/consume (boto3, well-documented)
- S3 put/get with gzip (boto3, well-documented)
- DynamoDB PutItem/GetItem (boto3, well-documented)
- CloudWatch log shipping (CloudWatch agent)

### Known but uncertain (needs prototyping)

- Per-domain rate limiting accuracy under high concurrency
- Classification accuracy on long-tail content categories
- Memory consumption of 2,000 concurrent Fargate workers
- Optimal SQS batch size for crawler throughput
- Playwright cold start latency on Fargate

### Unknown (needs discovery)

- Anti-bot bypass success rate with `curl-impersonate` + datacenter proxies
- Actual cost per million URLs in production (projections are estimates)
- DynamoDB hot partition behavior at 270 writes/sec sustained
- LLM fallback rate distribution across real URL lists (may be > 10%)

---

## 5. LocalStack POC

*Detailed in Section 2 Phase 1. Summary here.*

LocalStack lets us run the entire distributed pipeline — SQS, S3,
DynamoDB, Redis — on a laptop with zero AWS spend. It is the mandatory
gate before Phase 2 cloud deployment.

**The one-line migration principle:**

```python
# This is the only difference between LocalStack and real AWS.

# Local (development / POC):
client = boto3.client("sqs", endpoint_url="http://localhost:4566")

# Production (real AWS):
client = boto3.client("sqs")  # endpoint_url unset, uses real AWS
```

Everything else — queue names, bucket names, table names, message
formats, retry logic — is identical between LocalStack and production.

**Why this matters:**
Running the POC on LocalStack proves these properties before Phase 2:
1. The distributed message flow is correct
2. The boto3 API calls use the right parameters
3. Worker fault tolerance (requeue, DLQ) behaves as designed
4. The `app/` extraction and classification code integrates cleanly
   with queue-driven I/O (no hidden assumptions about HTTP context)

**LocalStack POC implementation is scoped and ready.** It will be
implemented as the first activity of Phase 1. The `app/` codebase
requires zero changes. Only new files in `poc/` and `localstack/`
are needed.

---

## 6. Quality Gates

Each phase has hard exit criteria. A phase does not close until all
criteria are met. No exceptions for schedule pressure.

### Phase 0 (complete) 
- [x] All 3 test URLs return structured JSON responses
- [x] Amazon bot-page correctly identified and flagged
- [x] Docker image builds and runs
- [x] Public URL accessible from any network
- [x] `/docs` Swagger UI renders correctly

### Phase 1 (LocalStack POC)
- [ ] `docker-compose up` starts LocalStack + Redis cleanly
- [ ] Init script creates all AWS resources without errors
- [ ] 18/20 test URLs crawled and stored end-to-end
- [ ] DynamoDB records correct and queryable via `lookup.py`
- [ ] Invalid URLs trigger DLQ after 5 retries
- [ ] Worker restart mid-crawl requeues message correctly
- [ ] Switching to real AWS requires only `AWS_ENDPOINT_URL` unset

### Phase 2 (AWS MVP)
- [ ] 1M URLs processed < 5% failure rate
- [ ] API P99 < 200ms under 100 concurrent reads
- [ ] CloudWatch alarms fire correctly on injected failures
- [ ] Cost per million URLs within 20% of $24 projection
- [ ] SLOs met for 1 consecutive week
- [ ] Runbook exists for: DLQ overflow, Redis OOM,
  DynamoDB throttle, Lambda cold-start spike

### Phase 3 (Production)
- [ ] 700M URLs/month processed with all SLOs met
- [ ] Zero-downtime canary deploy validated
- [ ] Rollback tested (previous image, < 5 min)
- [ ] 4 consecutive weeks of SLO compliance
- [ ] Full runbook suite reviewed by SRE

---

## 7. Release Plan

### Deployment strategy

**Phase 1** — local only. No deployment risk. Run on developer laptop.

**Phase 2** — single region, single AZ. Manual deploy via GitHub Actions
pushing to ECR and updating ECS task definition. Rollback: update
task definition to previous image tag (< 2 min).

**Phase 3** — canary deployment:
1. Deploy new image to 5% of ECS tasks
2. Monitor crawl success rate and classification confidence for 1 hour
3. If metrics stable: roll to 25% → 50% → 100% in 1-hour steps
4. If any SLO breaches: roll back to previous task definition

**Feature flags** — LLM fallback is controlled by an environment variable
(`ENABLE_LLM_FALLBACK=true/false`). New classifier models are deployed
in shadow mode (run alongside current model, compare outputs, no traffic
impact) before going live.

**Rollback trigger conditions:**
- Crawl success rate drops below 90% (vs baseline 95%)
- Classification confidence average drops below 0.30
- API P99 latency exceeds 500ms for 5 consecutive minutes
- DLQ size grows by > 10,000 in 1 hour

### CI/CD pipeline (Phase 3)
Push to main branch
│
▼
GitHub Actions
├── python -m pytest (unit tests)
├── docker build (verify image builds)
├── docker run + curl /health (smoke test)
│
▼
Push to ECR (tagged with git SHA)
│
▼
ECS rolling deploy (canary → full)
│
▼
CloudWatch alarm check (15 min soak)
│
├── Alarms clear → deploy complete
└── Alarm fires → auto-rollback to previous task definition


---

## 8. Evaluation Criteria

How we measure whether the system is working at each phase.

### Correctness

| Test | Method | Pass threshold |
|---|---|---|
| Title extraction | Compare to known ground truth for 100 URLs | ≥ 90% match |
| Topic accuracy | Human review of 50 randomly sampled pages | ≥ 80% acceptance |
| Bot detection | Known captcha URLs return `bot_blocked: true` | 100% |
| Schema validity | All responses parse as valid `CrawlResponse` | 100% |

### Performance

| Metric | Measurement | Target |
|---|---|---|
| Single URL P50 latency | 1000 sequential requests | < 3s |
| Throughput (Phase 2) | 5 workers, 100 URLs | > 15 URLs/min/worker |
| API read P99 | Load test 1000 concurrent | < 200ms |
| Docker image size | `docker images` | < 2.5GB (current), < 1GB (ONNX Phase 3) |

### Cost efficiency

| Metric | How to measure | Target |
|---|---|---|
| Cost per million URLs | AWS Cost Explorer / total URLs crawled | < $25 |
| LLM fallback rate | DynamoDB: count topics where source="llm" | < 15% |
| Cache hit rate | CloudFront + Redis hit metrics | > 60% combined |
| Spot interruption rate | ECS task stop reason distribution | < 5% |

### Operational readiness

Before Phase 3 launch, all of the following must exist and be tested:

- Runbook: DLQ overflow response procedure
- Runbook: Redis cache eviction emergency flush
- Runbook: DynamoDB throttle — switch to provisioned capacity
- Runbook: Crawler IP ban — rotate proxy pool
- Runbook: Render / ECS service restart procedure
- Postmortem template for any P1 incident during Phase 2

---


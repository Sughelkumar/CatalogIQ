# CatalogIQ System Design Document

CatalogIQ is an asynchronous, high-throughput product enrichment engine built to clean messy marketplace listings using LLM inference while maintaining system responsiveness, tight concurrency control, and zero redundant execution.

---

## Architecture Overview & Lifecycle Diagram

```text
[ Client / Browser ]
        │
        │ 1. POST /api/jobs (CSV JSON Payload)
        ▼
[ FastAPI App (main.py) ] ──────────► [ SQLite DB ] (Creates Job + Products)
        │
        │ 2. Dispatches Background asyncio.Task
        ▼
[ Pipeline Engine (pipeline.py) ]
        │
        ├──────────────────────────────────────────────┐
        │ 3. Compute SHA-256 Content Hash             │
        ▼                                              ▼
[ SQLite DB (enrichment_cache) ]             [ Single-Flight Event Map ]
 (Historical Cache Hit?)                      (In-Flight Duplicate?)
        │                                              │
        ├─ YES ──► [ Instant Return ]                  ├─ YES ──► [ Wait on Event & Reuse ]
        │                                              │
        └─ NO ─────────────────────────────────────────┴─ NO
                                 │
                                 │ 4. Acquire Semaphore Token
                                 ▼
                    [ asyncio.Semaphore(N) ]
                                 │
                                 │ 5. Execute LLM Call (Up to 3 Retries w/ Backoff)
                                 ▼
                     [ LLM Provider Interface ]
                   (Mock / Groq / Gemini / Ollama)
                                 │
                                 │ 6. Validate Category & Save Cache/Product
                                 ▼
                     [ SQLite DB ] (Status: enriched)
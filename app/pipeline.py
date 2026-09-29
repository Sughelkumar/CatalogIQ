import asyncio
import hashlib
import json
import logging
from typing import Dict, Any, Optional
from app.config import settings
from app.models import VALID_CATEGORIES, EnrichmentOutput
from app.llm import get_llm_provider
from app.database import db_get_cache, db_save_cache, db_save_product, get_db

class MetricsManager:
    def __init__(self):
        self.llm_calls_total = 0
        self.llm_errors_total = 0
        self.max_concurrent_llm_calls = 0
        self._current = 0
        self._lock = asyncio.Lock()

    async def record_start(self):
        async with self._lock:
            self.llm_calls_total += 1
            self._current += 1
            if self._current > self.max_concurrent_llm_calls:
                self.max_concurrent_llm_calls = self._current

    async def record_finish(self, failed: bool):
        async with self._lock:
            self._current -= 1
            if failed:
                self.llm_errors_total += 1

metrics = MetricsManager()

def compute_content_hash(raw_title: str, raw_description: Optional[str]) -> str:
    combined = f"{raw_title} {raw_description or ''}"
    normalized = " ".join(combined.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

class PipelineEngine:
    def __init__(self):
        self.provider = get_llm_provider()
        self.semaphore = asyncio.Semaphore(settings.LLM_CONCURRENCY)
        # Lock and result table for in-flight deduplication
        self._in_flight_events: Dict[str, asyncio.Event] = {}
        self._in_flight_results: Dict[str, Dict[str, Any]] = {}
        self._map_lock = asyncio.Lock()

    async def process_product(self, raw_title: str, raw_description: Optional[str]) -> Dict[str, Any]:
        content_hash = compute_content_hash(raw_title, raw_description)

        # 1. Check persistent SQLite cache
        cached = await db_get_cache(content_hash)
        if cached:
            return {"status": "cache_hit", "data": cached}

        # 2. Single-flight coalescing for concurrent duplicate requests
        async with self._map_lock:
            if content_hash in self._in_flight_events:
                event = self._in_flight_events[content_hash]
                is_leader = False
            else:
                event = asyncio.Event()
                self._in_flight_events[content_hash] = event
                is_leader = True

        if not is_leader:
            await event.wait()
            res = self._in_flight_results.get(content_hash, {})
            if res.get("status") == "success":
                return {"status": "cache_hit", "data": res["data"]}
            # If the primary request failed, re-attempt execution
            return await self.process_product(raw_title, raw_description)

        # 3. Primary execution with retries and concurrency limits
        result_data = None
        last_error = None

        async with self.semaphore:
            for attempt in range(4): # 1 initial + up to 3 retries
                await metrics.record_start()
                try:
                    output: EnrichmentOutput = await self.provider.enrich(raw_title, raw_description)
                    
                    if output.category not in VALID_CATEGORIES:
                        raise ValueError(f"Category '{output.category}' not in valid options")
                    
                    result_data = output.model_dump()
                    await metrics.record_finish(failed=False)
                    break
                except Exception as e:
                    last_error = str(e)
                    await metrics.record_finish(failed=True)
                    if attempt < 3:
                        await asyncio.sleep(0.2 * (2 ** attempt)) # 200ms, 400ms, 800ms

        # 4. Save cache and release waiting requests
        async with self._map_lock:
            if result_data:
                await db_save_cache(content_hash, result_data)
                self._in_flight_results[content_hash] = {"status": "success", "data": result_data}
                self._in_flight_events[content_hash].set()
                del self._in_flight_events[content_hash]
                return {"status": "enriched", "data": result_data}
            else:
                self._in_flight_results[content_hash] = {"status": "failed", "error": last_error}
                self._in_flight_events[content_hash].set()
                del self._in_flight_events[content_hash]
                return {"status": "failed", "error": last_error}

pipeline_engine = PipelineEngine()

async def run_job_background(job_id: str, products: list):
    # Set job status to running
    def _start_job():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE jobs SET status = 'running', started_at = datetime('now') WHERE id = ?", (job_id,))
        conn.commit()
        conn.close()
    await asyncio.to_thread(_start_job)

    done = 0
    failed = 0
    cache_hits = 0

    async def _handle_item(p):
        nonlocal done, failed, cache_hits
        res = await pipeline_engine.process_product(p["raw_title"], p.get("raw_description"))
        
        prod_record = {
            "sku": p["sku"],
            "raw_title": p["raw_title"],
            "raw_description": p.get("raw_description"),
            "status": "failed" if res["status"] == "failed" else "enriched",
            "error": res.get("error")
        }
        
        if res["status"] == "failed":
            failed += 1
        else:
            done += 1
            if res["status"] == "cache_hit":
                cache_hits += 1
            data = res["data"]
            prod_record.update({
                "clean_title": data["clean_title"],
                "category": data["category"],
                "brand": data.get("brand"),
                "tags": data.get("tags", [])
            })
            
        await db_save_product(prod_record)

        # Update Job counter in SQLite
        def _update_job():
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE jobs SET done = ?, failed = ?, cache_hits = ? WHERE id = ?",
                (done, failed, cache_hits, job_id)
            )
            conn.commit()
            conn.close()
        await asyncio.to_thread(_update_job)

    # Process products concurrently within the job
    await asyncio.gather(*[_handle_item(p) for p in products])

    # Complete job
    def _finish_job():
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE jobs SET status = 'completed', finished_at = datetime('now') WHERE id = ?", (job_id,))
        conn.commit()
        conn.close()
    await asyncio.to_thread(_finish_job)
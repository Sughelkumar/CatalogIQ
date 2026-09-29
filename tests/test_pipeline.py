import pytest
import asyncio
from app.config import settings
from app.pipeline import pipeline_engine, metrics
from app.database import init_db

@pytest.fixture(autouse=True)
def setup_database():
    init_db()

@pytest.mark.asyncio
async def test_concurrency_and_retries():
    # Verify concurrency limit remains bounded
    tasks = [
        pipeline_engine.process_product(f"Sample Item {i}", "description")
        for i in range(20)
    ]
    results = await asyncio.gather(*tasks)
    
    assert len(results) == 20
    assert metrics.max_concurrent_llm_calls <= settings.LLM_CONCURRENCY

@pytest.mark.asyncio
async def test_deduplication():
    # Concurrent duplicates hit the single-flight coalescing cache
    t1 = pipeline_engine.process_product("AMUL butter 500G", "pck of 2")
    t2 = pipeline_engine.process_product("  amul   butter 500g ", "pck of 2")
    
    r1, r2 = await asyncio.gather(t1, t2)
    
    assert r1["status"] in ["enriched", "cache_hit"]
    assert r2["status"] == "cache_hit"
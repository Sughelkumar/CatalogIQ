import asyncio
import random
from typing import Optional
from app.llm.base import BaseLLMProvider
from app.models import EnrichmentOutput

class MockLLMProvider(BaseLLMProvider):
    def __init__(self, latency_ms: int, failure_rate: float):
        self.latency_ms = latency_ms
        self.failure_rate = failure_rate

    async def enrich(self, raw_title: str, raw_description: Optional[str] = None) -> EnrichmentOutput:
        await asyncio.sleep(self.latency_ms / 1000.0)

        if random.random() < self.failure_rate:
            raise RuntimeError("Mock LLM simulated failure")

        combined = f"{raw_title} {raw_description or ''}".lower()

        # Rule-based categorization for mock provider
        category = "Other"
        if any(w in combined for w in ["butter", "milk", "cheese", "rice", "dal", "oil"]):
            category = "Groceries"
        elif any(w in combined for w in ["coke", "pepsi", "juice", "tea", "coffee"]):
            category = "Beverages"
        elif any(w in combined for w in ["soap", "shampoo", "cream", "lotion"]):
            category = "Personal Care"
        elif any(w in combined for w in ["shirt", "jeans", "shoes", "dress"]):
            category = "Fashion"
        elif any(w in combined for w in ["phone", "laptop", "cable", "usb"]):
            category = "Electronics"

        brand = None
        if "amul" in combined:
            brand = "Amul"
        elif "nestle" in combined:
            brand = "Nestle"

        words = [w for w in combined.split() if len(w) > 2][:5]

        return EnrichmentOutput(
            clean_title=raw_title.strip().title(),
            category=category,
            brand=brand,
            tags=[w.lower() for w in words]
        )
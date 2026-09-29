from abc import ABC, abstractmethod
from typing import Optional
from app.models import EnrichmentOutput

class BaseLLMProvider(ABC):
    @abstractmethod
    async def enrich(self, raw_title: str, raw_description: Optional[str] = None) -> EnrichmentOutput:
        pass
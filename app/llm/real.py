import json
import httpx
from typing import Optional
from app.llm.base import BaseLLMProvider
from app.models import EnrichmentOutput, VALID_CATEGORIES

class GroqLLMProvider(BaseLLMProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.url = "https://api.groq.com/openai/v1/chat/completions"

    async def enrich(self, raw_title: str, raw_description: Optional[str] = None) -> EnrichmentOutput:
        prompt = f"""Extract product metadata. Return strictly JSON with keys:
clean_title (string), category (must be exactly one of: {', '.join(VALID_CATEGORIES)}), brand (string or null), tags (list of max 5 lowercase strings).

Raw Title: {raw_title}
Raw Description: {raw_description or ''}"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"}
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(self.url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = json.loads(data["choices"][0]["message"]["content"])
            return EnrichmentOutput(**content)
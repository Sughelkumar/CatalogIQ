import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "mock")
    MOCK_LATENCY_MS: int = int(os.getenv("MOCK_LATENCY_MS", "200"))
    MOCK_FAILURE_RATE: float = float(os.getenv("MOCK_FAILURE_RATE", "0.1"))
    LLM_CONCURRENCY: int = int(os.getenv("LLM_CONCURRENCY", "5"))
    
    # Real LLM API keys
    GROQ_API_KEY: str | None = os.getenv("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")
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")

settings = Settings()
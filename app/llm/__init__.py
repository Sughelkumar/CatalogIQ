from app.config import settings
from app.llm.base import BaseLLMProvider
from app.llm.mock import MockLLMProvider
from app.llm.real import GroqLLMProvider

def get_llm_provider() -> BaseLLMProvider:
    provider_name = settings.LLM_PROVIDER.lower()
    if provider_name == "mock":
        return MockLLMProvider(settings.MOCK_LATENCY_MS, settings.MOCK_FAILURE_RATE)
    elif provider_name == "groq":
        if not settings.GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY environment variable missing")
        return GroqLLMProvider(settings.GROQ_API_KEY)
    else:
        # Fallback to Mock
        return MockLLMProvider(settings.MOCK_LATENCY_MS, settings.MOCK_FAILURE_RATE)
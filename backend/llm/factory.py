"""Factory to create LLM provider instances from configuration."""
from typing import Optional
from backend.llm.base import LLMProvider
from backend.llm.fastflowlm import FastFlowLMProvider
from backend.llm.ollama import OllamaProvider
from backend.llm.vllm import VLLMProvider
from backend.llm.openai_adapter import OpenAIAdapterProvider
from backend.llm.anthropic import AnthropicProvider
from backend.llm.lmstudio import LMStudioProvider
from backend.llm.jan import JanProvider
from backend.llm.localai import LocalAIProvider
import backend.config as config


_PROVIDER_CLASSES = {
    "fastflowlm": FastFlowLMProvider,
    "ollama": OllamaProvider,
    "vllm": VLLMProvider,
    "openai": lambda: OpenAIAdapterProvider(
        base_url=config.OPENAI_BASE_URL,
        api_key=config.OPENAI_API_KEY,
        model=config.OPENAI_MODEL,
    ),
    "anthropic": AnthropicProvider,
    "lmstudio": LMStudioProvider,
    "jan": JanProvider,
    "localai": LocalAIProvider,
}


def create_provider(name: str) -> Optional[LLMProvider]:
    """Create a provider instance by name."""
    factory = _PROVIDER_CLASSES.get(name)
    if factory is None:
        return None
    if callable(factory) and not isinstance(factory, type):
        return factory()
    return factory()


def get_all_provider_names() -> list[str]:
    """Return list of all available provider names."""
    return list(_PROVIDER_CLASSES.keys())

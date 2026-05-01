"""Provider registry for runtime provider discovery."""
from typing import Optional
from backend.llm.base import LLMProvider
from backend.llm.factory import create_provider, get_all_provider_names
import threading


_registry: dict[str, LLMProvider] = {}
_lock = threading.Lock()


def get_provider(name: str) -> Optional[LLMProvider]:
    """Get or create a cached provider instance."""
    with _lock:
        if name not in _registry:
            _registry[name] = create_provider(name) or _registry.get(name)
        return _registry.get(name)


def list_providers() -> list[dict]:
    """Return metadata for all available providers."""
    names = get_all_provider_names()
    result = []
    for name in names:
        provider = get_provider(name)
        if provider:
            result.append({
                "name": provider.name,
                "supports_images": provider.supports_images,
            })
    return result


def clear_cache() -> None:
    """Clear the provider cache (useful for config reloads)."""
    with _lock:
        for p in _registry.values():
            p.close()
        _registry.clear()

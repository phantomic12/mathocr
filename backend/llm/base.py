"""Abstract base class for LLM providers."""
from abc import ABC, abstractmethod
from typing import Optional


class LLMProvider(ABC):
    """Abstract LLM provider interface."""

    name: str = "base"
    supports_images: bool = True

    @abstractmethod
    def complete(self, messages: list[dict], **kwargs) -> str:
        """Send a completion request and return the raw text response."""

    def stream_complete(self, messages: list[dict], callback, **kwargs):
        """Stream a completion, calling callback(text, usage) for each token chunk.

        The callback receives:
          - text: accumulated full response string so far (build it from chunks)
          - usage: dict with prompt_tokens, completion_tokens, or None if unavailable

        Default implementation falls back to non-streaming complete().
        Override in providers that support streaming.
        """
        # Fallback: non-streaming
        result = self.complete(messages, **kwargs)
        usage = getattr(self, "_last_usage", None)
        callback(result, usage)
        return result

    @abstractmethod
    def get_model_id(self) -> str:
        """Return the model string used in API calls."""

    def close(self) -> None:
        """Cleanup any open connections. Override if needed."""
        pass


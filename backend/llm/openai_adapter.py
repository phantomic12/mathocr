"""OpenAI-compatible adapter (OpenAI, LM Studio, Jan, LocalAI, etc.)."""
import openai
from backend.llm.base import LLMProvider
import backend.config as config


class OpenAIAdapterProvider(LLMProvider):
    name = "openai_adapter"
    supports_images = True

    def __init__(self, base_url: str, api_key: str, model: str):
        self.client = openai.OpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    def complete(self, messages: list[dict], **kwargs) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs,
        )
        return response.choices[0].message.content or ""

    def get_model_id(self) -> str:
        return self.model

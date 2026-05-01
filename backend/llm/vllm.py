"""vLLM adapter."""
import openai
from backend.llm.base import LLMProvider
import backend.config as config


class VLLMProvider(LLMProvider):
    name = "vllm"
    supports_images = True

    def __init__(self):
        self.client = openai.OpenAI(
            base_url=config.VLLM_BASE_URL,
            api_key=config.VLLM_API_KEY,
        )
        self.model = config.VLLM_MODEL

    def complete(self, messages: list[dict], **kwargs) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs,
        )
        return response.choices[0].message.content or ""

    def get_model_id(self) -> str:
        return self.model

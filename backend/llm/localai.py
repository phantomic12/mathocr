"""LocalAI adapter."""
from backend.llm.openai_adapter import OpenAIAdapterProvider
import backend.config as config


class LocalAIProvider(OpenAIAdapterProvider):
    name = "localai"
    supports_images = True

    def __init__(self):
        super().__init__(
            base_url=config.LOCALAI_BASE_URL,
            api_key=config.LOCALAI_API_KEY,
            model=config.LOCALAI_MODEL,
        )

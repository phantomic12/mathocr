"""Jan adapter."""
from backend.llm.openai_adapter import OpenAIAdapterProvider
import backend.config as config


class JanProvider(OpenAIAdapterProvider):
    name = "jan"
    supports_images = True

    def __init__(self):
        super().__init__(
            base_url=config.JAN_BASE_URL,
            api_key=config.JAN_API_KEY,
            model=config.JAN_MODEL,
        )

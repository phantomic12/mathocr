"""LM Studio adapter."""
from backend.llm.openai_adapter import OpenAIAdapterProvider
import backend.config as config


class LMStudioProvider(OpenAIAdapterProvider):
    name = "lmstudio"
    supports_images = True

    def __init__(self):
        super().__init__(
            base_url=config.LMSTUDIO_BASE_URL,
            api_key=config.LMSTUDIO_API_KEY,
            model=config.LMSTUDIO_MODEL,
        )

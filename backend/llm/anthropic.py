"""Anthropic adapter using their official SDK."""
from anthropic import Anthropic
from backend.llm.base import LLMProvider
import backend.config as config


class AnthropicProvider(LLMProvider):
    name = "anthropic"
    supports_images = True

    def __init__(self):
        self.client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.model = config.ANTHROPIC_MODEL

    def complete(self, messages: list[dict], **kwargs) -> str:
        # Convert messages to Anthropic format
        text_parts = []
        image_blocks = []
        
        for msg in messages:
            if isinstance(msg.get("content"), list):
                for part in msg["content"]:
                    if part.get("type") == "text":
                        text_parts.append(part["text"])
                    elif part.get("type") == "image_url":
                        image_blocks.append({
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": part["image_url"]["url"].split(",")[-1],
                            }
                        })
            else:
                text_parts.append(msg.get("content", ""))
        
        system = next((m["content"] for m in messages if m.get("role") == "system"), "")
        user_text = next((m["content"] for m in messages if m.get("role") == "user"), "\n".join(text_parts))
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user_text}],
            **kwargs,
        )
        return response.content[0].text

    def get_model_id(self) -> str:
        return self.model

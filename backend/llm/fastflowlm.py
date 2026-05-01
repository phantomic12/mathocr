"""FastFlowLM (Qwen3.5-VL on NPU) adapter."""
import time
import openai
from backend.llm.base import LLMProvider
import backend.config as config


class FastFlowLMProvider(LLMProvider):
    name = "fastflowlm"
    supports_images = True

    def __init__(self):
        self.client = openai.OpenAI(
            base_url=str(config.FASTFLOWLM_BASE_URL).rstrip("/"),
            api_key=config.FASTFLOWLM_API_KEY,
        )
        self.model = config.FASTFLOWLM_MODEL
        self._last_usage = None

    def complete(self, messages: list[dict], **kwargs) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs,
        )
        self._last_usage = None
        if hasattr(response, "usage") and response.usage is not None:
            self._last_usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            }
        return response.choices[0].message.content or ""

    def stream_complete(self, messages: list[dict], callback, **kwargs):
        accumulated = ""
        t0 = time.time()
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=True,
            **kwargs,
        )
        for chunk in response:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                accumulated += delta
                elapsed = time.time() - t0
                # Compute live token speed
                char_count = len(accumulated)
                # Rough estimate: ~4 chars per token for Qwen
                tok_est = max(1, char_count // 4)
                tok_per_sec = tok_est / elapsed if elapsed > 0 else 0
                self._last_usage = {
                    "prompt_tokens": 0,
                    "completion_tokens": tok_est,
                    "tok_per_sec": round(tok_per_sec, 1),
                }
                callback(accumulated, self._last_usage)
        return accumulated

    def get_model_id(self) -> str:
        return self.model

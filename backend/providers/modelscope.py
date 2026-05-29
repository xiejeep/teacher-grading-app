import base64
import requests

import backend.config as config
from backend.providers.base import BaseAIProvider, ProviderResponse


BASE_URL = "https://api-inference.modelscope.cn/v1"
MODELS_WITH_THINKING = {
    "moonshotai/Kimi-K2.6:DashScope",
    "moonshotai/Kimi-K2.5:DashScope",
}


class ModelScopeProvider(BaseAIProvider):

    def __init__(self):
        self.model = config.MODELSCOPE_MODEL
        self.api_url = f"{BASE_URL}/chat/completions"

    @property
    def supports_thinking(self) -> bool:
        return self.model in MODELS_WITH_THINKING

    def _request(self, messages: list[dict], max_tokens: int,
                 response_format: dict | None = None) -> ProviderResponse:
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
        }

        if self.supports_thinking:
            payload["thinking"] = {"type": "enabled"}

        if response_format:
            payload["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {config.MODELSCOPE_API_KEY}",
            "Content-Type": "application/json",
        }

        resp = requests.post(self.api_url, json=payload, headers=headers, timeout=300)
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]
        return ProviderResponse(
            content=choice["message"]["content"],
            finish_reason=choice.get("finish_reason", "unknown"),
            usage=data.get("usage", {}),
        )

    def chat_completion(
        self,
        system_prompt: str,
        user_content: list[dict],
        max_tokens: int = 32768,
        response_format: dict | None = None,
    ) -> ProviderResponse:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        return self._request(messages, max_tokens, response_format)

    def chat_completion_with_messages(
        self,
        messages: list[dict],
        max_tokens: int = 32768,
        response_format: dict | None = None,
    ) -> ProviderResponse:
        return self._request(messages, max_tokens, response_format)

    @staticmethod
    def build_image_content(image_path: str) -> dict:
        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{img_b64}",
            },
        }

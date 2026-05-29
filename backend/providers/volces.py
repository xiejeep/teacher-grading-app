import base64
import requests
from PIL import Image

import backend.config as config
from backend.providers.base import BaseAIProvider, ProviderResponse


API_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"


class VolcesProvider(BaseAIProvider):

    def _request(self, messages: list[dict], max_tokens: int,
                 response_format: dict | None = None) -> ProviderResponse:
        payload = {
            "model": config.VOLCES_EP_ID,
            "thinking": {"type": "enabled"},
            "max_tokens": max_tokens,
            "temperature": 0,
            "messages": messages,
        }
        if response_format:
            payload["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {config.VOLCES_API_KEY}",
            "Content-Type": "application/json",
        }

        resp = requests.post(API_URL, json=payload, headers=headers, timeout=300)
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
        img = Image.open(image_path)
        img_w, img_h = img.size
        total_pixels = img_w * img_h

        with open(image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        return {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{img_b64}",
                "image_pixel_limit": {
                    "min_pixels": int(total_pixels * 0.92),
                    "max_pixels": int(total_pixels * 1.08),
                },
            },
        }

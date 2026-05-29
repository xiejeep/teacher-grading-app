from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ProviderResponse:
    content: str
    finish_reason: str
    usage: dict


class BaseAIProvider(ABC):

    @abstractmethod
    def chat_completion(
        self,
        system_prompt: str,
        user_content: list[dict],
        max_tokens: int = 32768,
        response_format: dict | None = None,
    ) -> ProviderResponse:
        ...

    @abstractmethod
    def chat_completion_with_messages(
        self,
        messages: list[dict],
        max_tokens: int = 32768,
        response_format: dict | None = None,
    ) -> ProviderResponse:
        ...

    @abstractmethod
    def build_image_content(self, image_path: str) -> dict:
        ...

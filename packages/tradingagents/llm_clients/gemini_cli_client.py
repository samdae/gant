from typing import Any

from .antigravity_client import ChatAntigravity
from .base_client import BaseLLMClient


class GeminiCLIClient(BaseLLMClient):
    """Client using Gemini CLI OAuth credentials."""

    def get_llm(self) -> Any:
        kwargs = dict(self.kwargs)
        kwargs["auth_mode"] = "gemini-cli"
        return ChatAntigravity(model=self.model, **kwargs)

    def validate_model(self) -> bool:
        return True

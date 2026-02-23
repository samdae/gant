"""OpenAI Codex (GPT-5.3) LLM client via langchain-openai + oauth-codex token.

Uses oauth-codex for OAuth PKCE authentication, then passes the access token
to langchain-openai's ChatOpenAI for full tool calling / structured output support.
"""

import logging
from typing import Any

from .base_client import BaseLLMClient

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gpt-5.3-codex"


def _get_codex_access_token() -> str:
    """Obtain a valid access token from oauth-codex (cached or refreshed)."""
    from oauth_codex import Client

    client = Client(authenticate_on_init=True)
    return client.get_access_token()


class CodexClient(BaseLLMClient):
    """Client for OpenAI Codex (GPT-5.3) via langchain-openai + oauth-codex."""

    def get_llm(self) -> Any:
        from langchain_openai import ChatOpenAI

        token = _get_codex_access_token()

        return ChatOpenAI(
            model=self.model or _DEFAULT_MODEL,
            api_key=token,
            **self.kwargs,
        )

    def validate_model(self) -> bool:
        return True

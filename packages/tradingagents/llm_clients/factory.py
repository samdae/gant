from typing import Any, Optional

from .base_client import BaseLLMClient
from .antigravity_client import AntigravityClient
from .gemini_cli_client import GeminiCLIClient
from .codex_client import CodexClient


def create_llm_client(
    provider: str,
    model: str,
    base_url: Optional[str] = None,
    **kwargs,
) -> BaseLLMClient:
    """Create an LLM client instance.

    Args:
        provider: "gemini-cli" (default), "antigravity", or "codex"
        model: Model name (e.g. gemini-3-pro-high, gpt-5.3-codex)
        base_url: Not used, kept for interface compatibility
        **kwargs: Additional arguments

    Returns:
        Configured LLM client
    """
    provider_lower = provider.lower()

    if provider_lower == "gemini-cli":
        return GeminiCLIClient(model, base_url, **kwargs)

    if provider_lower == "antigravity":
        return AntigravityClient(model, base_url, **kwargs)

    if provider_lower == "codex":
        return CodexClient(model, base_url, **kwargs)

    raise ValueError(
        f"Unsupported LLM provider: '{provider}'. "
        f"Supported: 'gemini-cli', 'antigravity', 'codex'."
    )

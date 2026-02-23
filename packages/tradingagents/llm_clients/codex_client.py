"""OpenAI Codex (GPT-5.3) LLM client via oauth-codex SDK.

Uses OAuth PKCE authentication. First run opens browser for login;
subsequent runs use cached tokens (~/.oauth_codex/auth.json or keyring).
"""

import logging
from typing import Any, Dict, List, Optional, Union, Callable

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from .base_client import BaseLLMClient

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gpt-5.3-codex"


class ChatCodex(BaseChatModel):
    """LangChain chat model backed by oauth-codex Client."""

    model: str = _DEFAULT_MODEL
    _client: Any = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        try:
            from oauth_codex import Client
            self._client = Client(authenticate_on_init=True)
        except ImportError:
            raise ImportError(
                "oauth-codex package required. Install: pip install oauth-codex"
            )

    @property
    def _llm_type(self) -> str:
        return "codex"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        api_messages: List[Dict[str, Any]] = []
        for m in messages:
            if isinstance(m, SystemMessage):
                api_messages.append({"role": "system", "content": m.content})
            elif isinstance(m, AIMessage):
                api_messages.append({"role": "assistant", "content": m.content or ""})
            else:
                api_messages.append({"role": "user", "content": m.content})

        try:
            text = self._client.generate(api_messages, model=self.model)
        except Exception:
            logger.exception("Codex generate failed")
            raise

        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=text))]
        )


class CodexClient(BaseLLMClient):
    """Client for OpenAI Codex (GPT-5.3) via oauth-codex."""

    def get_llm(self) -> Any:
        return ChatCodex(model=self.model, **self.kwargs)

    def validate_model(self) -> bool:
        return True

"""OpenAI Codex (GPT-5.3) LLM client via oauth-codex Responses API.

Uses oauth-codex's internal engine to call the Responses API directly,
bypassing Cloudflare and supporting full tool calling for LangChain/LangGraph.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult

from .base_client import BaseLLMClient

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gpt-5.3-codex"


class ChatCodex(BaseChatModel):
    """LangChain chat model using oauth-codex Responses API with tool support."""

    model: str = _DEFAULT_MODEL
    _engine: Any = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from oauth_codex import Client

        client = Client(authenticate_on_init=True)
        client.refresh_if_needed()
        self._engine = client._engine

    @property
    def _llm_type(self) -> str:
        return "codex"

    def bind_tools(self, tools: list, **kwargs) -> Any:
        formatted = []
        for tool in tools:
            if hasattr(tool, "name") and hasattr(tool, "args_schema"):
                schema = (
                    tool.args_schema.model_json_schema()
                    if tool.args_schema
                    else {"type": "object", "properties": {}}
                )
                schema.pop("title", None)
                formatted.append(
                    {
                        "type": "function",
                        "name": tool.name,
                        "description": getattr(tool, "description", "") or "",
                        "parameters": schema,
                    }
                )
            elif isinstance(tool, dict):
                if "function" in tool:
                    fn = tool["function"]
                    formatted.append(
                        {
                            "type": "function",
                            "name": fn["name"],
                            "description": fn.get("description", ""),
                            "parameters": fn.get(
                                "parameters", {"type": "object", "properties": {}}
                            ),
                        }
                    )
                else:
                    formatted.append(tool)
            else:
                from langchain_core.utils.function_calling import convert_to_openai_tool

                oai = convert_to_openai_tool(tool)
                fn = oai["function"]
                formatted.append(
                    {
                        "type": "function",
                        "name": fn["name"],
                        "description": fn.get("description", ""),
                        "parameters": fn.get(
                            "parameters", {"type": "object", "properties": {}}
                        ),
                    }
                )

        return self.bind(tools=formatted, **kwargs)

    @staticmethod
    def _convert_messages(messages: List[BaseMessage]) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                result.append({"role": "developer", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                result.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                if msg.tool_calls:
                    if msg.content:
                        result.append(
                            {
                                "type": "message",
                                "role": "assistant",
                                "content": [
                                    {"type": "output_text", "text": msg.content}
                                ],
                            }
                        )
                    for tc in msg.tool_calls:
                        args = tc.get("args", {})
                        result.append(
                            {
                                "type": "function_call",
                                "name": tc["name"],
                                "arguments": json.dumps(args)
                                if isinstance(args, dict)
                                else str(args),
                                "call_id": tc.get("id", ""),
                            }
                        )
                else:
                    result.append({"role": "assistant", "content": msg.content or ""})
            elif isinstance(msg, ToolMessage):
                content = msg.content
                if not isinstance(content, str):
                    content = json.dumps(content)
                result.append(
                    {
                        "type": "function_call_output",
                        "call_id": msg.tool_call_id,
                        "output": content,
                    }
                )
        return result

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        input_msgs = self._convert_messages(messages)
        tools = kwargs.pop("tools", None)

        create_kwargs: Dict[str, Any] = {
            "model": self.model,
            "input": input_msgs,
        }
        if tools:
            create_kwargs["tools"] = tools

        try:
            response = self._engine.responses.create(**create_kwargs)
        except Exception:
            logger.exception("Codex responses.create failed")
            raise

        content = ""
        tool_calls = []

        for item in response.output:
            item_type = item.get("type", "")
            if item_type == "message":
                for part in item.get("content", []):
                    if part.get("type") == "output_text":
                        content += part.get("text", "")
            elif item_type == "function_call":
                try:
                    args = json.loads(item.get("arguments", "{}"))
                except (json.JSONDecodeError, TypeError):
                    args = {}
                tool_calls.append(
                    {
                        "name": item.get("name", ""),
                        "args": args,
                        "id": item.get("call_id", ""),
                        "type": "tool_call",
                    }
                )

        ai_msg = AIMessage(content=content, tool_calls=tool_calls)
        return ChatResult(generations=[ChatGeneration(message=ai_msg)])


class CodexClient(BaseLLMClient):
    """Client for OpenAI Codex (GPT-5.3) via oauth-codex Responses API."""

    def get_llm(self) -> Any:
        return ChatCodex(model=self.model or _DEFAULT_MODEL, **self.kwargs)

    def validate_model(self) -> bool:
        return True

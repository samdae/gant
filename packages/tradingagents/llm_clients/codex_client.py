"""LangChain adapter for the official, ChatGPT-authenticated Codex runtime."""

import json
import os
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid4

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, messages_to_dict
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool
from openai_codex import ApprovalMode, Codex, CodexConfig, Sandbox

from .base_client import BaseLLMClient


class ChatCodex(BaseChatModel):
    model: str = "gpt-6.2-sol"

    @property
    def _llm_type(self) -> str:
        return "codex"

    def bind_tools(self, tools: list, **kwargs: Any):
        functions = []
        for tool in tools:
            if isinstance(tool, dict) and "name" in tool and "parameters" in tool:
                functions.append(tool)
            else:
                functions.append(convert_to_openai_tool(tool)["function"])
        return self.bind(tools=functions, **kwargs)

    def _generate(self, messages: list[BaseMessage], stop=None, run_manager=None, **kwargs):
        tools = kwargs.get("tools") or []
        instructions = [
            "You are a component of TradingAgents. Answer the supplied conversation. "
            "The host runs all tools. Never use local files, shell, web or Codex tools."
        ]
        history = []
        for message in messages:
            if isinstance(message, SystemMessage):
                instructions.append(str(message.content))
            else:
                history.append(message)

        schema = None
        if tools:
            instructions.append(
                "Request needed host tools via calls with JSON-encoded arguments. "
                "Use existing tool results when available. Return an empty calls array "
                "and your final answer in content when finished. Available tools: "
                + json.dumps(tools, ensure_ascii=False)
            )
            schema = {
                "type": "object", "additionalProperties": False,
                "required": ["content", "calls"],
                "properties": {
                    "content": {"type": "string"},
                    "calls": {"type": "array", "items": {
                        "type": "object", "additionalProperties": False,
                        "required": ["name", "arguments"],
                        "properties": {
                            "name": {"type": "string", "enum": [t["name"] for t in tools]},
                            "arguments": {"type": "string"},
                        },
                    }},
                },
            }

        prompt = json.dumps(messages_to_dict(history), ensure_ascii=False, default=str)
        with TemporaryDirectory() as cwd, Codex(CodexConfig(cwd=cwd)) as codex:
            account = codex.account().account
            if account is None or account.root.type != "chatgpt":
                raise RuntimeError("TradingAgents requires ChatGPT sign-in. Run codex login.")
            thread = codex.thread_start(
                model=self.model, model_provider="openai", cwd=cwd, ephemeral=True,
                sandbox=Sandbox.read_only, approval_mode=ApprovalMode.deny_all,
                config={"features.shell_tool": False, "web_search": "disabled"},
                base_instructions="\n\n".join(instructions),
            )
            result = thread.run(prompt, output_schema=schema)
            content = result.final_response
            if result.status.value != "completed" or not content:
                raise RuntimeError(f"Codex returned no answer (turn status: {result.status}).")

        calls = []
        if tools:
            answer = json.loads(content)
            content = answer["content"]
            for call in answer["calls"]:
                args = json.loads(call["arguments"])
                if not isinstance(args, dict):
                    raise ValueError("Codex tool arguments must be a JSON object")
                calls.append({"name": call["name"], "args": args, "id": uuid4().hex})

        message = AIMessage(content=content, tool_calls=calls)
        return ChatResult(generations=[ChatGeneration(message=message)])


class CodexClient(BaseLLMClient):
    def get_llm(self) -> ChatCodex:
        return ChatCodex(model=self.model or os.getenv("CODEX_MODEL", "gpt-6.2-sol"), **self.kwargs)

    def validate_model(self) -> bool:
        return True

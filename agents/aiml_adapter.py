"""
Custom AIML API Adapter for Band SDK
Uses OpenAI-compatible endpoint at api.aimlapi.com
Pattern 2: Adapter manages tool loop
"""
import json
import logging
import re
import requests
from typing import Any
from thenvoi.core.simple_adapter import SimpleAdapter
from thenvoi.core.protocols import AgentToolsProtocol
from thenvoi.core.types import PlatformMessage
from thenvoi.runtime.prompts import render_system_prompt

logger = logging.getLogger(__name__)

MAX_TOOL_ITERS = 10


def sanitize_name(name: str) -> str:
    """Sanitize participant name for OpenAI name field."""
    return re.sub(r'[\s<|\\/>]+', '_', name)


class AIMLApiAdapter(SimpleAdapter):
    """
    Custom Band SDK adapter using AIML API (OpenAI-compatible).
    Supports: nvidia/nemotron-3-nano-omni-30b-a3b-reasoning and others.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning",
        custom_section: str = "",
        system_prompt: str = None,
        max_tokens: int = 4096,
        base_url: str = "https://api.aimlapi.com/v1",
    ):
        super().__init__(history_converter=None)
        self.api_key = api_key
        self.model = model
        self.custom_section = custom_section
        self._custom_system_prompt = system_prompt
        self.max_tokens = max_tokens
        self.base_url = base_url.rstrip('/')
        self._system_prompt = ""
        self._room_messages: dict[str, list] = {}

    async def on_started(self, agent_name: str, agent_description: str) -> None:
        await super().on_started(agent_name, agent_description)
        if self._custom_system_prompt:
            self._system_prompt = self._custom_system_prompt
        else:
            self._system_prompt = render_system_prompt(
                agent_name=agent_name,
                agent_description=agent_description,
                custom_section=self.custom_section,
            )
        logger.info(f"AIML API Adapter started as: {agent_name}")

    async def on_message(
        self,
        msg: PlatformMessage,
        tools: AgentToolsProtocol,
        history,
        participants_msg: str | None,
        *,
        is_session_bootstrap: bool,
        room_id: str,
    ) -> None:
        if is_session_bootstrap:
            self._room_messages[room_id] = [
                {"role": "system", "content": self._system_prompt}
            ]

        messages = self._room_messages.setdefault(room_id, [
            {"role": "system", "content": self._system_prompt}
        ])

        if participants_msg:
            messages.append({"role": "system", "content": participants_msg})

        messages.append({"role": "user", "content": msg.format_for_llm()})

        tool_schemas = tools.get_tool_schemas("openai")

        for iteration in range(MAX_TOOL_ITERS):
            try:
                response = self._call_aiml(messages, tool_schemas)
            except Exception as e:
                await tools.send_event(content=f"AIML API error: {e}", message_type="error")
                raise

            content = response.get("content", "")
            tool_calls = response.get("tool_calls", [])

            if not tool_calls:
                if content:
                    messages.append({"role": "assistant", "content": content})
                return

            messages.append({
                "role": "assistant",
                "content": content or "",
                "tool_calls": tool_calls,
            })

            for tc in tool_calls:
                name = tc.get("function", {}).get("name") or tc.get("name", "")
                tool_call_id = tc.get("id", f"call_{iteration}")
                raw_args = tc.get("function", {}).get("arguments") or tc.get("arguments", {})

                if isinstance(raw_args, str):
                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        args = {}
                else:
                    args = raw_args

                await tools.send_event(
                    content=f"Calling {name}",
                    message_type="tool_call",
                    metadata={"tool": name, "input": args},
                )

                try:
                    result = await tools.execute_tool_call(name, args)
                    await tools.send_event(
                        content=f"{name} completed",
                        message_type="tool_result",
                        metadata={"tool": name, "is_error": False},
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": str(result),
                    })
                except Exception as e:
                    await tools.send_event(
                        content=f"{name} error: {e}",
                        message_type="error",
                        metadata={"tool": name, "is_error": True},
                    )
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": f"ERROR: {e}",
                    })

        await tools.send_event(
            content=f"Exceeded max tool iterations ({MAX_TOOL_ITERS})",
            message_type="error",
        )
        raise RuntimeError("Tool loop exceeded max iterations")

    def _call_aiml(self, messages: list, tool_schemas: list) -> dict:
        """Call AIML API synchronously (runs in thread pool via SDK)."""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
        }
        if tool_schemas:
            payload["tools"] = tool_schemas
            payload["tool_choice"] = "auto"

        resp = requests.post(url, json=payload, headers=headers, timeout=45)
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]["message"]
        return {
            "content": choice.get("content", ""),
            "tool_calls": choice.get("tool_calls", []),
        }

    async def on_cleanup(self, room_id: str) -> None:
        self._room_messages.pop(room_id, None)

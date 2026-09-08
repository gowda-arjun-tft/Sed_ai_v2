"""Layer-2 input accounting and lossless, retrievable history offloading."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from deepagents.backends.utils import create_file_data
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import ToolMessage
from langchain_core.utils.function_calling import convert_to_openai_tool

from ..backend.fs import text_hash
from ..backend.windows import token_count


class InputSizeError(ValueError):
    """An operational input cannot fit; this never judges completed model content."""


def dump(value) -> str:
    """Input JSON-compatible data; return lossless readable serialization for model context."""
    return json.dumps(value, ensure_ascii=False, indent=2)


def estimate(messages, system="", tools=(), response_schema=None, reserve=8_000) -> int:
    """Input every dispatch component; return a conservative, explicitly local token estimate."""
    content = [m.model_dump() if hasattr(m, "model_dump") else m for m in messages]
    schemas = [convert_to_openai_tool(t) if not isinstance(t, dict) else t for t in tools]
    payload = dump({"system": system, "messages": content, "tools": schemas,
                    "response_format": response_schema})
    return token_count(payload) + reserve + 32 * (len(content) + len(schemas))


class InputBudget(AgentMiddleware):
    """Offload older read results without summaries; enforce final assembled input bounds."""

    def __init__(self, run_dir: Path, policy: dict, system: str, schema: dict):
        """Input frozen policy and prompt; retain configuration, not shared mutable run state."""
        self.policy, self.system, self.schema = policy, system, schema
        self.logger = logging.getLogger(f"cdi.layer2.{(run_dir / 'run.log').resolve()}")

    def before_model(self, state, runtime):
        """Input thread state; replace old tool bodies with retrievable StateBackend pointers."""
        messages = state.get("messages", [])
        count = estimate(messages, self.system, response_schema=self.schema,
                         reserve=self.policy["framing_reserve"])
        if count <= self.policy["target_tokens"]:
            return None
        replacements, files = [], {}
        # Keep the newest read results visible. Older bodies remain in checkpointed
        # files; replacing message IDs preserves tool-call pairing and source evidence.
        tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
        for message in tool_messages[:-1]:
            if not message.id or not isinstance(message.content, str):
                continue
            if message.content.startswith("Archived read result: "):
                continue
            path = f"/history/{text_hash(message.content)}.md"
            files[path] = create_file_data(message.content)
            replacements.append(message.model_copy(update={
                "content": f"Archived read result: {path}. Use read_file to retrieve it."
            }))
        return {"messages": replacements, "files": files} if replacements else None

    async def abefore_model(self, state, runtime):
        """Input async thread state; apply the same non-model pointer offload."""
        return self.before_model(state, runtime)

    def _check(self, request):
        """Input the final middleware request; record its estimate or reject oversized input."""
        system = request.system_message.content if request.system_message else ""
        count = estimate(request.messages, system, request.tools, self.schema,
                         self.policy["framing_reserve"])
        if count > self.policy["maximum_tokens"]:
            raise InputSizeError(f"assembled input estimate {count} exceeds "
                                 f"{self.policy['maximum_tokens']} tokens")
        reason = ("mandatory instructions/current evidence after paging and pointer offload"
                  if count > self.policy["target_tokens"] else "normal")
        self.logger.info("input_estimate tokens=%d reason=%s", count, reason)

    def wrap_model_call(self, request, handler):
        """Input a sync dispatch; enforce its complete input budget before provider invocation."""
        self._check(request)
        return handler(request)

    async def awrap_model_call(self, request, handler):
        """Input an async dispatch including tool followups; enforce the same input budget."""
        self._check(request)
        return await handler(request)

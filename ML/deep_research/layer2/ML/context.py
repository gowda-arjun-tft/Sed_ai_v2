"""Layer-2 input accounting and lossless, retrievable history offloading."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import AIMessage, HumanMessage, RemoveMessage, ToolMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from langgraph.config import get_config

from ..backend.evidence import EvidenceStore
from ..backend.settings import MODEL_INPUT_TOKEN_LIMIT
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

    def __init__(self, run_dir: Path, policy: dict, system: str, schema: dict, tools=()):
        """Input frozen policy and prompt; retain configuration, not shared mutable run state."""
        self.policy, self.system, self.schema = policy, system, schema
        self.run_dir = run_dir
        self.tools = tools
        self.logger = logging.getLogger(f"cdi.layer2.{(run_dir / 'run.log').resolve()}")

    def before_model(self, state, runtime):
        """Input thread state; archive completed older exchanges and retain retrievable references."""
        messages = state.get("messages", [])
        count = estimate(messages, self.system, self.tools, response_schema=self.schema,
                         reserve=self.policy["framing_reserve"])
        if count <= self.policy["target_tokens"]:
            return None
        # Only archive complete assistant/tool groups; the latest group and initial
        # user instructions stay active. Persist first, then remove message IDs.
        groups, i = [], 1
        while i < len(messages):
            message = messages[i]
            group = [message]
            i += 1
            if isinstance(message, AIMessage) and message.tool_calls:
                expected = {c["id"] for c in message.tool_calls}
                while i < len(messages) and isinstance(messages[i], ToolMessage):
                    group.append(messages[i])
                    i += 1
                if expected != {m.tool_call_id for m in group[1:]}:
                    continue
            elif not isinstance(message, AIMessage):
                continue
            groups.append(group)
        older = [m for group in groups[:-1] for m in group if m.id]
        older.extend(m for m in messages[1:] if isinstance(m, HumanMessage)
                     and m.id and m.id.startswith("history-"))
        if not older:
            return None
        thread = get_config()["configurable"]["thread_id"]
        path = EvidenceStore(self.run_dir).archive(thread, [m.model_dump(mode="json") for m in older])
        return {"messages": [RemoveMessage(id=m.id) for m in older] + [HumanMessage(
            content=f"Earlier completed exchanges: {path}. List its pages with ls; retrieve exact history with read_file.",
            id="history-" + path.strip("/").rsplit("/", 1)[-1],
        )]}

    async def abefore_model(self, state, runtime):
        """Input async thread state; apply the same non-model pointer offload."""
        return self.before_model(state, runtime)

    def _check(self, request):
        """Input the final middleware request; record its estimate or reject oversized input."""
        system = request.system_message.content if request.system_message else ""
        count = estimate(request.messages, system, request.tools, self.schema,
                         self.policy["framing_reserve"])
        if count > min(self.policy["maximum_tokens"], MODEL_INPUT_TOKEN_LIMIT):
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

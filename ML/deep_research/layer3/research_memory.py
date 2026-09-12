"""Domain-private native memory with lossless archives and final-dispatch input checks."""

import json
import time

from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from deepagents.middleware import SummarizationMiddleware
from deepagents.middleware.filesystem import FilesystemMiddleware, FilesystemPermission
from langchain.agents.middleware import AgentMiddleware
from langchain_core.exceptions import ContextOverflowError
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, get_buffer_string
from langchain_core.utils.function_calling import convert_to_openai_tool

from ML.deep_research.layer2.ML.context import InputSizeError
from ML.deep_research.layer2.backend.fs import atomic_write_text, text_hash, write_json
from ML.deep_research.layer2.backend.jobs import IncompleteResponseError
from ML.deep_research.layer2.backend.run_log import diagnostic_identifier, log_failure
from ML.deep_research.layer2.backend.windows import token_count
from ML.deep_research.layer2.backend.usage import UsageCallback
from .research_budget import CallUnavailable


def count_input(messages, *, tools=None) -> int:
    """Estimate actual serialized message bodies, call arguments and tool schemas, plus framing."""
    schemas = [t if isinstance(t, dict) else convert_to_openai_tool(t) for t in tools or []]
    values = [m.model_dump(mode="json") if hasattr(m, "model_dump") else m for m in messages]
    return token_count(json.dumps([values, schemas], ensure_ascii=False, default=str)) + 32 * len(values)


def check_input(messages, record, *, tools=None, options=None, ceiling=None) -> int:
    """Enforce input policy only; file bodies cannot be inferred from their ID strings."""
    policy = record["research"]
    count = count_input(messages, tools=tools) + policy["framing_reserve"]
    count += token_count(json.dumps(options or {}, default=str))
    limit = min(ceiling or policy["maximum_tokens"], policy["maximum_tokens"], record["model_input_token_limit"])
    if count > limit:
        raise InputSizeError(f"Research input estimate {count} exceeds allowance {limit}")
    return count


class ResearchTrace(UsageCallback):
    """Save complete model/tool records immediately; log only safe operational identifiers."""

    raise_error = True
    run_inline = True

    def __init__(self, root, thread, logger, domain):
        """Bind trace ownership to a trusted domain, not model-provided paths."""
        root.mkdir(parents=True, exist_ok=True)
        super().__init__(root, thread)
        self.root, self.logger, self.domain = root, logger, domain
        self.starts, self.phases = {}, {}

    def on_chat_model_start(self, serialized, messages, *, run_id, metadata=None, **kwargs):
        """Persist the dispatched input and distinguish main and compaction requests."""
        self.starts[run_id] = time.perf_counter()
        self.phases[run_id] = "compaction" if (metadata or {}).get("lc_source") == "summarization" else "research"
        super().on_chat_model_start(serialized, messages, run_id=run_id,
                                   metadata={"lc_agent_name": f"{self.domain}/{self.phases[run_id]}"}, **kwargs)
        write_json(self.root / f"model-{run_id}-input.json",
                   [[m.model_dump(mode="json") for m in group] for group in messages])
        self.logger.info("model_started domain=%s phase=%s call=%s", self.domain, self.phases[run_id], run_id)

    def on_llm_end(self, response, *, run_id, **kwargs):
        """Persist provider messages and usage before the graph can lose an interrupted completion."""
        for index, group in enumerate(response.generations):
            if group:
                write_json(self.root / f"model-{run_id}-{index}.json", group[0].message.model_dump(mode="json"))
        super().on_llm_end(response, run_id=run_id, **kwargs)
        self.logger.info("model_finished domain=%s phase=%s call=%s elapsed_seconds=%.3f",
                         self.domain, self.phases.pop(run_id, "research"), run_id,
                         time.perf_counter() - self.starts.pop(run_id, time.perf_counter()))

    def on_llm_error(self, error, *, run_id, **kwargs):
        """Release callback clocks and log failure frames without exception payloads."""
        self.starts.pop(run_id, None)
        self.phases.pop(run_id, None)
        self._actors.pop(run_id, None)
        log_failure(self.logger, "research_model_failed", error, domain=self.domain, call=str(run_id))

    def on_tool_start(self, serialized, input_str, *, run_id, **kwargs):
        """Retain tool arguments privately, never in run.log."""
        self.starts[run_id] = time.perf_counter()
        write_json(self.root / f"tool-{run_id}-input.json", {"tool": serialized.get("name"), "input": input_str})
        self.logger.info("tool_started domain=%s tool=%s call=%s", self.domain,
                         diagnostic_identifier(serialized.get("name")), run_id)

    def on_tool_end(self, output, *, run_id, **kwargs):
        """Retain complete tool results and observed duration."""
        value = output.model_dump(mode="json") if hasattr(output, "model_dump") else str(output)
        write_json(self.root / f"tool-{run_id}-output.json", value)
        self.logger.info("tool_finished domain=%s call=%s elapsed_seconds=%.3f", self.domain, run_id,
                         time.perf_counter() - self.starts.pop(run_id, time.perf_counter()))

    def on_tool_error(self, error, *, run_id, **kwargs):
        """Keep failures operational and remove stale tool clocks."""
        self.starts.pop(run_id, None)
        log_failure(self.logger, "research_tool_failed", error, domain=self.domain, call=str(run_id))


class ResearchGuard(AgentMiddleware):
    """Final assembled-request guard and immediate authoritative final-response receipt."""

    def __init__(self, record, root, fingerprint, logger, budget=None):
        """Bind frozen policy and the current domain's output receipt."""
        self.record, self.root, self.fingerprint, self.logger = record, root, fingerprint, logger
        self.budget = budget

    async def awrap_tool_call(self, request, handler):
        """Resolve pending tool calls honestly when another parallel call crosses the boundary."""
        if (self.budget and self.budget.phase in {"finalization", "exhausted"}
                and request.tool_call["name"] not in {"ls", "glob", "grep", "read_file"}):
            return ToolMessage(content="Operational limitation: finalization permits saved-file reading only.",
                               tool_call_id=request.tool_call["id"], name=request.tool_call["name"], status="error")
        try:
            return await handler(request)
        except CallUnavailable as error:
            return ToolMessage(content=str(error), tool_call_id=request.tool_call["id"],
                               name=request.tool_call["name"], status="error")

    def checked_request(self, request, note="", final=False):
        """Count the actual ephemeral counter and tool surface without adding history messages."""
        if self.budget:
            system = request.system_message or SystemMessage(content="")
            content = (system.content + "\n\n" + note if isinstance(system.content, str)
                       else [*system.content, {"type": "text", "text": note}])
            tools = request.tools
            if final:
                tools = []
            elif self.budget.phase == "finalization":
                tools = [t for t in tools if getattr(t, "name", None) in {"ls", "glob", "grep", "read_file"}]
            request = request.override(system_message=system.model_copy(update={"content": content}), tools=tools)
        values = ([request.system_message] if request.system_message else []) + request.messages
        profile = getattr(request.model, "profile", None) or {}
        count = check_input(values, self.record, tools=request.tools, options=request.model_settings,
                            ceiling=profile.get("max_input_tokens") or profile.get("max_context_tokens"))
        self.logger.info("research_input estimated_tokens=%d exceptional=%s", count,
                         count > self.record["research"]["target_tokens"])
        return request

    async def awrap_model_call(self, request, handler):
        """Check after context/file middleware, then preserve completed assistant content verbatim."""
        try:
            if self.budget:
                result = await self.budget.call("main", lambda note, final: self.checked_request(request, note, final), handler)
            else:
                result = await handler(self.checked_request(request))
        except ContextOverflowError as error:
            # No implicit framework overflow clipping/re-dispatch; preserve the operational failure.
            raise InputSizeError("Provider rejected the assembled context") from error
        for message in result.result:
            if getattr(message, "type", None) != "ai":
                continue
            info = message.response_metadata
            if info.get("status") == "incomplete" or info.get("finish_reason") == "length":
                raise IncompleteResponseError("Provider reported incomplete research output")
            if not message.tool_calls and not message.invalid_tool_calls:
                atomic_write_text(self.root / "response.md", message.text)
                write_json(self.root / "final.json", {"fingerprint": self.fingerprint,
                           "sha256": text_hash(message.text), "message": message.model_dump(mode="json")})
        return result


class ResearchSummarization(SummarizationMiddleware):
    """Explicit native summarizer kept separate from the historical Layer 4 compactor."""

    def __init__(self, model, backend, record, prompt, logger, budget=None):
        """Use native safe message partitioning, with no argument or summary-input truncation."""
        self.record, self.prompt, self.logger = record, prompt, logger
        self.budget = budget
        policy = record["research"]
        super().__init__(model, backend=backend, trigger=("tokens", policy["summary_trigger_tokens"]),
                         keep=("tokens", policy["summary_keep_tokens"]), summary_prompt=prompt,
                         token_counter=count_input, trim_tokens_to_summarize=None)

    async def awrap_model_call(self, request, handler):
        """Retain existing summaries but reserve the last invocation for the final main response."""
        if self.budget and self.budget.used >= self.budget.policy["maximum_calls"] - 1:
            return await handler(request.override(messages=self._get_effective_messages(request)))
        return await super().awrap_model_call(request, handler)

    async def _acreate_summary(self, messages_to_summarize):
        """Count the exact summary input and use one normal request without framework retry wrappers."""
        content = self.prompt.format(messages=get_buffer_string(messages_to_summarize, format="xml"))
        def prepare(note, final):
            """Validate the supporting summary's own instructions plus its current counter."""
            request = [HumanMessage(content=content + ("\n\n" + note if note else ""))]
            check_input(request, self.record)
            return request

        async def invoke(request):
            """Dispatch one native summary, sharing the domain's model transport."""
            return await self.model.ainvoke(request, config={"metadata": {"lc_source": "summarization"}})

        response = (await self.budget.call("summary", prepare, invoke) if self.budget
                    else await invoke(prepare("", False)))
        self.logger.info("compaction_finished archived_messages=%d", len(messages_to_summarize))
        return response.text

    async def _aoffload_to_backend(self, backend, messages, session_id):
        """Make archive failure an operational preservation failure, never silently lossy compaction."""
        path = await super()._aoffload_to_backend(backend, messages, session_id)
        if path is None:
            raise OSError("Cannot preserve research conversation archive")
        return path


def memory_backend(root):
    """Expose only this domain's inputs, evidence and archives; notes live in checkpoint state."""
    for name in ("inputs", "evidence", "archive", "prior"):
        (root / name).mkdir(parents=True, exist_ok=True)
    return CompositeBackend(default=StateBackend(), routes={
        f"/{name}/": FilesystemBackend(root_dir=root / name, virtual_mode=True)
        for name in ("inputs", "evidence", "archive", "prior")}, artifacts_root="/archive")


def file_middleware(backend):
    """Use native file tools but expose neither deletion nor execution, and only notes are writable."""
    return FilesystemMiddleware(backend=backend, human_message_token_limit_before_evict=None,
                                tools=["ls", "glob", "grep", "read_file", "write_file", "edit_file"],
                                _permissions=[FilesystemPermission(["write"], ["/notes/**"], "allow"),
                                              FilesystemPermission(["write"], ["/**"], "deny")])

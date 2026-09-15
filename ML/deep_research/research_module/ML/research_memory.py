"""Domain-private native memory with lossless archives and final-dispatch input checks."""

import json
from uuid import uuid4

from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend
from deepagents.middleware import SummarizationMiddleware
from deepagents.middleware.filesystem import FilesystemMiddleware, FilesystemPermission
from langchain.agents.middleware import AgentMiddleware
from langchain_core.exceptions import ContextOverflowError
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, get_buffer_string
from langchain_core.utils.function_calling import convert_to_openai_tool

from ML.deep_research.domain_decider.ML.context import InputSizeError
from ML.deep_research.domain_decider.backend.fs import atomic_write_text, text_hash, write_json
from ML.deep_research.domain_decider.backend.jobs import IncompleteResponseError
from ML.deep_research.domain_decider.backend.windows import token_count
from ..backend.research_budget import CallUnavailable
from ML.deep_research.domain_decider.backend.stage_settings import generation_options
from ML.deep_research.domain_decider.backend.tracing import event, private_json


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


from .research_trace import ResearchTrace


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
        identifier = uuid4().hex
        state = getattr(request, "state", {}) or {}
        private_json(self.root / "trace" / f"operation-{identifier}-before.json",
                     {"call": request.tool_call, "todos": state.get("todos"), "files": state.get("files")})
        event(self.root / "trace", "tool_proposed", tool_call_id=request.tool_call["id"],
              reference=f"operation-{identifier}-before.json")
        try:
            result = await handler(request)
            private_json(self.root / "trace" / f"operation-{identifier}-result.json",
                         getattr(result, "update", result))
            event(self.root / "trace", "tool_result", tool_call_id=request.tool_call["id"],
                  reference=f"operation-{identifier}-result.json")
            return result
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
        settings = {**request.model_settings, **generation_options(self.record, "research")}
        request = request.override(model_settings=settings)
        values = ([request.system_message] if request.system_message else []) + request.messages
        profile = getattr(request.model, "profile", None) or {}
        count = check_input(values, self.record, tools=request.tools, options=request.model_settings,
                            ceiling=profile.get("max_input_tokens") or profile.get("max_context_tokens"))
        self.logger.info("research_input estimated_tokens=%d exceptional=%s", count,
                         count > self.record["research"]["target_tokens"])
        identifier = uuid4().hex
        private_json(self.root / "trace" / f"dispatch-{identifier}.json",
                     {"messages": values, "options": settings,
                      "tools": [t if isinstance(t, dict) else convert_to_openai_tool(t) for t in request.tools]})
        event(self.root / "trace", "context_checked", reference=f"dispatch-{identifier}.json", estimated_tokens=count)
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
                event(self.root / "trace", "final_response_saved", fingerprint=self.fingerprint,
                      sha256=text_hash(message.text), reference="../final.json")
        return result


class ResearchSummarization(SummarizationMiddleware):
    """Explicit native summarizer with domain-private, retrievable conversation archives."""

    def __init__(self, model, backend, record, prompt, logger, budget=None, root=None):
        """Use native safe message partitioning, with no argument or summary-input truncation."""
        self.record, self.prompt, self.logger = record, prompt, logger
        self.budget = budget
        self.root = root
        policy = record["research"]
        super().__init__(model, backend=backend, trigger=("tokens", policy["summary_trigger_tokens"]),
                         keep=("tokens", policy["summary_keep_tokens"]), summary_prompt=prompt,
                         token_counter=count_input, trim_tokens_to_summarize=None)

    async def awrap_model_call(self, request, handler):
        """Retain existing summaries but reserve the last invocation for the final main response."""
        if self.budget and self.budget.remaining is not None and self.budget.remaining <= 1:
            return await handler(request.override(messages=self._get_effective_messages(request)))
        if self.root is None:
            return await super().awrap_model_call(request, handler)
        identifier = uuid4().hex
        effective = self._get_effective_messages(request)
        before = self._count_tokens(effective, request.system_message, request.tools)
        private_json(self.root / "trace" / f"compaction-{identifier}-before.json",
                     {"effective": effective, "system": request.system_message})
        async def observe(updated):
            """Observe the native middleware's exact downstream context without altering it."""
            private_json(self.root / "trace" / f"compaction-{identifier}-after.json", updated.messages)
            after = self._count_tokens(updated.messages, updated.system_message, updated.tools)
            event(self.root / "trace", "memory_context_observed", operation=identifier, before_tokens=before,
                  context_changed=updated.messages != effective,
                  after_tokens=after, trigger_tokens=self.record["research"]["summary_trigger_tokens"],
                  before_reference=f"compaction-{identifier}-before.json", after_reference=f"compaction-{identifier}-after.json")
            return await handler(updated)
        return await super().awrap_model_call(request, observe)

    async def _acreate_summary(self, messages_to_summarize):
        """Count the exact summary input and use one normal request without framework retry wrappers."""
        content = self.prompt.format(messages=get_buffer_string(messages_to_summarize, format="xml"))
        options = generation_options(self.record, "summary")
        identifier = uuid4().hex
        if self.root is not None:
            private_json(self.root / "trace" / f"summary-{identifier}-selected.json", messages_to_summarize)
        def prepare(note, final):
            """Validate the supporting summary's own instructions plus its current counter."""
            request = [HumanMessage(content=content + ("\n\n" + note if note else ""))]
            check_input(request, self.record, options=options)
            return request

        async def invoke(request):
            """Dispatch one native summary, sharing the domain's model transport."""
            return await self.model.ainvoke(request, config={"metadata": {"lc_source": "summarization"}}, **options)

        response = (await self.budget.call("summary", prepare, invoke) if self.budget
                    else await invoke(prepare("", False)))
        self.logger.info("compaction_finished archived_messages=%d", len(messages_to_summarize))
        if self.root is not None:
            private_json(self.root / "trace" / f"summary-{identifier}-response.json", response)
            event(self.root / "trace", "summary_returned", operation=identifier,
                  selected_reference=f"summary-{identifier}-selected.json", response_reference=f"summary-{identifier}-response.json",
                  selected_messages=len(messages_to_summarize))
        return response.text

    def _partition_messages(self, messages, cutoff_index):
        """Observe native safe partitioning, including repeated single-message compactions."""
        selected, retained = super()._partition_messages(messages, cutoff_index)
        if self.root is not None:
            identifier = uuid4().hex
            private_json(self.root / "trace" / f"partition-{identifier}.json",
                         {"selected": selected, "retained_unchanged": retained, "cutoff_index": cutoff_index})
            event(self.root / "trace", "compaction_partition", reference=f"partition-{identifier}.json",
                  selected_messages=len(selected), retained_messages=len(retained))
        return selected, retained

    async def _aoffload_to_backend(self, backend, messages, session_id):
        """Make archive failure an operational preservation failure, never silently lossy compaction."""
        path = await super()._aoffload_to_backend(backend, messages, session_id)
        if path is None:
            raise OSError("Cannot preserve research conversation archive")
        if self.root is not None:
            from ML.deep_research.domain_decider.backend.fs import sha256
            actual = (self.root / path.lstrip("/")).resolve()
            digest = sha256(actual) if actual.is_relative_to(self.root.resolve()) and actual.is_file() else None
            event(self.root / "trace", "archive_saved", path=path, sha256=digest, selected_messages=len(messages))
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

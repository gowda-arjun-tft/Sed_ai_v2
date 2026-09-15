"""Private provider and tool observations; no model-content grading."""

import time

from ML.deep_research.domain_decider.backend.tracing import private_json as write_json
from ML.deep_research.domain_decider.backend.run_log import diagnostic_identifier, log_failure
from ML.deep_research.domain_decider.backend.usage import UsageCallback
from ML.deep_research.domain_decider.backend.tracing import event, private_json, reasoning_summaries

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
        private_json(self.root / f"model-{run_id}-settings.json", kwargs.get("invocation_params", {}))
        event(self.root, "model_started", model_request=str(run_id), parent_request=str(kwargs.get("parent_run_id")),
              phase=self.phases[run_id], input_reference=f"model-{run_id}-input.json",
              settings_reference=f"model-{run_id}-settings.json")
        self.logger.info("model_started domain=%s phase=%s call=%s", self.domain, self.phases[run_id], run_id)

    def on_llm_end(self, response, *, run_id, **kwargs):
        """Persist provider messages and usage before the graph can lose an interrupted completion."""
        for index, group in enumerate(response.generations):
            if group:
                write_json(self.root / f"model-{run_id}-{index}.json", group[0].message.model_dump(mode="json"))
                reasoning_summaries(self.root / f"model-{run_id}-{index}-reasoning.json",
                                    group[0].message.model_dump(mode="json"))
                event(self.root, "model_returned", model_request=str(run_id),
                      provider_id=group[0].message.id, response_reference=f"model-{run_id}-{index}.json",
                      usage=group[0].message.usage_metadata)
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
        event(self.root, "model_failed", model_request=str(run_id), error_type=type(error).__name__)

    def on_tool_start(self, serialized, input_str, *, run_id, **kwargs):
        """Retain tool arguments privately, never in run.log."""
        self.starts[run_id] = time.perf_counter()
        write_json(self.root / f"tool-{run_id}-input.json", {"tool": serialized.get("name"), "input": input_str})
        event(self.root, "tool_started", tool_request=str(run_id), parent_request=str(kwargs.get("parent_run_id")),
              tool=serialized.get("name"), input_reference=f"tool-{run_id}-input.json")
        self.logger.info("tool_started domain=%s tool=%s call=%s", self.domain,
                         diagnostic_identifier(serialized.get("name")), run_id)

    def on_tool_end(self, output, *, run_id, **kwargs):
        """Retain complete tool results and observed duration."""
        value = output.model_dump(mode="json") if hasattr(output, "model_dump") else str(output)
        write_json(self.root / f"tool-{run_id}-output.json", value)
        event(self.root, "tool_returned", tool_request=str(run_id), output_reference=f"tool-{run_id}-output.json")
        self.logger.info("tool_finished domain=%s call=%s elapsed_seconds=%.3f", self.domain, run_id,
                         time.perf_counter() - self.starts.pop(run_id, time.perf_counter()))

    def on_tool_error(self, error, *, run_id, **kwargs):
        """Keep failures operational and remove stale tool clocks."""
        self.starts.pop(run_id, None)
        log_failure(self.logger, "research_tool_failed", error, domain=self.domain, call=str(run_id))
        event(self.root, "tool_failed", tool_request=str(run_id), error_type=type(error).__name__)

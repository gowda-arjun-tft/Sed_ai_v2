"""Durable logical-call reservations shared by all four domain model request paths."""

import asyncio
import time

from ML.deep_research.layer2.backend.fs import load_json, now_iso, write_json


class BudgetExhausted(RuntimeError):
    """No logical model invocation remains for this domain."""


class CallUnavailable(RuntimeError):
    """The current phase reserves capacity for main-model finalization."""


class CallBudget:
    """Reserve before dispatch; retain failed and uncertain reservations across resumes."""

    def __init__(self, root, policy, entry, logger, persist):
        """Open this domain's ledger without resetting an existing allowance."""
        self.path = root / "calls.json"
        self.policy, self.entry, self.logger, self.persist = policy, entry, logger, persist
        self.lock = asyncio.Lock()
        if self.path.exists():
            self.state = load_json(self.path)
            if self.state.get("fingerprint") != entry["fingerprint"]:
                raise ValueError("Research call ledger dependencies changed")
        else:
            if entry.get("checkpoint_started"):
                raise RuntimeError("Research call ledger missing; restore it before resuming")
            self.state = {"fingerprint": entry["fingerprint"], "calls": []}
        calls = self.state["calls"]
        if len(calls) > policy["maximum_calls"] or any(c["number"] != i for i, c in enumerate(calls, 1)):
            raise ValueError("Invalid research call ledger")
        self.save()

    @property
    def used(self):
        """Count reservations, including attempts interrupted before a receipt was saved."""
        return len(self.state["calls"])

    @property
    def phase(self):
        """Describe the next dispatch from already-consumed logical calls."""
        if self.used >= self.policy["maximum_calls"]:
            return "exhausted"
        if self.used >= self.policy["finalize_after"]:
            return "finalization"
        return "wrap_up" if self.used >= self.policy["wrap_up_after"] else "research"

    def save(self):
        """Persist the authoritative ledger before its compact run-status projection."""
        write_json(self.path, self.state)
        self.entry["budget"] = {"used": self.used, "remaining": self.policy["maximum_calls"] - self.used,
                                "phase": self.phase}
        self.persist()

    def require_research(self):
        """Deny undispatched network work once the final ten calls are reserved."""
        if self.used >= self.policy["finalize_after"]:
            raise CallUnavailable("Finalization: read saved evidence and write the report; no new network research.")

    async def call(self, kind, prepare, invoke):
        """Account for checked requests atomically; cached/local work never enters this method."""
        async with self.lock:
            if self.used >= self.policy["maximum_calls"]:
                raise BudgetExhausted("Research logical-call allowance exhausted")
            final = self.used == self.policy["maximum_calls"] - 1
            if kind in {"search", "document"}:
                self.require_research()
            if final and kind != "main":
                raise CallUnavailable("The last logical call is reserved for the main model's report.")
            phase = self.phase
            note = (f"Runtime call allowance: {self.used} used; this is logical call {self.used + 1} "
                    f"of {self.policy['maximum_calls']} (includes search, documents and summaries). ")
            if kind == "main":
                note += {"research": "Finish early when the objective is met.",
                         "wrap_up": "Prioritize essential gaps and prepare to finish.",
                         "finalization": "Finish from saved evidence; no new searches, downloads or document analysis."}[phase]
                if final:
                    note += " This final call has no tools: write the final Markdown now and disclose remaining gaps."
            else:
                note += "Complete only this request's supporting task; do not write the domain report."
            payload = prepare(note, final)  # Check actual annotated input before spending a reservation.
            receipt = {"number": self.used + 1, "kind": kind, "phase": phase,
                       "started_at": now_iso(), "outcome": "reserved"}
            self.state["calls"].append(receipt)
            self.save()
            if self.phase != phase:
                self.logger.info("research_phase_changed previous=%s phase=%s used=%d thread=%s",
                                 phase, self.phase, self.used, self.entry["thread_id"])
            self.logger.info("research_call_reserved kind=%s number=%d phase=%s used=%d remaining=%d thread=%s",
                             kind, receipt["number"], phase, self.used,
                             self.policy["maximum_calls"] - self.used, self.entry["thread_id"])
        started = time.perf_counter()
        try:
            result = await invoke(payload)
        except BaseException as error:
            receipt["outcome"] = "interrupted" if isinstance(error, asyncio.CancelledError) else "failed_or_uncertain"
            raise
        else:
            receipt["outcome"] = "returned"
            return result
        finally:
            receipt["elapsed_seconds"] = round(time.perf_counter() - started, 3)
            self.save()
            self.logger.info("research_call_finished kind=%s number=%d outcome=%s elapsed_seconds=%.3f phase=%s thread=%s",
                             kind, receipt["number"], receipt["outcome"], receipt["elapsed_seconds"],
                             self.phase, self.entry["thread_id"])

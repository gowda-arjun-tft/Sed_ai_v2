"""One numbered workflow calling the existing public phase runners, without another agent loop."""

import asyncio
import os
import time
from pathlib import Path

from . import domain_decider, research_module
from .domain_decider.backend.cli import load_dotenv_key
from .domain_decider.backend.fs import atomic_write_text, load_json, now_iso, sha256, storage_path, write_json
from .domain_decider.backend.run_log import log_failure, operational_logger
from .domain_decider.backend.settings import DOMAIN_PLUGIN_PATH, REPO_ROOT, RUNS_DIR
from .domain_decider.backend.stage_settings import resolve_stage_settings
from .research_module.backend.document_uploads import run_writer
from .research_module.backend.research_run import checkpoint_root, read_research_config, research_policy
from .research_module.backend.settings import SOURCE_SUGGESTION_PATH, RESEARCH_INSTRUCTION_PATH, RESEARCH_CONFIG_PATH
from .workflow_storage import allocate, child_path, input_snapshots, save_inputs
from .domain_decider.backend.tracing import TRACE_ROOT, event


def create_run(fact_sheet, *, domain_plugin=DOMAIN_PLUGIN_PATH, requirements=REPO_ROOT / "inputs/requirement.md",
               source_suggestion=SOURCE_SUGGESTION_PATH, research_instruction=RESEARCH_INSTRUCTION_PATH,
               research_config=RESEARCH_CONFIG_PATH, stage_settings=None, public_input_confirmed=False,
               runs_dir=RUNS_DIR):
    """Preflight and freeze the full workflow without making any provider requests."""
    if public_input_confirmed is not True:
        raise ValueError("Full research requires public-input confirmation")
    load_dotenv_key()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required")
    resolved = resolve_stage_settings(stage_settings)
    snapshots = input_snapshots({"fact_sheet.md": fact_sheet, "domain_plugin.md": domain_plugin,
        "requirements.md": requirements, "source_suggestion.md": source_suggestion,
        "user_research_instruction.md": research_instruction, "research_config.json": research_config})
    # Parse the exact captured configuration, not a second read of an editable user file.
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as directory:
        config = Path(directory) / "research_config.json"
        config.write_bytes(snapshots["research_config.json"])
        _, limits = read_research_config(config)
    policy = research_policy(resolved["stages"]["research"]["reasoning"], call_limits=limits)
    checkpoint_root({"research": policy})
    root, identity, number = allocate(runs_dir, fact_sheet)
    record = {"workflow_version": 1, "schema_version": 9, "status": "created", "number": number,
              "source_identity": identity, "started_at": now_iso(), "public_input_confirmed": True,
              "stage_settings": resolved, "checkpoint_root": policy["checkpoint_root"],
              "inputs": save_inputs(root, snapshots),
              "phases": {"domain_decider": "domain_decider", "research_module": "research_module"}}
    write_json(root / "run.json", record)
    _publish(root, record)
    return root


def _phase(root, record, name):
    """Create once or reuse an already-recorded phase after interruption between manifest writes."""
    path = child_path(root, record["phases"][name])
    if not (path / "run.json").exists():
        inputs = root / "_internal/inputs"
        settings = {**record["stage_settings"]["stages"],
                    "reasoning_summaries": record["stage_settings"]["reasoning_summaries"]}
        common = {"public_input_confirmed": True, "stage_settings": settings, "destination": path}
        if name == "domain_decider":
            domain_decider.create_run(inputs / "fact_sheet.md", inputs / "domain_plugin.md",
                inputs / "requirements.md", root.parent, prompt_directory=inputs / "domain_prompts", **common)
        else:
            research_module.create_run(child_path(root, record["phases"]["domain_decider"]), root.parent,
                source_suggestion=inputs / "source_suggestion.md",
                research_instruction=inputs / "user_research_instruction.md", research_config=inputs / "research_config.json",
                prompt_directory=inputs / "research_prompts", **common)
    child = load_json(path / "run.json")
    if name == "research_module" and Path(child["source_l2"]["path"]).resolve() != child_path(root, record["phases"]["domain_decider"]):
        raise ValueError("Research phase does not belong to the selected domain preparation")
    child["workflow_root"] = str(root.resolve())
    write_json(path / "run.json", child)
    return path, child


def _publish(root, record):
    """Publish status links only; reports remain independent per domain and unchanged."""
    lines = [f"# {root.parent.name} — run {record['number']}", "", f"Status: **{record['status']}**", "",
             "[Operational log](run.log) · [Private event index](_internal/trace/events.jsonl)", ""]
    for name, relative in record["phases"].items():
        path = child_path(root, relative)
        if (path / "run.json").exists():
            child = load_json(path / "run.json")
            lines.append(f"- [{name}]({relative}/README.md): {child['status']}")
            if name == "research_module":
                jobs = child.get("research", {}).get("jobs", {})
                lines.append(f"  Research: {sum(j.get('status') == 'complete' for j in jobs.values())}/{len(child['domains'])}; "
                             f"[reports]({relative}/research/). Uploads: {child.get('document_uploads', {}).get('status', 'not_run')}.")
    atomic_write_text(root / "README.md", "\n".join(lines) + "\n")


async def _run_domain(path, logger):
    """Keep ownership until the synchronous public runner exits, even on notebook cancellation."""
    worker = asyncio.create_task(asyncio.to_thread(domain_decider.run_all, path))
    try:
        await asyncio.shield(worker)
    except asyncio.CancelledError:
        # A Python thread cannot be safely killed; do not release its run lock or start research.
        logger.warning("cancellation_requested waiting_for_domain_phase_exit=true")
        await asyncio.gather(worker, return_exceptions=True)
        raise


async def run_all(run_dir, *, retry_failed=False):
    """Resume only the explicitly selected root; completed phases never dispatch again."""
    root = storage_path(run_dir).resolve()
    record = load_json(root / "run.json")
    if record.get("workflow_version") != 1 or record.get("schema_version") != 9:
        raise ValueError("Select a numbered full workflow; advanced historical actions use module APIs/CLI")
    for relative, item in record["inputs"].items():
        if sha256(child_path(root, relative)) != item["sha256"]:
            raise ValueError("Frozen workflow input changed")
    if record["status"] == "complete":
        return
    if not record.get("public_input_confirmed"):
        raise ValueError("Frozen public-input consent is missing")
    load_dotenv_key()
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is required")
    checkpoint_root({"research": {"version": 4, "checkpoint_root": record["checkpoint_root"]}})
    with run_writer(root), operational_logger(root) as logger:
        trace_token = TRACE_ROOT.set(root / "_internal/trace")
        started = time.perf_counter()
        try:
            record["status"] = "running"
            write_json(root / "run.json", record)
            logger.info("workflow_started number=%d", record["number"])
            event(root / "_internal/trace", "workflow_started", settings=record["stage_settings"])
            domain, saved = _phase(root, record, "domain_decider")
            event(root / "_internal/trace", "phase_selected", stage="domain_decider", run_id=saved["run_id"], status=saved["status"])
            if saved["status"] != "complete":
                await _run_domain(domain, logger)
            status = load_json(domain / "run.json")["status"]
            if status != "complete":
                record["status"] = status
                return
            research, saved = _phase(root, record, "research_module")
            event(root / "_internal/trace", "phase_selected", stage="research_module", run_id=saved["run_id"], status=saved["status"])
            if saved["status"] != "complete":
                await research_module.run_all(research, retry_failed=retry_failed)
            record["status"] = load_json(research / "run.json")["status"]
        except BaseException as error:
            record["status"] = "interrupted" if isinstance(error, (KeyboardInterrupt, asyncio.CancelledError)) else "failed"
            log_failure(logger, "workflow_failed", error)
            raise
        finally:
            TRACE_ROOT.reset(trace_token)
            record.update(updated_at=now_iso(), elapsed_seconds=round(time.perf_counter() - started, 3))
            write_json(root / "run.json", record)
            _publish(root, record)
            logger.info("workflow_finished status=%s elapsed_seconds=%.3f", record["status"], record["elapsed_seconds"])
            event(root / "_internal/trace", "workflow_finished", status=record["status"], elapsed_seconds=record["elapsed_seconds"])

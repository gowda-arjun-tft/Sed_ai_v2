"""Static historical schema-8 inputs for shared Layer 4 harness regression tests."""

import shutil
from pathlib import Path

from ML.deep_research.layer2.backend.fs import load_json, now_iso, write_json
from ML.deep_research.layer3 import settings
from ML.deep_research.layer3.pipeline.progress import stage_record


def create_run(l2_run, runs_dir, *, public_input_confirmed=False, reasoning_effort="low",
               web_search_context_size="low", web_search_verbosity="low"):
    """Build a historical fixture; never expose legacy execution in the production runner."""
    if not public_input_confirmed:
        raise ValueError("public-input confirmation required")
    run = l2_run.resolve().parent / "L3_historical_fixture"
    run.mkdir()
    target = run / "inputs"
    shutil.copytree(l2_run / "inputs", target)
    shutil.copytree(l2_run / "missions", target / "missions")
    shutil.copytree(l2_run / "mission_md", target / "mission_md")
    (target / "prompts").mkdir()
    shutil.copy2(settings.SKILL_PATH, target / "prompts/SKILL.md")
    shutil.copy2(settings.PROMPTS_DIR / "synthesis.md", target / "prompts/synthesis.md")
    for name in ("sources/raw", "sources/text", "domains", "research"):
        (run / name).mkdir(parents=True)
    for name in ("usage.jsonl", "sources/queries.jsonl", "sources/index.jsonl"):
        (run / name).touch()
    source = load_json(l2_run / "run.json")
    record = {
        "schema_version": 8, "harness": "domain_plain_research_direct_output",
        "run_id": run.name, "status": "created", "started_at": now_iso(),
        "source_l2": {"run_id": source["run_id"], "path": str(l2_run), "status": source["status"],
                      "checks": source.get("checks", {}), "facts": source.get("facts", {})},
        "provider": "online", "public_input_confirmed": True, "model": settings.MODEL_NAME,
        "reasoning_effort": reasoning_effort,
        "web_search": {"context_size": web_search_context_size, "verbosity": web_search_verbosity},
        "model_context_window_tokens": settings.MODEL_INPUT_TOKEN_LIMIT,
        "context_management": {
            "policy_version": 1, "applies_to": "domain_researcher", "soft_target_tokens": 200_000,
            "eviction_trigger_tokens": 150_000, "eviction_keep_tool_results": 6,
            "eviction_exempt_tools": ["search_web"], "emergency_eviction_trigger_tokens": 170_000,
            "emergency_eviction_keep_tool_results": 0, "summary_trigger_tokens": 170_000,
            "summary_keep_tokens": 70_000, "summary_trim_tokens": None,
        },
        "domains": list(settings.DOMAIN_NAMES),
    }
    record["execution"] = {
        "domains": {n: stage_record(record, "researcher", n, 0) for n in settings.DOMAIN_NAMES},
        "final": stage_record(record, "synthesis", "property-synthesis", 0),
    }
    write_json(run / "run.json", record)
    return run

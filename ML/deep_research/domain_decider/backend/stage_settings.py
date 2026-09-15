"""Resolve user-owned stage controls once; historical requests keep their frozen options."""

import json
from pathlib import Path

from .settings import REASONING_EFFORTS, WEB_SEARCH_LEVELS

STAGES = ("metadata", "design", "distribution", "source_discovery", "research",
          "research_search", "document", "summary")
SEARCH_STAGES = {"design", "source_discovery", "research_search"}


def read_stage_settings(path: Path) -> dict:
    """Read a JSON configuration without silently accepting duplicate keys."""
    def unique(pairs):
        """Reject ambiguous operational settings, not model-authored output."""
        values = dict(pairs)
        if len(values) != len(pairs):
            raise ValueError("Duplicate stage-setting keys")
        return values

    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique)


def resolve_stage_settings(selected=None, *, legacy=None) -> dict:
    """Freeze complete independent settings; explicit values override legacy generation arguments."""
    selected = {} if selected is None else selected
    if not isinstance(selected, dict) or set(selected) - {*STAGES, "reasoning_summaries"}:
        raise ValueError("Unknown stage settings")
    summaries = selected.get("reasoning_summaries", True)
    if type(summaries) is not bool:
        raise ValueError("reasoning_summaries must be boolean")
    resolved = {}
    for stage in STAGES:
        defaults = {"reasoning": "medium" if stage == "summary" else "high",
                    "verbosity": "low" if stage in {"source_discovery", "research_search"} else "medium"}
        if stage in SEARCH_STAGES:
            defaults["search_context"] = "medium"
        values = selected.get(stage, {})
        if not isinstance(values, dict) or set(values) - set(defaults):
            raise ValueError(f"Unsupported settings for {stage}")
        values = defaults | (legacy or {}).get(stage, {}) | values
        if values["reasoning"] not in REASONING_EFFORTS or values["verbosity"] not in WEB_SEARCH_LEVELS:
            raise ValueError(f"Unsupported generation setting for {stage}")
        if stage in SEARCH_STAGES and values["search_context"] not in WEB_SEARCH_LEVELS:
            raise ValueError(f"Unsupported search context for {stage}")
        resolved[stage] = values
    return {"version": 1, "reasoning_summaries": summaries, "stages": resolved}


def generation_options(record: dict, stage: str) -> dict:
    """Native Responses options shared by dispatch, caches and input accounting."""
    policy = record.get("stage_settings")
    if not policy:
        return {}
    values = policy["stages"][stage]
    reasoning = {"effort": values["reasoning"]}
    if policy["reasoning_summaries"]:
        reasoning["summary"] = "auto"
    return {"reasoning": reasoning, "text": {"verbosity": values["verbosity"]}}


def search_context(record: dict, stage: str) -> str:
    """Use stage-specific search context only for records that froze that policy."""
    if record.get("stage_settings"):
        return record["stage_settings"]["stages"][stage]["search_context"]
    return record["web_search"]["context_size"]

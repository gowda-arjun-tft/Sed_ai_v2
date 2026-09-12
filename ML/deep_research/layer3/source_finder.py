"""Native request construction and durable source-finder completions."""

import json
from pathlib import Path

from langchain_core.messages import AIMessage

from ML.deep_research.layer2.ML.context import estimate, messages
from ML.deep_research.layer2.backend.fs import atomic_write_text, text_hash, write_json
from ML.deep_research.layer2.backend.jobs import IncompleteResponseError, saved_entry, saved_text
from .pipeline.create_run import local_path


def request_options(record: dict) -> dict:
    """Bind only hosted web search, requiring its use without enforced JSON mode."""
    search = record["web_search"]
    return {
        "tools": [{"type": "web_search", "search_context_size": search["context_size"],
                   "external_web_access": True}],
        "tool_choice": search["tool_choice"],
        "include": ["web_search_call.action.sources"],
        "text": {"verbosity": search["verbosity"]},
    }


def prepare(run: Path, record: dict, domain: dict, profile: dict) -> tuple:
    """Assemble complete fresh messages, their fingerprint and the effective input ceiling."""
    prompt = saved_text(run / "_internal/inputs/prompts/source_finder.md")
    request = messages(prompt, {
        "source_suggestions": saved_text(run / "_internal/inputs/source_suggestion.md"),
        "asset_metadata": saved_text(run / "_internal/inputs/asset_metadata.md"),
        "domain_context": saved_text(local_path(run, domain["input_path"])),
    })
    options = request_options(record)
    policy = record["context_policy"]
    frozen = {key: record[key] for key in (
        "model", "reasoning_effort", "provider_max_retries", "timeout_seconds",
        "context_policy", "model_input_token_limit", "public_input_confirmed", "web_search",
    )}
    fingerprint = text_hash(json.dumps(
        [frozen, options, domain, [text_hash(m.content) for m in request]], sort_keys=True))
    count = estimate(request, policy["framing_reserve"], options)
    ceiling = min(policy["maximum_tokens"], record["model_input_token_limit"],
                  profile.get("max_input_tokens") or record["model_input_token_limit"],
                  record["web_search"]["input_token_limit"])
    return request, fingerprint, count, ceiling


def recover(run: Path, key: str, fingerprint: str, previous: dict) -> tuple[dict, bool]:
    """Reuse an intact completed response even if the run record missed its last save."""
    if previous.get(key, {}).get("response_path"):
        local_path(run, previous[key]["response_path"])
    entry = saved_entry(run, key, fingerprint, previous)
    path = local_path(run, entry["response_path"]) if entry.get("response_path") else None
    raw = saved_text(path) if path else None
    complete = raw is not None and (entry.get("model_completed") or entry.get("status") == "complete")
    if raw is not None and not complete and entry.get("error_type") != "IncompleteResponseError":
        raise ValueError("Response exists without completion metadata; preserve it for manual recovery")
    if complete and text_hash(raw) != entry.get("response_sha256"):
        raise ValueError("Saved source response changed; restore the preserved response")
    if complete:
        entry.update(status="complete", error_type="")
    return entry, complete


def save_response(run: Path, entry: dict, result: AIMessage) -> None:
    """Save exact text and provider trace before interpretation, including incomplete output."""
    if not isinstance(result, AIMessage):
        raise TypeError("Source finder did not return an assistant message")
    path = local_path(run, entry["response_path"])
    atomic_write_text(path, result.text)
    info = result.response_metadata
    incomplete = info.get("status") == "incomplete" or info.get("finish_reason") == "length"
    entry.update(
        status="failed" if incomplete else "complete",
        model_completed=not incomplete,
        error_type="IncompleteResponseError" if incomplete else "",
        response_id=result.id, response_sha256=text_hash(result.text),
        provider={key: info[key] for key in (
            "id", "model_name", "finish_reason", "status", "incomplete_details") if key in info},
    )
    blocks = result.content if isinstance(result.content, list) else []
    blocks = [*blocks, *(result.additional_kwargs.get("tool_outputs") or [])]
    actions = {}
    for block in blocks:
        if isinstance(block, dict) and block.get("type") == "web_search_call":
            action = (block.get("action") or {}).get("type", "unknown")
            # Counts are operational only; arbitrary action strings never enter run.log.
            action = action if action in {"search", "open_page", "find_in_page"} else "unknown"
            actions[action] = actions.get(action, 0) + 1
    entry["web_actions"] = actions
    write_json(path.with_name("provider_message.json"), result.model_dump(mode="json"))
    write_json(path.with_name("completion.json"), entry)
    if incomplete:
        raise IncompleteResponseError("Provider reported incomplete output")

"""Rebuild source JSON views from exact responses, with observational warnings only."""

import json
from decimal import Decimal
from pathlib import Path

from ML.deep_research.layer2.backend.fs import atomic_write_text, storage_path, text_hash, write_json
from ML.deep_research.layer2.backend.jobs import saved_text
from ML.deep_research.layer2.backend.publication import ObjectMembers
from .pipeline.create_run import local_path, require_current


def _invalid_constant(value: str) -> None:
    """Reject non-JSON numeric constants at the serialization boundary."""
    raise ValueError("Non-JSON constant")


def parse_json(text: str):
    """Parse serialization without losing duplicate members or rejecting unconventional values."""
    return json.loads(text, object_pairs_hook=ObjectMembers, parse_float=Decimal,
                      parse_constant=_invalid_constant)


def pretty_json(text: str, registry: dict | None = None) -> str | None:
    """Render valid JSON hierarchically, optionally adding trusted document-upload fields."""
    try:
        value = parse_json(text)
        if registry is not None:
            from .document_records import enrich

            value = enrich(value, registry)

        def render(item, level=0):
            """Recursively render one parsed JSON value without collapsing object members."""
            indent, child = "  " * level, "  " * (level + 1)
            if isinstance(item, ObjectMembers):
                if not item:
                    return "{}"
                rows = [f"{child}{json.dumps(key, ensure_ascii=False)}: {render(value, level + 1)}"
                        for key, value in item]
                return "{\n" + ",\n".join(rows) + f"\n{indent}}}"
            if isinstance(item, list):
                if not item:
                    return "[]"
                return "[\n" + ",\n".join(f"{child}{render(value, level + 1)}"
                                           for value in item) + f"\n{indent}]"
            if isinstance(item, Decimal):
                return str(item)
            return json.dumps(item, ensure_ascii=False, allow_nan=False)

        return render(value) + "\n"
    except (ValueError, RecursionError):
        return None


def is_json(text: str) -> bool:
    """Check serialization only; no required fields, coverage checks or content grading."""
    return pretty_json(text) is not None


def _view(run: Path, relative: str, text: str | None) -> None:
    """Archive previous bytes before replacing or removing one rebuildable presentation."""
    target = local_path(run, relative)
    old = saved_text(target)
    if old == text:
        return
    if old is not None:
        history = storage_path(
            run / "_internal/trace/presentation_history" / text_hash(old) / relative
        )
        if not history.exists():
            atomic_write_text(history, old)
    if text is None:
        target.unlink(missing_ok=True)
    else:
        atomic_write_text(target, text)


def publish(run: Path) -> dict:
    """Publish readable JSON views; preserve malformed/unavailable material via trace links."""
    record = require_current(run)
    from .document_records import REGISTRY_PATH
    from ML.deep_research.layer2.backend.fs import load_json

    registry = load_json(run / REGISTRY_PATH) if (run / REGISTRY_PATH).exists() else None
    issues, links = [], []
    for domain in record["domains"]:
        key = domain["key"]
        entry = record["jobs"].get(key, {})
        relative = entry.get("response_path")
        raw = saved_text(local_path(run, relative)) if relative else None
        active = registry
        if raw is not None and registry is not None and f"{key}:{text_hash(raw)}" not in registry.get("active_sources", []):
            active = {}  # A new source response has not yet entered the upload workflow.
        formatted = pretty_json(raw, active) if raw is not None else None
        if entry.get("status") == "complete" and formatted is not None:
            _view(run, domain["output_path"], formatted)
            links.append(f"- [{Path(domain['output_path']).name}]({domain['output_path']})")
            if not local_path(run, relative).with_name("provider_message.json").is_file():
                issues.append({"job": key, "status": "complete", "kind": "provider_trace_unavailable",
                               "response_path": relative})
        else:
            _view(run, domain["output_path"], None)
            issues.append({"job": key, "status": entry.get("status", "pending"),
                           "kind": "unreadable_json" if entry.get("status") == "complete"
                           else "unavailable_response", "response_path": relative})
    audit = "_internal/trace/source_issues.json"
    write_json(run / audit, {"issues": issues})
    warnings = []
    for item in issues:
        link = f"[raw response]({item['response_path']})" if item["response_path"] else "no response saved"
        warnings.append(f"- {item['job']}: {item['kind']} ({item['status']}); {link}.")
    uploads = ""
    if registry is not None:
        counts = registry.get("counts", {})
        warning = " Preparation completed with upload warnings." if registry.get("status") == "partial" else ""
        uploads = (f"\n\nDocument uploads: {registry.get('status', 'pending')}; "
                   f"{counts.get('uploaded_files', 0)} unique files accepted, "
                   f"{counts.get('failed_urls', 0)} unresolved document URLs.{warning} "
                   f"[Upload receipts and issues]({REGISTRY_PATH}).\n"
                   "Upload acceptance does not prove readability. Files remain until manually deleted.\n")
    research = record.get("research")
    research_text = "\n\nResearch preparation ends here. No deep research or synthesis was run. "
    if research:
        jobs = research.get("jobs", {})
        reports = [f"- [{Path(j['output_path']).name}]({j['output_path']})"
                   for j in jobs.values() if j.get("status") == "complete"]
        gaps = [f"- {key}: {j.get('status')}; [retained work]({j['root']}/)."
                for key, j in jobs.items() if j.get("root") and
                (j.get("status") != "complete" or j.get("empty_response"))]
        research_text = (f"\n\n## Domain research\n\nStatus: {research['status']}; "
                         f"{len(reports)}/{len(record['domains'])} reports completed. No final synthesizer.\n\n"
                         + "\n".join(reports) + ("\n\nExecution/empty-response observations:\n\n" + "\n".join(gaps) if gaps else "")
                         + "\n\nCompletion records execution, not independently verified research coverage. ")
        if research.get("version") == 2:
            usage = [f"- {key}: {j['budget']['used']}/{research['maximum_calls']} calls used; "
                     f"{j['budget']['remaining']} remaining; {j['budget']['phase']}."
                     for key, j in jobs.items() if j.get("budget")]
            research_text += "\n\nLogical model calls (including failed/uncertain dispatched requests):\n\n" + "\n".join(usage)
            if research.get("prior_work"):
                research_text += "\n\nPrior research was copied into fresh threads; parent usage is separate:\n\n" + "\n".join(
                    f"- {key}: {item['notes']}; [prior work and parent usage]({item['path']}/manifest.json)."
                    for key, item in research["prior_work"].items())
    _view(run, "README.md",
          f"# Layer 3{' research' if research else ' source discovery'}\n\nStatus: {record['status']}\n\n"
          f"{len(links)}/{len(record['domains'])} JSON outputs published. [Log](run.log).\n\n"
          + "\n".join(links) + (
              f"\n\nWarnings: [internal observations]({audit})\n\n" + "\n".join(warnings)
              if issues else "")
          + uploads + research_text +
          "Access classifications are model-reported results through OpenAI at the time of testing; "
          "completion or valid JSON does not independently verify every URL. "
          "Provider action traces, raw responses and frozen inputs remain in _internal/.\n")
    return {"published_sources": len(links), "observations": len(issues)}

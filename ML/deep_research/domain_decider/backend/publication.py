"""ID-based JSON routing and recoverable Markdown views; never grade model content."""

import json
import shutil
from pathlib import Path
from uuid import uuid4

from .create_run import require_current
from .fs import atomic_write_text, sha256, slug, text_hash, write_json
from .jobs import saved_text


class ObjectMembers(list):
    """Preserve JSON object member order and duplicates instead of silently keeping the last value."""


def members(text: str, response: str, issues: list) -> list:
    """Input raw response text; return object members or retain unusable content in the routing audit."""
    try:
        value = json.loads(text, object_pairs_hook=ObjectMembers)
    except ValueError:
        value = text
    if isinstance(value, ObjectMembers):
        return value
    issues.append({"kind": "unusable_object", "response_path": response, "value": value})
    return []


def domain_definitions(text: str, response: str) -> tuple[dict, list]:
    """Input a raw plan; return usable ID definitions and all ambiguous or unprocessed values."""
    definitions, issues, seen = {}, [], set()
    for key, value in members(text, response, issues):
        if key != "domains" or not isinstance(value, list) or isinstance(value, ObjectMembers):
            issues.append({"kind": "unprocessed_plan_member", "response_path": response, "value": [key, value]})
            continue
        for row in value:
            if not isinstance(row, ObjectMembers) or len(dict(row)) != len(row):
                issues.append({"kind": "ambiguous_definition", "response_path": response, "value": row})
                if isinstance(row, ObjectMembers):
                    for field, identifier in row:
                        if field == "domain_id" and isinstance(identifier, str):
                            seen.add(identifier)
                            definitions.pop(identifier, None)
                continue
            item = dict(row)
            identifier, name = item.get("domain_id"), item.get("name")
            if not isinstance(identifier, str) or not identifier.strip() or not isinstance(name, str) or not name.strip():
                issues.append({"kind": "unusable_definition", "response_path": response, "value": row})
                continue
            if identifier in seen:
                issues.append({"kind": "duplicate_domain_id", "response_path": response, "value": row,
                               "previous": definitions.pop(identifier, None)})
                continue
            seen.add(identifier)
            duties = item.get("responsibilities", [])
            if isinstance(duties, str):
                duties = [duties]
            usable = [duty for duty in duties if isinstance(duty, str)] if isinstance(duties, list) else []
            definitions[identifier] = {"name": name, "responsibilities": usable}
            if (duties != usable or "responsibilities" not in item
                    or item.keys() - {"domain_id", "name", "responsibilities"}):
                issues.append({"kind": "unprocessed_definition_values", "response_path": response, "value": row})
    return definitions, issues


def domain_names(definitions: dict) -> dict[str, str]:
    """Input settled ID definitions; return safe, collision-resistant Windows/Linux filenames."""
    used, result = set(), {}
    reserved = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                *(f"lpt{i}" for i in range(1, 10))}
    for identifier, definition in definitions.items():
        filename = slug(definition["name"])[:80]
        if filename in used or filename in reserved:
            filename += "-" + text_hash(identifier)[:12]
        while filename in used:
            filename += "-domain"
        used.add(filename)
        result[identifier] = f"domains/{filename}.md"
    return result


def materialize(run: Path, revision: Path) -> None:
    """Input finished views; archive previous bytes before atomic per-file replacements or removal."""
    names = [p.relative_to(revision) for p in revision.rglob("*") if p.is_file()]
    existing = list((run / "domains").glob("*.md"))
    existing += [run / n for n in ("README.md", "asset_metadata.md", "domain_plan.md", "domain_plan.json",
                                  "_internal/trace/routing_issues.json") if (run / n).exists()]
    old = {p.relative_to(run).as_posix(): sha256(p) for p in existing}
    new = {p.as_posix(): sha256(revision / p) for p in names}
    if old == new:
        return
    archive = run / "_internal/trace/presentation_history" / text_hash(json.dumps(old, sort_keys=True))[:20]
    for name in old:
        target = archive / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(run / name, target)
    for name in names:
        target = run / name
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
        try:
            shutil.copyfile(revision / name, temporary)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
    for name in old.keys() - new.keys():
        (run / name).unlink()  # Exact replaced view is recoverable in presentation_history.


def publish(run: Path) -> dict:
    """Input current saved jobs; publish ID-routed text and retain unprocessed values internally."""
    record = require_current(run)
    jobs = record["jobs"]
    complete = {key: job for key, job in sorted(jobs.items()) if job["status"] == "complete"}
    metadata = [job for job in complete.values() if job["stage"] == "metadata"]
    design = complete.get("design/000001")
    revision = run / "_internal/trace/publications" / uuid4().hex
    revision.mkdir(parents=True)
    if metadata:
        shutil.copyfile(run / metadata[-1]["response_path"], revision / "asset_metadata.md")
    definitions, issues = {}, []
    if design:
        plan = saved_text(run / design["response_path"])
        definitions, issues = domain_definitions(plan, design["response_path"])
        overview = "# Research domains\n\n" + "\n\n".join(
            f"## {definition['name']}\n\n" + "\n".join(
                f"- {duty}" for duty in definition["responsibilities"])
            for definition in definitions.values())
        if not definitions:
            overview += "No usable domain definitions. See the internal routing observations."
        overview += f"\n\n[Original designer response]({design['response_path']})\n"
        atomic_write_text(revision / "domain_plan.md", overview)
    filenames = domain_names(definitions)
    for identifier, definition in definitions.items():
        duties = "\n".join(f"- {duty}" for duty in definition["responsibilities"])
        atomic_write_text(revision / filenames[identifier],
                          f"# {definition['name']}\n\n## Research responsibilities\n{duties}\n")
    for job in complete.values():
        if job["stage"] != "distribution":
            continue
        response = job["response_path"]
        for identifier, body in members(saved_text(run / response), response, issues):
            if identifier in definitions and isinstance(body, str):
                with (revision / filenames[identifier]).open("a", encoding="utf-8", newline="") as handle:
                    handle.write("\n\n" + body)
            else:
                issues.append({"kind": "unrouted_contribution", "response_path": response,
                               "domain_id": identifier, "value": body})
    for key, job in jobs.items():
        if job["status"] != "complete":
            issues.append({"kind": "incomplete_job", "job": key, "status": job["status"],
                           "error_type": job.get("error_type", ""), "response_path": job.get("response_path")})
    expected = record["source_windows"] * 2 + 1
    if len(complete) != expected:
        issues.append({"kind": "workflow_incomplete", "completed": len(complete), "expected": expected})
    if not definitions:
        issues.append({"kind": "no_usable_domains"})
    audit_path = "_internal/trace/routing_issues.json"
    write_json(revision / audit_path, {"object_values_are_member_pairs": True, "issues": issues})
    links = "\n".join(f"- [{definitions[key]['name'].replace('[', '').replace(']', '')}]({path})"
                      for key, path in filenames.items())
    warning = f"\n\nWarning: {len(issues)} operational/routing observations. [Details]({audit_path})." if issues else ""
    atomic_write_text(revision / "README.md",
                      f"# Layer 2 results\n\nStatus: {record['status']}\n\n"
                      f"{len(complete)}/{expected} logical calls complete · {len(definitions)} domains\n\n"
                      "[Asset metadata](asset_metadata.md) · [Domain plan](domain_plan.md) · [Log](run.log)\n\n"
                      + links + warning + "\n\nRouting does not measure extraction completeness. "
                      "Schema 9 is not yet integrated with Layers 3/4. Domain Markdown and shared asset metadata "
                      "are the research inputs. Raw responses and history remain in `_internal/`.\n")
    write_json(run / "_internal/trace/publication.json", {"path": revision.relative_to(run).as_posix()})
    materialize(run, revision)
    return {"domain_count": len(definitions), "routing_issues": len(issues), "audit_path": audit_path}

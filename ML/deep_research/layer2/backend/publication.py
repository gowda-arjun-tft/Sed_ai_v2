"""Readable, rebuildable domain views of preserved records; no model calls or grading."""

import json
import shutil
from pathlib import Path
from urllib.parse import quote

from ..ML.context import dump
from .fs import atomic_write_text, load_json, slug, text_hash, write_json
from .records import resolve_assignments


def readable(value, depth: int = 0) -> str:
    """Input arbitrary JSON; render all values as readable Markdown, preserving unusual shapes."""
    if isinstance(value, str):
        return value
    if not isinstance(value, (dict, list)) or not value:
        return json.dumps(value, ensure_ascii=False)
    if depth > 5:
        return "\n~~~~json\n" + dump(value) + "\n~~~~"
    items = value.items() if isinstance(value, dict) else enumerate(value, 1)
    lines = []
    for key, child in items:
        label = str(key).replace("_", " ") if isinstance(value, dict) else str(key)
        body = readable(child, depth + 1).replace("\n", "\n  ")
        lines.append(f"- **{label}:** {body}")
    return "\n".join(lines)


def domain_names(definitions: list) -> dict:
    """Input app-ID domain definitions; return collision-safe Windows filenames, never host paths."""
    names, used = {}, set()
    reserved = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                *(f"lpt{i}" for i in range(1, 10))}
    for domain in definitions:
        identity = domain["domain_id"]
        title = domain["definition"].get("name", identity)
        name = slug(str(title))[:80] or identity
        if name in used or name in reserved:
            name = f"{name}-{identity}"
        while name in used:
            name += "-domain"
        used.add(name)
        names[identity] = f"domains/{name}.md"
    return names


def domain_markdown(definition: dict, facts: list) -> str:
    """Input a domain definition and assigned records; return research prose without audit metadata."""
    blocks = [f"# {definition.get('name', 'Unnamed domain')}", "## Research responsibilities"]
    duties = definition.get("responsibilities", [])
    if isinstance(duties, list):
        blocks.append("\n".join("- " + readable(duty).replace("\n", "\n  ") for duty in duties))
    else:
        blocks.append(readable(duties))
    groups = {}
    for record in facts:
        body = record["body"]
        section = body.get("section") if isinstance(body, dict) else None
        usable = isinstance(section, str) and section.strip() and "\n" not in section and "\r" not in section
        heading = section.strip() if usable else "Other supplied facts"
        if isinstance(body, dict):
            details = {key: value for key, value in body.items()
                       if key != "source" and not (key == "section" and usable)
                       and not (key == "means" and value in (None, "", [], {}))}
            if "fact" in details:
                text = "- " + readable(details.pop("fact")).replace("\n", "\n  ")
                if details:
                    text += "\n  " + readable(details).replace("\n", "\n  ")
            else:
                text = readable(details)
        else:
            text = "- " + readable(body).replace("\n", "\n  ")
        groups.setdefault(heading, []).append(text)
    for heading, entries in groups.items():
        blocks.extend([f"## {heading}", "\n\n".join(entries)])
    if not facts:
        blocks.append("No recorded facts assigned. This is not evidence that no relevant facts exist.")
    return "\n\n".join(blocks) + "\n"


def materialize(run: Path, texts: dict) -> None:
    """Input a committed revision; refresh its public views, archiving replaced bytes first."""
    existing = [p for p in (run / "domains").glob("*.md")]
    existing += [run / name for name in ("README.md", "domain_plan.md", "unresolved.md")
                 if (run / name).is_file()]
    old = {p.relative_to(run).as_posix(): p.read_bytes() for p in existing}
    new = {name: text.encode("utf-8") for name, text in texts.items()}
    if old == new:
        return
    # Archive even user-edited visible views before refreshing; revisions remain authoritative.
    identity = text_hash(dump({k: v.hex() for k, v in sorted(old.items())}))[:20]
    archive = run / "_internal/trace/presentation_history" / identity
    for name in old:
        target = archive / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(run / name, target)
    for name, text in texts.items():
        atomic_write_text(run / name, text)
    for name in old.keys() - texts.keys():
        (run / name).unlink()  # Recoverable above; only previous Markdown view files.


def publish(run: Path, definitions: list, facts: list, responses: list, audit: list,
            *, profile: str = "", observations: list = ()) -> dict:
    """Input preserved records and decisions; save a revision, refresh Markdown and return counts."""
    ownership, decisions = resolve_assignments(definitions, facts, responses, audit)
    unowned = sum(not owners for owners in ownership.values())
    coverage = {"recorded_facts": len(facts), "owned_facts": len(facts) - unowned,
                "unresolved_facts": unowned, "audit_items": len(audit),
                "domain_count": len(definitions), "path": "domains"}
    record = load_json(run / "run.json")
    status = "partial" if any(j["status"] == "failed" for j in record["jobs"].values()) else "complete"
    names = domain_names(definitions)
    texts = {}
    for domain in definitions:
        identity, body = domain["domain_id"], domain["definition"]
        assigned = [fact for fact in facts if identity in ownership[fact["fact_id"]]]
        texts[names[identity]] = domain_markdown(body, assigned)
    domains = load_json(run / "_internal/domains.json")
    texts["domain_plan.md"] = "\n\n".join([
        "# Domain plan", "## Subject overview", profile,
        "## Initial domains", readable(domains["initial"]),
        "## Review observations and change reasons", readable(list(observations)),
        "## Final domains", readable(definitions),
    ]) + "\n"
    if audit:
        blocks = ["# Unassigned and unprocessed material",
                  "Preserved values below could not be represented fully in the normal outputs. "
                  "They were not graded, repaired or automatically retried. "
                  "Assignment coverage concerns recorded facts, not complete source extraction."]
        for index, item in enumerate(audit, 1):
            blocks += [f"## Item {index}", readable(item)]
            path = item.get("response_path")
            if not path and item.get("job") in record["jobs"]:
                path = record["jobs"][item["job"]]["response_path"]
            if path:
                blocks.append(f"[Preserved response]({quote(path)})")
        texts["unresolved.md"] = "\n\n".join(blocks) + "\n"
    links = "\n".join(f"- [{d['definition'].get('name', d['domain_id'])}]({quote(names[d['domain_id']])})"
                      for d in definitions)
    texts["README.md"] = (
        f"# Layer 2 results\n\nStatus: {status}\n\n"
        f"{len(definitions)} domains · {len(facts)} recorded facts · "
        f"{len(facts) - unowned} assigned · {unowned} unassigned · {len(audit)} audit items\n\n"
        "[Domain plan](domain_plan.md) · [Operational log](run.log)\n\n" + links + "\n\n"
        + ("[Unassigned and unprocessed material](unresolved.md)\n\n" if audit else "")
        + "Coverage does not prove complete source extraction. Schema 5 is not yet integrated "
        "with Layers 3/4. Preserved records, responses, usage and checkpoints are in `_internal/`.\n"
    )
    owners = load_json(run / "_internal/assignments.json")
    owners.update(final=decisions, active_fact_ids=[f["fact_id"] for f in facts])
    # Publish the internal commit only after every revision file exists. Interrupted views
    # are rebuilt from saved jobs on resume without asking the model to repair anything.
    revision = text_hash(dump([texts, domains, owners, audit]))[:20]
    root = run / "_internal/trace/publications" / revision
    for name, text in texts.items():
        atomic_write_text(root / name, text)
    write_json(root / "records.json", {"domains": domains, "assignments": owners, "audit": audit})
    write_json(run / "_internal/assignments.json", owners)
    write_json(run / "_internal/trace/publication.json", {"path": root.relative_to(run).as_posix()})
    materialize(run, texts)
    return coverage

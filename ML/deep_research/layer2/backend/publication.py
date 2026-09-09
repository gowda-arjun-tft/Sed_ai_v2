"""Readable, rebuildable domain views of preserved records; no model calls or grading."""

import json

from ..ML.context import dump
from .fs import slug


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
        heading, text = fact_markdown(record["body"])
        groups.setdefault(heading, []).append(text)
    for heading, entries in groups.items():
        blocks.extend([f"## {heading}", "\n\n".join(entries)])
    if not facts:
        blocks.append("No recorded facts assigned. This is not evidence that no relevant facts exist.")
    return "\n\n".join(blocks) + "\n"
def fact_markdown(body):
    """Input one immutable body; return its section and research prose without bookkeeping."""
    section = body.get("section") if isinstance(body, dict) else None
    usable = isinstance(section, str) and section.strip() and "\n" not in section and "\r" not in section
    heading = section.strip() if usable else "Other supplied facts"
    if isinstance(body, dict):
        details = {key: value for key, value in body.items()
                   if key not in {"source", "means", "applicability"}
                   and not (key == "section" and usable)}
        if "fact" in details:
            text = "- " + readable(details.pop("fact")).replace("\n", "\n  ")
            if details:
                text += "\n  " + readable(details).replace("\n", "\n  ")
        else:
            text = readable(details)
    else:
        text = "- " + readable(body).replace("\n", "\n  ")
    return heading, text

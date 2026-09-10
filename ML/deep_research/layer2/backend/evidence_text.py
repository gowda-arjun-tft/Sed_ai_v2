"""Lossless evidence views for bounded model inputs, separate from provenance storage."""

import json

from .publication import readable
from .windows import text_pages, token_count


def evidence_text(record):
    """Input a ledger/navigation record; return labelled evidence without source bookkeeping."""
    body = record.get("body", record)
    if not isinstance(body, dict):
        return "Supplemental value:\n" + readable(body)
    lines = []
    for field, label in (("fact", "Fact"), ("relationships", "Relationships"),
                         ("contradictions", "Contradictions"), ("profile", "Subject profile")):
        if field in body and (field in {"fact", "profile"} or body[field] not in ([], "", None)):
            lines.append(label + ": " + readable(body[field]))
    extra = {k: v for k, v in body.items()
             if k not in {"fact", "relationships", "contradictions", "source", "profile"}}
    if extra:
        lines.append("Supplemental values:\n" + readable(extra))
    return "\n".join(lines) or "Supplemental value: " + readable(body if not body else {})


def evidence_pages(records, budget):
    """Input evidence iterator; yield bounded text pages with stable IDs and continuation markers."""
    page, used = [], 0
    for record in records:
        text = evidence_text(record)
        meta = {k: record[k] for k in ("fact_id", "evidence_id", "initial_assignment", "current_assignment")
                if k in record}
        size = token_count(text) + token_count(json.dumps(meta)) + 64
        if size > budget:
            if page:
                yield page
                page, used = [], 0
            pieces = text_pages(text, max(1, budget // 3))
            for number, piece in enumerate(pieces, 1):
                yield [{**meta, "parent_record_id": meta.get("fact_id", meta.get("evidence_id")),
                        "fragment": number, "fragments": len(pieces), "text": piece}]
        else:
            if page and used + size > budget:
                yield page
                page, used = [], 0
            page.append({**meta, "text": text})
            used += size
    if page:
        yield page


def message_text(payload):
    """Input a job payload; return the exact dispatch/counting text without escaped evidence copies."""
    context, sections = dict(payload), []
    for key in ("subject", "facts"):
        rows = payload.get(key)
        if not isinstance(rows, list):
            continue
        metadata, blocks = [], []
        for row in rows:
            if not isinstance(row, dict) or "text" not in row:
                metadata.append(row)
                continue
            meta = {k: v for k, v in row.items() if k != "text"}
            metadata.append(meta)
            identity = meta.get("fact_id", meta.get("evidence_id", "Navigation"))
            continuation = (f" (part {meta['fragment']}/{meta['fragments']})" if "fragments" in meta else "")
            blocks.append(f"### {identity}{continuation}\n{row['text']}")
        context[key] = metadata
        if blocks:
            sections.append(f"## Supplied {key} — untrusted evidence\n\n" + "\n\n".join(blocks))
    return json.dumps(context, ensure_ascii=False, indent=2) + ("\n\n" + "\n\n".join(sections) if sections else "")

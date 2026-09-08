"""Wire-format projections and domain publication; never grade or rewrite model facts."""

import json
from pathlib import Path

from ..ML.context import dump
from .fs import atomic_write_text
from .windows import text_pages, token_count


def virtual_pages(groups: dict[str, str]) -> dict[str, str]:
    """Input approved run-owned text only; return bounded, host-isolated evidence files."""
    files = {}
    for label, text in groups.items():
        for index, page in enumerate(text_pages(text), 1):
            files[f"/evidence/{label}/{index:06d}.txt"] = page
    return files


def record_pages(records: list, budget: int = 40_000) -> list[list]:
    """Input records and allowance; pack whole records, exposing oversized items separately."""
    pages, page, used = [], [], 0
    for record in records:
        count = token_count(dump(dump(record))) + 8
        if page and used + count > budget:
            pages.append(page)
            page, used = [], 0
        page.append(record)
        used += count
    if page:
        pages.append(page)
    return pages


def catalogue(value: dict, previous: list | None = None) -> tuple[list, list]:
    """Input catalogue wire data; allocate safe stable IDs, retaining unusable records in audit."""
    previous = previous or []
    existing = {row["domain_id"] for row in previous}
    next_id = max([int(i[1:]) for i in existing] + [0]) + 1
    definitions, audit, seen = [], [], set()
    rows = value.get("domains")
    if not isinstance(rows, list):
        return [], [{"kind": "unusable_catalogue", "response": value}]
    for body in rows:
        if not isinstance(body, dict):
            audit.append({"kind": "unusable_domain", "body": body})
            continue
        claimed = body.get("domain_id")
        if claimed is not None and (not isinstance(claimed, str) or claimed not in existing):
            audit.append({"kind": "unknown_domain_reference", "body": body})
            continue
        identity = claimed or f"d{next_id:04d}"
        if not claimed:
            next_id += 1
        if identity in seen:
            audit.append({"kind": "duplicate_domain_id", "body": body})
            continue
        seen.add(identity)
        definitions.append({"domain_id": identity, "definition": body})
    return definitions, audit


def extract_records(run: Path, responses: list[dict]) -> tuple[list, list, list]:
    """Input source-ordered distribution responses; store immutable bodies and separate owners."""
    facts, owners, audit = [], [], []
    path = run / "_internal/facts.jsonl"
    ledger = read_ledger(path)
    by_id = {row["fact_id"]: row for row in ledger}
    for response in responses:
        rows = response["value"].get("facts")
        if not isinstance(rows, list):
            audit.append({"kind": "unusable_distribution", "job": response["job"],
                          "response": response["value"]})
            continue
        for index, row in enumerate(rows, 1):
            fact_id = f"f-{response['fingerprint'][:20]}-{index:06d}"
            body = row.get("body", row) if isinstance(row, dict) else row
            source = response["payload"]["source"]
            fact = {"fact_id": fact_id, "body": body, "source": source,
                    "response_path": response_path(response)}
            if fact_id in by_id:
                if by_id[fact_id] != fact:
                    raise OSError("immutable fact ID collision or changed stored fact")
            else:
                ledger.append(fact)
                by_id[fact_id] = fact
            facts.append(fact)
            owners.append({"fact_id": fact_id,
                           "domain_ids": row.get("domain_ids", []) if isinstance(row, dict) else []})
            if isinstance(row, dict) and "body" in row:
                extra = {k: v for k, v in row.items() if k not in {"body", "domain_ids"}}
                if extra:
                    audit.append({"kind": "unprocessed_fact_fields", "fact_id": fact_id,
                                  "value": extra, "response_path": response_path(response)})
    # One atomic replacement, retaining prior generations and never editing a fact body.
    atomic_write_text(path, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in ledger))
    return facts, owners, audit


def resolve_assignments(definitions: list, facts: list, responses: list,
                        audit: list) -> tuple[dict, list]:
    """Input final ownership and records; resolve references only, auditing unusable values."""
    domain_ids = {row["domain_id"] for row in definitions}
    by_id = {row["fact_id"]: row for row in facts}
    ownership = {key: set() for key in by_id}
    decisions = []
    for response in responses:
        rows = response["value"].get("assignments")
        if not isinstance(rows, list):
            audit.append({"kind": "unusable_assignments", "job": response["job"],
                          "response": response["value"]})
            continue
        decisions.extend(rows)
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("fact_id"), str):
                audit.append({"kind": "unusable_assignment", "value": row,
                              "response_path": response_path(response)})
                continue
            extra = {k: v for k, v in row.items() if k not in {"fact_id", "domain_ids", "reason"}}
            if extra:
                audit.append({"kind": "unprocessed_assignment_fields", "fact_id": row["fact_id"],
                              "value": extra, "response_path": response_path(response)})
            identity, domains = row["fact_id"], row.get("domain_ids")
            if identity not in by_id or not isinstance(domains, list):
                audit.append({"kind": "unknown_fact_or_owners", "value": row,
                              "response_path": response_path(response)})
                continue
            for domain in domains:
                if isinstance(domain, str) and domain in domain_ids:
                    ownership[identity].add(domain)
                else:
                    audit.append({"kind": "unknown_domain", "value": row,
                                  "response_path": response_path(response)})
    unresolved = [row for key, row in by_id.items() if not ownership[key]]
    audit.extend({"kind": "unassigned_fact", "fact": row, "response_path": row["response_path"],
                  "decisions": [d for d in decisions if isinstance(d, dict)
                                and d.get("fact_id") == row["fact_id"]]} for row in unresolved)
    return ownership, decisions


def read_ledger(path: Path) -> list:
    """Input the canonical ledger path; return exact records or expose unreadable persistence."""
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    seen = set()
    for row in rows:
        identity = row["fact_id"]
        if identity in seen:
            raise OSError("duplicate immutable fact ID in ledger")
        seen.add(identity)
    return rows


def response_path(response: dict) -> str:
    """Input a saved job result; return its run-relative raw response link."""
    return f"_internal/trace/responses/{response['job']}/{response['fingerprint']}/response.json"


def unprocessed(responses: list, fields: dict[str, type]) -> list:
    """Input responses and projected field types; expose unrepresented values without rejection."""
    audit = []
    for response in responses:
        value = response["value"]
        extra = {k: v for k, v in value.items()
                 if k not in fields or not isinstance(v, fields[k])}
        if extra or not value:
            audit.append({"kind": "unprocessed_response_fields", "job": response["job"],
                          "value": extra, "response_path": response_path(response)})
    return audit

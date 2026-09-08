"""Wire-format projections and domain publication; never grade or rewrite model facts."""

from pathlib import Path

from ..ML.context import dump
from .fs import atomic_write_text, load_json, text_hash, write_json
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
                    "response_path": f"responses/{response['job']}/{response['fingerprint']}/response.json"}
            path = run / "facts" / f"{fact_id}.json"
            if path.exists():
                if load_json(path) != fact:
                    raise OSError("immutable fact ID collision or changed stored fact")
            else:
                write_json(path, fact)
            facts.append(fact)
            owners.append({"fact_id": fact_id,
                           "domain_ids": row.get("domain_ids", []) if isinstance(row, dict) else []})
    return facts, owners, audit


def publish(run: Path, definitions: list, facts: list, responses: list,
            audit: list) -> dict:
    """Input final ownership and immutable records; publish usable links and disclose all others."""
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
                audit.append({"kind": "unusable_assignment", "value": row})
                continue
            identity, domains = row["fact_id"], row.get("domain_ids")
            if identity not in by_id or not isinstance(domains, list):
                audit.append({"kind": "unknown_fact_or_owners", "value": row})
                continue
            for domain in domains:
                if isinstance(domain, str) and domain in domain_ids:
                    ownership[identity].add(domain)
                else:
                    audit.append({"kind": "unknown_domain", "fact_id": identity, "domain": domain})
    unresolved = [row for key, row in by_id.items() if not ownership[key]]
    audit.extend({"kind": "unassigned_fact", "fact": row} for row in unresolved)
    write_json(run / "review" / "final_assignments.json", decisions)
    # Version publications: changed upstream inputs never destroy the prior domain files.
    publication_id = text_hash(dump([definitions, facts, decisions, audit]))[:20]
    root = run / "publications" / publication_id
    for domain in definitions:
        identity = domain["domain_id"]
        assigned = [row for row in facts if identity in ownership[row["fact_id"]]]
        value = {"domain": domain, "facts": assigned}
        write_json(root / "domains" / identity / "facts.json", value)
        title = domain["definition"].get("name", identity)
        text = f"# {title}\n\n" + "\n\n".join(
            f"## {row['fact_id']}\n\n{dump(row['body'])}\n\nSource:\n{dump(row['source'])}"
            for row in assigned
        )
        atomic_write_text(root / "domains" / identity / "facts.md", text + "\n")
    write_json(root / "unresolved_facts.json", audit)
    atomic_write_text(root / "unresolved_facts.md",
                      "# Assignment audit\n\n" + dump(audit) +
                      "\n\nCoverage concerns recorded facts only, not extraction completeness.\n")
    write_json(run / "publication.json", {"path": root.relative_to(run).as_posix()})
    return {"recorded_facts": len(facts), "owned_facts": len(facts) - len(unresolved),
            "unresolved_facts": len(unresolved), "audit_items": len(audit),
            "domain_count": len(definitions), "path": root.relative_to(run).as_posix()}

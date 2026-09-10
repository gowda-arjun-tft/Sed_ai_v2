"""Stream raw responses into immutable facts, explicit domains and observable audits."""

import json
from contextlib import contextmanager
from uuid import uuid4

from .fs import text_hash


@contextmanager
def atomic_text(path):
    """Input output path; yield a UTF-8 stream and replace only after successful close."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            yield handle
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def write_arrays(path, **collections):
    """Input named iterators; atomically write their JSON arrays without collecting values."""
    with atomic_text(path) as handle:
        handle.write("{")
        for number, (name, rows) in enumerate(collections.items()):
            handle.write(("," if number else "") + json.dumps(name) + ":[")
            for i, row in enumerate(rows):
                handle.write(("," if i else "") + json.dumps(row, ensure_ascii=False))
            handle.write("]")
        handle.write("}\n")


def audit(store, kind, **details):
    """Input a structural observation; retain its complete values independently of execution status."""
    value = {"kind": kind, **details}
    identity = text_hash(json.dumps(value, ensure_ascii=False, sort_keys=True))
    store.put("audit", identity, value)


def observe_response(store, response, fields):
    """Input any completed object and recognized projections; preserve unprocessed fields visibly."""
    value = response["value"]
    extra = {k: v for k, v in value.items() if k not in fields or not isinstance(v, fields[k])}
    if extra or not value:
        audit(store, "unprocessed_response_fields", value=extra, job=response["job"],
              response_path=response["response_path"])
    store.add_text("responses/" + response["job"], json.dumps(value, ensure_ascii=False))


def load_ledger(store):
    """Input run index; rebuild immutable ledger lookup one JSON line at a time."""
    store.clear("ledger", "facts", "initial_owners", "final_owners", "decisions",
                "audit", "observations", "subject", "dispositions", "planning", "patch_votes", "replacement_votes")
    with store.connect() as db:
        db.execute("DELETE FROM owners")
    path = store.run / "_internal/facts.jsonl"
    if path.exists():
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                value = json.loads(line)
                identity = value["fact_id"]
                if store.get("ledger", identity) is not None:
                    raise OSError("duplicate immutable fact ID in ledger")
                store.put("ledger", identity, value)


def ingest_facts(store, response):
    """Input one understanding response; identify immutable evidence without interpreting its content."""
    rows = response["value"].get("evidence", [])
    if not isinstance(rows, list):
        return
    version = text_hash(json.dumps([store.run.name, response["job"], response["value"]],
                                   ensure_ascii=False, sort_keys=True))
    for i, row in enumerate(rows, 1):
        identity = f"f-{version[:20]}-{i:06d}"
        fact = {"fact_id": identity, "body": row,
                "source": response["payload"]["source"], "response_path": response["response_path"]}
        old = store.get("ledger", identity)
        if old is not None and old != fact:
            raise OSError("immutable fact ID collision or changed stored fact")
        store.put("ledger", identity, fact)
        store.put("facts", identity, fact)
        store.put("planning", identity, {"fact_id": identity})


def save_ledger(store):
    """Input the rebuilt immutable projection; atomically stream all historical generations."""
    with atomic_text(store.run / "_internal/facts.jsonl") as handle:
        for fact in store.rows("ledger"):
            handle.write(json.dumps(fact, ensure_ascii=False) + "\n")


def apply_domains(store, response):
    """Input explicit domain additions/replacements; carry untouched IDs and expose unusable values."""
    observe_response(store, response, {"domains": list, "dispositions": list})
    rows = response["value"].get("domains", [])
    if not isinstance(rows, list):
        rows = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            audit(store, "unusable_domain", value=row, response_path=response["response_path"])
            continue
        claimed = row.get("domain_id")
        if claimed is not None and (not isinstance(claimed, str) or store.get("domains", claimed) is None or claimed in seen):
            audit(store, "unknown_or_conflicting_domain_reference", value=row,
                  response_path=response["response_path"])
            continue
        identity = claimed or f"d{store.count('domains') + 1:04d}"
        seen.add(identity)
        previous = store.get("domains", identity)
        definition = {**(previous["definition"] if previous else {}), **row}
        store.put("domains", identity, {"domain_id": identity, "definition": definition})
    dispositions = response["value"].get("dispositions", [])
    if isinstance(dispositions, list):
        for row in dispositions:
            identity = row.get("proposal_id") if isinstance(row, dict) else None
            if not isinstance(identity, str) or store.get("observations", identity) is None:
                audit(store, "unusable_disposition", value=row, response_path=response["response_path"])
            else:
                previous = store.get("dispositions", identity)
                if previous is not None and previous != row:
                    audit(store, "conflicting_dispositions", previous=previous, value=row,
                          response_path=response["response_path"])
                store.put("dispositions", identity, row)

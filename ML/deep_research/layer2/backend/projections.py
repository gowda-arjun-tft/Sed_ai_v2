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
    store.clear("ledger", "facts", "initial_owners", "final_owners", "decisions", "initial_decisions",
                "audit", "observations", "subject", "dispositions")
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
    """Input one source response; preserve each body once and separate initial ownership."""
    observe_response(store, response, {"facts": list})
    rows = response["value"].get("facts", [])
    if not isinstance(rows, list):
        return
    for i, row in enumerate(rows, 1):
        identity = f"f-{response['fingerprint'][:20]}-{i:06d}"
        fact = {"fact_id": identity, "body": row.get("body", row) if isinstance(row, dict) else row,
                "source": response["payload"]["source"], "response_path": response["response_path"]}
        old = store.get("ledger", identity)
        if old is not None and old != fact:
            raise OSError("immutable fact ID collision or changed stored fact")
        store.put("ledger", identity, fact)
        store.put("facts", identity, fact)
        domains = row.get("domain_ids", []) if isinstance(row, dict) else []
        if not isinstance(domains, list):
            audit(store, "unusable_initial_owners", value=domains, fact_id=identity,
                  response_path=response["response_path"])
            domains = []
        valid = []
        for domain in domains:
            if isinstance(domain, str) and store.get("domains", domain) is not None:
                valid.append(domain)
            else:
                audit(store, "unknown_initial_owner", value=domain, fact_id=identity,
                      response_path=response["response_path"])
        store.put("initial_owners", identity, {"fact_id": identity, "domain_ids": valid})
        if isinstance(row, dict) and "body" in row:
            extra = {k: v for k, v in row.items() if k not in {"body", "domain_ids"}}
            if extra:
                audit(store, "unprocessed_fact_fields", fact_id=identity, value=extra,
                      response_path=response["response_path"])


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


def apply_owners(store, response, *, initial=False):
    """Input ownership rows; combine explicit IDs and expose unknown references without grading."""
    observe_response(store, response, {"assignments": list})
    rows = response["value"].get("assignments", [])
    if not isinstance(rows, list):
        return
    supplied = {f.get("fact_id") for f in response.get("payload", {}).get("facts", [])
                if isinstance(f, dict) and isinstance(f.get("fact_id"), str)}
    returned = {r.get("fact_id") for r in rows if isinstance(r, dict) and isinstance(r.get("fact_id"), str)}
    if supplied - returned:
        audit(store, "unresolved_comparison", fact_ids=sorted(supplied - returned),
              definition_page=response.get("payload", {}).get("domain_page"),
              response_path=response["response_path"])
    collection = "initial_owners" if initial else "final_owners"
    for i, row in enumerate(rows):
        store.put("initial_decisions" if initial else "decisions", response["fingerprint"] + str(i), row)
        identity = row.get("fact_id") if isinstance(row, dict) else None
        domains = row.get("domain_ids") if isinstance(row, dict) else None
        if not isinstance(identity, str) or store.get("facts", identity) is None or not isinstance(domains, list):
            audit(store, "unusable_assignments", value=row, response_path=response["response_path"])
            continue
        valid = []
        for domain in domains:
            if isinstance(domain, str) and store.get("domains", domain) is not None:
                valid.append(domain)
            else:
                audit(store, "unknown_domain", value=row, response_path=response["response_path"])
        prior = store.get(collection, identity) or {"fact_id": identity, "domain_ids": []}
        prior["domain_ids"] = list(dict.fromkeys(prior["domain_ids"] + valid))
        store.put(collection, identity, prior)
        if not initial:
            with store.connect() as db:
                db.executemany("INSERT OR IGNORE INTO owners VALUES(?,?)", [(identity, d) for d in valid])
        if not domains and row.get("reason"):
            audit(store, "unresolved_ownership_decision", value=row, response_path=response["response_path"])
        extras = {k: v for k, v in row.items() if k not in {"fact_id", "domain_ids", "reason"}}
        if extras:
            audit(store, "unprocessed_assignment_fields", value=extras, response_path=response["response_path"])

"""Explicit ID operations: initial unions, reviewer patches and bounded scope replacements."""

from .projections import audit, observe_response


def set_owners(store, identity, domains, *, initial=False):
    """Input fact ID and owners; persist one mapping and its rebuildable publication join."""
    domains = list(dict.fromkeys(domains))
    store.put("initial_owners" if initial else "final_owners", identity,
              {"fact_id": identity, "domain_ids": domains})
    if not initial:
        with store.connect() as db:
            db.execute("DELETE FROM owners WHERE fact_id=?", (identity,))
            db.executemany("INSERT INTO owners VALUES(?,?)", [(identity, d) for d in domains])


def owners(store, identity, *, initial=False):
    """Input a fact ID; return its current or initial owners without changing records."""
    row = store.get("initial_owners" if initial else "final_owners", identity)
    return row["domain_ids"] if row else []


def comparison_key(payload):
    """Input a finite comparison payload; return its fact/definition-page identity."""
    return f"{payload.get('fact_page', 1)}:{payload.get('domain_page', 1)}"


def expect_replacements(store, payload):
    """Input scheduled scope; register every comparison before dispatch, including later failures."""
    for fact in payload["facts"]:
        for domain in payload["final_domain_ids"]:
            identity = fact["fact_id"] + ":" + domain
            value = store.get("replacement_votes", identity) or {
                "fact_id": fact["fact_id"], "domain_id": domain, "scheduled": [], "votes": {}, "conflict": False}
            key = comparison_key(payload)
            if key not in value["scheduled"]:
                value["scheduled"].append(key)
            store.put("replacement_votes", identity, value)


def apply_owners(store, response, *, initial=False):
    """Input completed ID rows; union initial scopes or collect explicit final scoped replacements."""
    observe_response(store, response, {"assignments": list})
    payload = response.get("payload", {})
    supplied = {f["fact_id"] for f in payload.get("facts", []) if "fact_id" in f}
    scope = set(payload.get("final_domain_ids", []))
    rows = response["value"].get("assignments", [])
    rows = rows if isinstance(rows, list) else []
    returned = set()
    for i, row in enumerate(rows):
        if not initial:
            store.put("decisions", response["fingerprint"] + str(i), row)
        identity = row.get("fact_id") if isinstance(row, dict) else None
        domains = row.get("domain_ids") if isinstance(row, dict) else None
        if (not isinstance(identity, str) or store.get("facts", identity) is None
                or (supplied and identity not in supplied) or not isinstance(domains, list)):
            audit(store, "unusable_assignments", value=row, response_path=response["response_path"])
            continue
        if any(not isinstance(d, str) or store.get("domains", d) is None or (scope and d not in scope)
               for d in domains):
            audit(store, "unknown_domain", value=row, response_path=response["response_path"])
            continue
        returned.add(identity)
        if initial:
            set_owners(store, identity, owners(store, identity, initial=True) + domains, initial=True)
        else:
            for domain in scope:
                key = identity + ":" + domain
                value = store.get("replacement_votes", key)
                if value is None:
                    audit(store, "unscheduled_assignment", value=row, response_path=response["response_path"])
                    continue
                part, choice = comparison_key(payload), domain in domains
                if part in value["votes"] and value["votes"][part] != choice:
                    value["conflict"] = True
                value["votes"][part] = choice
                store.put("replacement_votes", key, value)
        extras = {k: v for k, v in row.items() if k not in {"fact_id", "domain_ids", "reason"}}
        if extras:
            audit(store, "unprocessed_assignment_fields", value=extras, response_path=response["response_path"])
        if not domains and row.get("reason"):
            audit(store, "unresolved_ownership_decision", value=row, response_path=response["response_path"])
    if supplied - returned:
        audit(store, "unresolved_comparison", fact_ids=sorted(supplied - returned),
              definition_page=payload.get("domain_page"), response_path=response["response_path"])


def apply_corrections(store, response):
    """Input reviewer ID patches; apply unambiguous operations, retaining baseline on conflicts."""
    rows = response["value"].get("corrections", [])
    if not isinstance(rows, list):
        return
    supplied = {f["fact_id"] for f in response["payload"].get("facts", []) if "fact_id" in f}
    for index, row in enumerate(rows):
        store.put("decisions", "patch:" + response["fingerprint"] + str(index), row)
        identity = row.get("fact_id") if isinstance(row, dict) else None
        add = row.get("add_domain_ids", []) if isinstance(row, dict) else None
        remove = row.get("remove_domain_ids", []) if isinstance(row, dict) else None
        if (not isinstance(identity, str) or store.get("facts", identity) is None or identity not in supplied
                or not isinstance(add, list) or not isinstance(remove, list)):
            audit(store, "unusable_correction", value=row, response_path=response["response_path"])
            continue
        extra = {k: v for k, v in row.items() if k not in {"fact_id", "add_domain_ids", "remove_domain_ids", "reason"}}
        if extra:
            audit(store, "unprocessed_correction_fields", value=extra, response_path=response["response_path"])
        for operation, domains in (("add", add), ("remove", remove)):
            for domain in domains:
                if not isinstance(domain, str) or store.get("domains", domain) is None:
                    audit(store, "unknown_correction_domain", value=row, response_path=response["response_path"])
                    continue
                key = identity + ":" + domain
                vote = store.get("patch_votes", key) or {"operations": [], "responses": []}
                vote["operations"] = list(dict.fromkeys(vote["operations"] + [operation]))
                vote["responses"] = list(dict.fromkeys(vote["responses"] + [response["response_path"]]))
                store.put("patch_votes", key, vote)
                chosen = operation == "add"
                if len(vote["operations"]) > 1:
                    chosen = domain in owners(store, identity, initial=True)
                    audit(store, "conflicting_corrections", fact_id=identity, domain_id=domain, value=vote)
                current = [d for d in owners(store, identity) if d != domain]
                set_owners(store, identity, current + ([domain] if chosen else []))


def commit_replacements(store):
    """Input comparison votes; retain positive owners, but remove only after complete unambiguous scopes."""
    for value in store.rows("replacement_votes"):
        incomplete = set(value["scheduled"]) != set(value["votes"])
        if value["conflict"] or incomplete:
            audit(store, "incomplete_or_conflicting_scope", value=value)
            if value["conflict"] or not any(value["votes"].values()):
                continue
        identity, domain = value["fact_id"], value["domain_id"]
        current = [d for d in owners(store, identity) if d != domain]
        set_owners(store, identity, current + ([domain] if any(value["votes"].values()) else []))

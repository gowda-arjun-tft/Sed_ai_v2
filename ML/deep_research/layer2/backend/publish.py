"""Stream preserved records into versioned human-facing research views."""

import json
import shutil
from urllib.parse import quote
from uuid import uuid4

from .fs import load_json, sha256, text_hash, write_json
from .projections import atomic_text, audit, write_arrays
from .publication import domain_names, fact_markdown, readable


def write_domain(store, path, domain):
    """Input one domain; group its assigned facts on disk and stream a research-only view."""
    with store.connect() as db, atomic_text(path) as handle:
        db.execute("CREATE TEMP TABLE rendered (seq INTEGER PRIMARY KEY, section TEXT, body TEXT)")
        rows = db.execute("SELECT r.body FROM current_facts r JOIN owners o ON o.fact_id=r.id "
                          "WHERE o.domain_id=? ORDER BY r.seq", (domain["domain_id"],))
        for row in rows:
            section, text = fact_markdown(json.loads(row[0])["body"])
            db.execute("INSERT INTO rendered(section,body) VALUES(?,?)", (section, text))
        body = domain["definition"]
        handle.write(f"# {body.get('name', 'Unnamed domain')}\n\n## Research responsibilities\n\n")
        duties = body.get("responsibilities", [])
        if isinstance(duties, list):
            for duty in duties:
                handle.write("- " + readable(duty).replace("\n", "\n  ") + "\n")
        else:
            handle.write(readable(duties) + "\n")
        count = 0
        for (section,) in db.execute("SELECT section FROM rendered GROUP BY section ORDER BY min(seq)"):
            handle.write(f"\n## {section}\n\n")
            for (text,) in db.execute("SELECT body FROM rendered WHERE section=? ORDER BY seq", (section,)):
                count += 1
                handle.write(text + "\n\n")
        if not count:
            handle.write("\nNo recorded facts assigned. This is not evidence that no relevant facts exist.\n")


def materialize(run, revision):
    """Input a completed revision; preserve previous bytes before refreshing each visible file."""
    names = [p.relative_to(revision) for p in revision.rglob("*.md")]
    existing = list((run / "domains").glob("*.md"))
    existing += [run / n for n in ("README.md", "domain_plan.md", "unresolved.md") if (run / n).exists()]
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
        shutil.copyfile(revision / name, temporary)
        temporary.replace(target)
    for name in old.keys() - new.keys():
        (run / name).unlink()  # Exact previous bytes are recoverable in the archive.


def publish(store):
    """Input preserved indexed records; stream a committed publication and return observational counts."""
    run, unowned = store.run, 0
    for fact in store.rows("facts"):
        owners = store.get("final_owners", fact["fact_id"])
        if not owners or not owners["domain_ids"]:
            unowned += 1
            audit(store, "unassigned_fact", fact=fact, response_path=fact["response_path"])
    coverage = {"recorded_facts": store.count("facts"), "owned_facts": store.count("facts") - unowned,
                "unresolved_facts": unowned, "audit_items": store.count("audit"),
                "domain_count": store.count("domains"), "path": "domains"}
    root = run / "_internal/trace/publications" / uuid4().hex
    names = domain_names(store.rows("domains"))
    for domain in store.rows("domains"):
        write_domain(store, root / names[domain["domain_id"]], domain)
    with atomic_text(root / "domain_plan.md") as handle:
        handle.write("# Domain plan\n\n## Subject overview\n\n")
        for subject in store.rows("subject"):
            handle.write(readable(subject.get("profile", subject)) + "\n\n")
        for label, collection in (("Initial domains", "initial_domains"),
                                  ("Review observations and change reasons", "observations"),
                                  ("Proposal dispositions", "dispositions"),
                                  ("Final domains", "domains")):
            handle.write(f"## {label}\n\n")
            for value in store.rows(collection):
                handle.write(readable(value) + "\n\n")
    if store.count("audit"):
        with atomic_text(root / "unresolved.md") as handle:
            handle.write("# Unassigned and unprocessed material\n\nCoverage concerns recorded facts, not exhaustive source extraction.\n\n")
            for i, item in enumerate(store.rows("audit"), 1):
                handle.write(f"## Item {i}\n\n" + readable(item) + "\n\n")
                if item.get("response_path"):
                    handle.write(f"[Preserved response]({quote(item['response_path'])})\n\n")
    record = load_json(run / "run.json")
    status = "partial" if any(j["status"] == "failed" for j in record["jobs"].values()) else "complete"
    with atomic_text(root / "README.md") as handle:
        handle.write(f"# Layer 2 results\n\nStatus: {status}\n\n{coverage['domain_count']} domains · "
                     f"{coverage['recorded_facts']} recorded facts · {unowned} unassigned\n\n"
                     "[Domain plan](domain_plan.md) · [Operational log](run.log)\n\n")
        for domain in store.rows("domains"):
            handle.write(f"- [{domain['definition'].get('name', domain['domain_id'])}]({names[domain['domain_id']]})\n")
        if store.count("audit"):
            handle.write("\n[Unassigned and unprocessed material](unresolved.md)\n")
        handle.write("\nSchema 6 is not yet integrated with Layers 3/4. Preserved evidence and recovery records are in `_internal/`.\n")
    write_arrays(root / "records.json", domains=store.rows("domains"), assignments=store.rows("decisions"), audit=store.rows("audit"))
    write_arrays(run / "_internal/domains.json", initial=store.rows("initial_domains"), final=store.rows("domains"),
                 dispositions=store.rows("dispositions"))
    write_arrays(run / "_internal/assignments.json", initial=store.rows("initial_owners"),
                 final=store.rows("decisions"), active_fact_ids=(f["fact_id"] for f in store.rows("facts")))
    write_json(run / "_internal/trace/publication.json", {"path": root.relative_to(run).as_posix()})
    materialize(run, root)
    return coverage

"""Six stage operations with explicit pages and finite domain comparisons."""

from itertools import chain, islice

from .jobs import iter_jobs, run_jobs
from .packing import definition_pages, fits, input_tokens, page_budget, record_pages, source_payloads
from .projections import apply_domains, audit, ingest_facts, observe_response, save_ledger
from .ownership import apply_owners, apply_corrections, commit_replacements, expect_replacements, owners, set_owners
from .evidence_text import evidence_pages
from .fs import load_json
from .windows import token_count
from ..ML.context import dump


def complete_definitions(store, stage, payload, *, collection="domains"):
    """Input current registry and payload; return all definitions only when the full request fits."""
    definitions = []
    count = input_tokens(store.run, stage, {**payload, "domain_definitions": []})
    target = load_json(store.run / "run.json")["context_policy"]["target_tokens"]
    for row in store.rows(collection):
        count += token_count(dump(dump(row))) + 32
        if count > target:
            return None
        definitions.append(row)
    return definitions if fits(store.run, stage, {**payload, "domain_definitions": definitions}) else None


async def plan_domains(store, stage, records, instructions, saver, logger):
    """Input subject/observation records; apply one finite source-ordered planning pass."""
    supplied_only = stage == "design"
    base = dict(instructions) if supplied_only else {**instructions, "evidence_files": ["/evidence/"]}
    key = "subject" if stage == "design" else "observations"
    budget = page_budget(store.run, stage, base)
    pages = iter(evidence_pages(records, budget) if supplied_only else record_pages(records, budget))
    first = next(pages, [])
    for index, page in enumerate(chain([first], pages), 1):
        version = ""
        if not supplied_only:
            store.add_records("domain_definitions", store.rows("domains"))
            version = store.snapshot()
        payload = {**base, key: page, "mode": "update", "group": index}
        definitions = complete_definitions(store, stage, payload)
        if definitions is not None:
            payload["domain_definitions"] = definitions
            responses = await run_jobs(store.run, stage, [payload], version, saver, logger, offset=index - 1)
            for response in responses:
                apply_domains(store, response)
            continue
        # Every definition page participates. These are planned ownership/scope
        # comparisons, never retries of completed model content.
        store.clear("comparisons")
        comparisons = ({**payload, "mode": "compare", "domain_definitions": domains,
                        "domain_page": i} for i, domains in enumerate(definition_pages(store, budget=budget), 1))
        async for response in iter_jobs(store.run, stage, comparisons, version, saver, logger,
                                        prefix=f"{stage}/compare-{index:06d}"):
            observe_response(store, response, {"comparisons": list})
            saved = response["value"]
            if supplied_only:
                saved = {"value": saved, "job": response["job"], "response_path": response["response_path"],
                         "domain_ids": [d["domain_id"] for d in response["payload"]["domain_definitions"]
                                        if "domain_id" in d]}
            store.put("comparisons", response["job"], saved)
        # The preserved proposal body is supplied on every reconciliation page;
        # only returned comparison records are paged, not silently shortlisted.
        reconciliations = (designer_reconciliations(store, payload, budget) if supplied_only else
                           ({**payload, "mode": "reconcile", "comparisons": matches}
                            for matches in record_pages(store.rows("comparisons"), budget)))
        for number, reconciliation in enumerate(reconciliations):
            if not supplied_only:
                store.add_records("domain_definitions", store.rows("domains"))
                version = store.snapshot()
            responses = await run_jobs(store.run, stage, [reconciliation], version, saver, logger,
                                       prefix=f"{stage}/reconcile-{index:06d}", offset=number)
            for response in responses:
                apply_domains(store, response)


def designer_reconciliations(store, payload, budget):
    """Input saved comparisons; yield bounded decisions with their current definitions, not pointers."""
    initial_count = store.count("domains")
    for comparison in store.rows("comparisons"):
        identifiers = dict.fromkeys(comparison["domain_ids"])
        rows = comparison["value"].get("comparisons", [])
        for row in rows if isinstance(rows, list) else []:
            claimed = row.get("domain_id") if isinstance(row, dict) else None
            if claimed is None:
                continue
            if isinstance(claimed, str) and store.get("domains", claimed) is not None:
                identifiers[claimed] = None
            else:
                audit(store, "unresolved_comparison_domain", value=row,
                      response_path=comparison["response_path"], job=comparison["job"])
        for matches in record_pages([comparison["value"]], budget):
            current = {**payload, "mode": "reconcile", "comparisons": matches}
            complete = complete_definitions(store, "design", current)
            if complete is not None:
                yield {**current, "domain_definitions": complete, "definition_scope": "complete"}
                continue
            # Compare jobs already visited every definition page. Carry the corresponding
            # definitions here explicitly; do not add a second all-roster comparison pass.
            identifiers.update((d["domain_id"], None) for d in islice(store.rows("domains"), initial_count, None))
            definitions = (store.get("domains", identity) for identity in identifiers)
            pages = iter(record_pages(definitions, budget))
            first = next(pages, [])
            for number, page in enumerate(chain([first], pages), 1):
                yield {**current, "domain_definitions": page, "definition_scope": "page",
                       "domain_page": number}


def ownership_payloads(store, stage, records, instructions=None, *, collection="domains"):
    """Input fact stream; schedule every required fact-page/definition-page combination."""
    base = {**(instructions or {}), "mode": "ownership"}
    if stage != "distribution":
        base["evidence_files"] = ["/evidence/"]
    budget = page_budget(store.run, stage, base)
    for page_index, facts in enumerate(evidence_pages(records, budget), 1):
        payload = {**base, "facts": facts, "fact_page": page_index}
        definitions = complete_definitions(store, stage, payload, collection=collection)
        pages = [definitions] if definitions is not None else definition_pages(store, collection, budget=budget)
        for domain_index, domains in enumerate(pages, 1):
            job = {**payload, "domain_definitions": domains, "domain_page": domain_index,
                   "definition_scope": "complete" if definitions is not None else "page",
                   "final_domain_ids": list(dict.fromkeys(d["domain_id"] for d in domains if "domain_id" in d))}
            if stage == "assignments":
                expect_replacements(store, job)
            yield job


def fact_inputs(store):
    """Input index; stream immutable bodies and current/initial IDs without source bookkeeping."""
    for fact in store.rows("facts"):
        yield {"fact_id": fact["fact_id"], "body": fact["body"],
               "initial_assignment": owners(store, fact["fact_id"], initial=True),
               "current_assignment": owners(store, fact["fact_id"])}


def planning_inputs(store):
    """Input ordered navigation/reference records; resolve each evidence body only when its page needs it."""
    for row in store.rows("planning"):
        yield store.get("facts", row["fact_id"]) if "fact_id" in row else row


async def understand(store, saver, logger):
    """Input run storage; read each original source window without industry or user instructions."""
    payloads = indexed_source(store)
    async for response in iter_jobs(store.run, "understanding", payloads, "", saver, logger):
        observe_response(store, response, {"profile": str, "evidence": list})
        identity, value = response["fingerprint"], response["value"]
        store.put("subject", identity, {"profile": value.get("profile", value), "source": response["payload"]["source"]})
        navigation = {k: v for k, v in value.items() if k != "evidence" or not isinstance(v, list)}
        if navigation or not value:
            store.put("planning", identity, {"evidence_id": identity, "body": navigation})
        ingest_facts(store, response)
    save_ledger(store)
    store.add_records("facts", store.rows("facts"))


def indexed_source(store):
    """Input run; register every source window before dispatch, including operationally failed jobs."""
    iterator = iter(source_payloads(store.run))
    payload, index = next(iterator, None), 1
    while payload is not None:
        following = next(iterator, None)
        store.add_text(f"source/{index:06d}", payload["overlap_context"] + payload["new_content"],
                       previous=f"source/{index - 1:06d}" if index > 1 else None,
                       following=f"source/{index + 1:06d}" if following is not None else None)
        yield payload
        payload, index = following, index + 1


async def distribute(store, saver, logger):
    """Input preserved facts/settled registry; assign IDs once without another original-source read."""
    payloads = ownership_payloads(store, "distribution", fact_inputs(store))
    async for response in iter_jobs(store.run, "distribution", payloads, "", saver, logger):
        apply_owners(store, response, initial=True)
    for fact in store.rows("facts"):
        set_owners(store, fact["fact_id"], owners(store, fact["fact_id"], initial=True))


async def review(store, instructions, saver, logger):
    """Input all facts; schedule observation pages including initial owners and Extra."""
    store.add_records("domain_definitions", store.rows("domains"))
    version = store.snapshot()
    payloads = ownership_payloads(store, "observations", fact_inputs(store), instructions)
    async for response in iter_jobs(store.run, "observations", payloads, version, saver, logger):
        observe_response(store, response, {"observations": list, "corrections": list, "issues": list})
        apply_corrections(store, response)
        issues = response["value"].get("issues", [])
        if isinstance(issues, list):
            for issue in issues:
                audit(store, "review_issue", value=issue, response_path=response["response_path"])
        rows = response["value"].get("observations", [])
        if isinstance(rows, list):
            for index, body in enumerate(rows, 1):
                identity = f"p-{response['fingerprint'][:20]}-{index:06d}"
                store.put("observations", identity, {"proposal_id": identity, "body": body,
                                                    "response_path": response["response_path"]})
    store.add_records("observations", store.rows("observations"))


async def assign(store, saver, logger):
    """Input accepted changed scopes; reconsider all evidence once, preserving untouched ownership."""
    store.clear("changed_domains")
    for domain in store.rows("domains"):
        previous = store.get("initial_domains", domain["domain_id"])
        if previous is None or previous["definition"].get("responsibilities") != domain["definition"].get("responsibilities"):
            store.put("changed_domains", domain["domain_id"], domain)
    if store.count("changed_domains"):
        store.add_records("domain_definitions", store.rows("domains"))
        version = store.snapshot()
        payloads = ownership_payloads(store, "assignments", fact_inputs(store), collection="changed_domains")
        async for response in iter_jobs(store.run, "assignments", payloads, version, saver, logger):
            apply_owners(store, response)
        commit_replacements(store)
    for proposal in store.rows("observations"):
        if store.get("dispositions", proposal["proposal_id"]) is None:
            audit(store, "unresolved_proposal", proposal=proposal, response_path=proposal["response_path"])

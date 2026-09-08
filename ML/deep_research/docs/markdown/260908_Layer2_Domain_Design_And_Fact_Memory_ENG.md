# Layer 2 Domain Design and Fact Memory

Status: **proposed design**, not implemented · Layer 2 only · Consolidated 08 September 2026 from the Layer 2 dynamic-domains research report of 07 September 2026 and the Layer 2 routing ticket write-up.

Decide the initial domains, route the facts, then review the subject in manageable batches. Every extra fact must find an existing or new domain. The reviewer never needs all domain contents in one call.

| Figure | Meaning |
| --- | --- |
| 200K | Normal maximum input target per model request, including all messages, instructions and tools. |
| 250K | Absolute dispatch ceiling. The extra 50K is tolerance, not routine capacity. |
| 0 | Extra facts in the intended final deliverable. All assigned; original audit records retained. |

---

## 1 · A small working desk, with the full archive beside it

Keep original facts and model responses in durable run files. Put only the current work, the applicable domain definitions and exact references on the model's desk. When more context is needed, fetch the referenced passage. After a batch, save the decisions and begin the next batch with fresh context.

**Chosen approach:** exact external storage + mandatory paged review + pointer-based reads + isolated review sessions + a shared input-size check. Summaries may help navigation, but never replace the source facts and never become the only memory.

**What "no loss" can mean.** Storage can preserve the exact source and every saved response. A coverage ledger can show which pages were processed and which recorded facts have owners. Neither proves that a language model extracted or understood every fact correctly. This design improves coverage and makes omissions visible; it does not promise perfect semantic recall.

---

## 2 · The workflow, stage by stage

Part A decides the domains. Part B distributes the facts and reviews them against the subject. A numbered stage can contain several small model calls.

```text
Research requirements + baseline domains
↓
1 · DOMAIN DESIGNER — create the initial domain plan
     keep the baseline; add responsibilities or domains with reasons
↓  (initial plan + original factsheet windows)
2 · FACT DISTRIBUTOR — route each source window
     60K source tokens, 10K overlap after the first window
     save fact records and source references
↓  two temporary destinations
     • domain fact files — facts assigned to the initial domains
     • Extra facts queue — facts with no suitable owner yet
↓  (review the saved facts in pages)
3 · DOMAIN PAGES — review every domain, page by page
     propose better ownership, expanded responsibilities or new subjects
↓
4 · EXTRA PAGES — find an owner for each Extra fact
     existing domain → expanded domain → specific new domain
↓  (saved proposals + exact supporting references)
5 · SETTLE THE PLAN — freeze the final domain catalogue
     reconcile proposals in batches; do not load every domain's facts
↓  (final catalogue + all recorded facts, paged)
6 · FINAL PLACEMENT — assign fact IDs to final domains
     review the whole recorded inventory, not just Extra
     change ownership; keep fact bodies unchanged
↓  (model-authored assignments)
7 · PUBLISHER — no model call
     application code groups the unchanged facts and follows the assignments
↓
Baseline domains + any added domains
     readable facts, provenance, final responsibilities and change reasons
     no Extra bucket in the successful final deliverable
```

Unresolved assignments or failed work remain visible; they are never deleted to make the queue appear empty.

### Stage detail

1. **Design a provisional domain plan.** Input: the research requirement and the baseline definitions. Keep the baseline responsibilities, propose additions and new domains, and explain each change. The designer does not pretend to know the whole subject yet. Output: initial domain plan and reasons.

2. **Read the original factsheet in source windows.** Use the planned domains to distribute supplied facts. Keep 60K source-token windows and 10K original-text overlap as the starting policy; the full-request budget still applies. Facts with no owner enter a temporary Extra-facts queue. Output: immutable fact records, source pointers and initial assignments.

3. **Review every domain, one page at a time.** The Domain Reviewer reads each domain's exact fact pages, its mandate and the compact domain catalogue. It returns suggested responsibility changes, misplaced-fact IDs, cross-domain references and proposed new subjects. Every scheduled page is processed; search is not a substitute for this sweep. Output: separate review decisions for each page.

4. **Resolve every Extra fact.** Read the Extra-facts queue in exact-text pages. Assign each fact to an existing domain, extend a domain, or propose a specific new domain. Unknown applicability is retained as uncertainty inside its subject domain; it is not a reason to leave the fact unassigned. Output: proposed owners and any new domain definitions.

5. **Settle the final domain plan.** The same reviewer role reconciles proposed definitions and boundaries in small batches, reading the existing catalogue plus each proposal and its supporting references. It relates duplicate proposals and preserves the original baseline responsibilities. No all-domain fact dump is sent. Output: final catalogue, change reasons and exact decision references.

6. **Confirm placement against the final plan.** Review the complete recorded-fact inventory in bounded batches against the frozen final catalogue. This lets a new domain receive facts that were initially inside another domain, not only facts from Extra. Return assignments by fact ID; do not rewrite the fact bodies. Output: final assignments; original fact text unchanged.

7. **Publish the domain files.** Application code groups unchanged fact records according to model-authored assignments. Final files contain the actual facts and their provenance, not just pointers. Publish available domain material even after sibling failures; show operational failures and unresolved assignment IDs separately. Output: domain facts, final plan and change record; no Extra domain in a successful result.

These are stages of one Layer 2 workflow. "Domain Reviewer" is one role used across multiple invocations, not a second reviewer supervising another reviewer. Initial distribution remains one call per source window, routing to all planned domains.

---

## 3 · What the reviewer actually sees

The reviewer does not review all domain contents in one call.

**Inside a single review session**

- Relevant requirements and fixed review rules.
- The current domain mandate and a compact catalogue of domain responsibilities.
- One page of exact facts and their source pointers.
- Relevant prior decisions, preserved exactly.
- Read access to the original passages and other referenced facts.

**Outside this session**

- All other fact bodies remain in durable files.
- Earlier conversations stay in the audit and checkpoint store.
- The page manifest holds the remaining work.
- Other domain reviewers do not share a growing message history.
- Every fact page is scheduled explicitly; similarity search cannot silently skip a page.

```text
Technical domain / page 1 → save decisions → fresh session
Technical domain / page 2 → save decisions → fresh session
Lease domain / page 1     → save decisions → fresh session
…every domain page…
Extra facts / page 1      → save proposed owners
Extra facts / page 2      → save proposed owners
Proposal reconciliation   → freeze final domain plan
Final placement pages     → assign facts under the final plan
```

Prior review decisions are not a substitute for source evidence. When a decision requires comparison across pages, the next session loads the relevant exact records using pointers. A catalogue or decision collection that outgrows the budget is itself paged; no hidden truncation or summary-only merge is allowed.

**Illustration.** At a 60K fact-page size, a 430K-token domain file takes eight review pages. Each call adds instructions, catalogue data and necessary reads. The other domains are not loaded alongside it. The number of calls follows actual input sizes; eight is an example, not a configured domain limit.

---

## 4 · Memory methods considered

| Method | What it does | Decision |
| --- | --- | --- |
| One large context | Loads many documents together; avoids retrieval but consumes context and can impair use of distant information. | Do not use as the review architecture. Long-context research found position-dependent failures; that is not a benchmark of the model in use. |
| Rolling summaries | Replace older material with compressed text. Some detail can be omitted. | Not the authoritative memory. Optional navigation notes must link to exact records. Automatic summarization stays disabled for this fact-preservation workflow. |
| External files + pointers | Store the full material outside messages and load a referenced piece when needed. | **Primary memory.** Preserve original files, fact records and review decisions. Pointer retrieval is not proof of exhaustive reading. |
| Mandatory paged processing | Visits every page in a manifest rather than relying on what search retrieves. | **Primary coverage method.** Combine with pointers for cross-page comparisons. A design recommendation, not a library guarantee of semantic completeness. |
| Vector retrieval / RAG | Selects passages relevant to a query. | Useful for lookup, but a top-k result is not an exhaustive inventory. Omit an embedding database in version one; IDs and paged reads suffice. |
| Isolated agents / subagents | Keep individual work in separate message contexts. | Use isolated sessions for review pages. Save detailed decisions outside the parent context, not only a short final summary. |
| Checkpoints | Save thread state so an interrupted agent can resume. | Use for tool-using review sessions. They preserve execution state; they do not shrink prompts or make facts understood. |
| MemGPT / recursive-LM approaches | Move data between memory tiers, or examine long input in an external environment using recursive calls. | Adopt external storage and bounded inspection as ideas. Do not add another framework, interpreter or recursive call tree. Neither approach guarantees lossless understanding. |

### The three storage levels

1. **Source archive.** Original `factsheet.md`, requirement and baseline roster snapshots. Stable references include source identity, exact offsets and hash. The source is never replaced by extracted text.
2. **Working records.** Every model response, fact record, assignment, proposal and reviewer decision. Immutable records get application-issued IDs. Changed ownership creates a new mapping, not an edited fact.
3. **Active context.** Only the instructions, active work page and relevant exact references needed now. A saved pointer occupies little space; reading its content consumes input tokens again.

Preserve exact source offsets across window overlap; repeated windows can point to the same source ranges. Byte and character boundaries must be round-trip safe, including non-ASCII text. Mechanical page boundaries are not claims about where a semantic fact starts or ends.

---

## 5 · The input boundary

The limit applies to **every individual model request**: designer, distributor, domain reviewer, Extra reviewer, plan reconciliation, placement, and every follow-up after a tool result. It is not the total run usage, and cached input still occupies context.

| Counted input | Example allowance, not a quota |
| --- | --- |
| System instructions, requirements, domain catalogue, tool and response-format definitions | 20K |
| Current exact fact page | 60K |
| Supporting source passages and comparison facts | 60K |
| Relevant prior decisions, valid recent tool exchange and protocol overhead | 30K |
| Illustrative assembled request | 170K, leaving 30K below the normal target |

- **Measure before sending.** Count the assembled request after middleware, with model tokenization and all provider-visible fields. The OpenAI Responses input-token-count interface is documented and present in the installed SDK; use it to verify the serialized request on the intended model before claiming exact enforcement. It is a separate network operation, not a generation call; access, billing and behavior still need validation. No such call was made to produce this document.
- **At the normal target, stop adding material.** Reduce the current page, postpone additional reads, or replace already-saved historical payloads with references. Keep instructions and unresolved comparisons needed for the current task.
- **Use 200K–250K only** for a necessary bounded continuation or reference comparison that cannot reasonably fit the normal working page. The 50K is input tolerance, not reserved output tokens. Log why it was used.
- **Before any request above 250K,** save available state and repack or divide the work before dispatch. Never send the oversized request and hope summarization happens afterward. If an essential request cannot be safely bounded or counted, surface an operational error; other work may continue.
- **After tool reads, count again.** Bound the total of parallel tool returns, not each return independently. Tool results must provide continuation references for unread content. Never silently discard the remainder.

A text-token estimate alone is not an exact provider guarantee. Use conservative local packing and verify provider-facing counting. Do not count only the factsheet or rely on the model's advertised context window. Provider automatic truncation must remain disabled. There is no new output-token ceiling; generated responses are saved fully, then paged if used as future input.

Start a fresh review session for each work page. If a session needs context rollover, archive the exact messages and tool results first. Carry exact pending decisions and references, and preserve a valid tool-call/result sequence. This is input scheduling and storage, not grading a completed response or asking for a content repair.

---

## 6 · The Extra-facts requirement

The intended final deliverable has no Extra-facts bucket. Every recorded extra fact must be assigned to one or more real domains. The reviewer can extend responsibilities or create a specific domain where necessary. It must not rename the queue to "Other" and call the task done.

- **Existing owner.** A supplied equipment-service record initially has no assignment. The reviewer assigns it to the technical domain, extends the maintenance responsibility if needed, and cites the original fact ID. Unknown installation status stays unknown.
- **New owner.** Several supplied facts establish a distinct operational subject outside the planned mandates. The reviewer proposes a specifically named domain, explains its scope, and assigns those fact IDs after reconciliation.

These examples are illustrative, not facts about a real subject. Historical Extra records remain in the audit archive. They are not a published domain and are not deleted to create the appearance of completion. Where a run fails or leaves an assignment unresolved, preserve that item and report it plainly; do not invent an owner or conceal it.

### Two different checks, two different promises

| Observation | What it can establish | What it cannot establish |
| --- | --- | --- |
| Every source page has a processing record | All scheduled source ranges reached processing, with failures visible | That the model extracted every meaning inside them |
| Every saved fact ID has a final domain assignment | No recorded fact is left in the Extra queue | That the assignment is semantically correct, or that an unextracted fact never existed |
| Exact source and response hashes match | The saved bytes were preserved | That the model reasoned accurately about them |

Keep this observational. ID accounting may report missing or unresolvable references, but must not grade prose, trigger content retries, discard responses or block available domain publication. Unreadable serialization and unsafe file access remain operational errors. Repeated unattended "retry until Extra is empty" is not part of this design. If the model leaves facts unassigned, surface the remaining IDs for an explicit follow-up.

A source-review evaluation must separately check that extraction did not overlook facts. An empty Extra queue alone cannot prove that the entire factsheet was used. Preserve full source access alongside domain outputs for that reason.

---

## 7 · Tools, roles and orchestration

| Role | Model-visible tools | Memory and execution |
| --- | --- | --- |
| Initial Domain Designer | None for ordinary supplied requirements; a bounded reference read only if the requirement material itself needs paging. | One small call normally; page unusually large requirements under the same budget policy. Save plan and reasons. |
| Fact Distributor | None; the source window is supplied directly. | Fresh context per window; all planned domains plus temporary Extra. Native batch concurrency five. |
| Domain / Extra Reviewer | `read_reference(ref, cursor)` | Fresh, checkpointed session per fact page; exact reference reads for source and cross-page comparison. |
| Plan reconciliation | The same `read_reference` | Sequential proposal pages and current catalogue. One writer owns catalogue updates and records changes. |
| Final placement reviewer | The same `read_reference` | Frozen final catalogue plus exact fact page. Returns ownership decisions without rewriting facts. |
| Publisher | Not a model agent | Groups immutable fact records by returned assignments; saves readable domain files and audit links. |

`read_reference` is a proposed small, read-only adapter: resolve a run-owned reference, return exact text within the remaining request budget, and expose the next cursor. The application supplies the work manifest, so a separate search or listing tool is unnecessary initially. The adapter validates IDs, cursors and path scope, not the meaning of the text.

Native `read_file` supports bounded reads and Deep Agents has filesystem tool allowlists. However, line limits are not token limits, and arbitrary file reads can exceed the remaining request allowance. Use the smallest token-aware adapter for this requirement; do not expose unrestricted read, write or shell tools in parallel.

### Deep Agents implementation outline

- Keep the installed Deep Agents 0.7.7, LangChain 1.3.15 and LangGraph 1.2.11. Installed interfaces remain the implementation authority over documentation.
- Build reusable Deep Agent graphs for the roles above. Supply each domain's frozen responsibilities with its work page. Dynamic domains do not require model-authored scheduling code.
- Expose only the bounded reference tool to reviewers. Keep the established empty-filesystem replacement for these graphs; no general-purpose subagent or default task tool.
- Use `StateBackend()` for small session state and a SQLite checkpointer for reviewer tool loops. Store the complete source and fact archive in application-owned run files; do not copy the entire corpus into every checkpoint.
- Application storage provides shared, read-only reference access across review threads. A thread-local `StateBackend` alone does not make files available to unrelated threads. No cross-subject `StoreBackend` or vector store is required.
- Use native `abatch_as_completed` for independent distribution work, maximum concurrency five. Review catalogue changes sequentially; final-placement batches can use the same native concurrency after the catalogue freezes.
- Use provider-native permissive JSON-object results for plans and assignments. No custom semantic schema, content validator, Markdown grading or repair retry. Save all completed responses.
- Implement one shared pre-dispatch input-sizing policy and the bounded reader. These are justified by the explicit input ceiling; they must apply to every model turn, not just the initial invocation.
- Disable automatic summarization and tool-call repair. Keep provider transport retries separate. Checkpoint or session restart must not re-run successfully saved work.

If literal nested subagents are later chosen, register the frozen domain definitions as compiled specialists and apply the same budget and tool restrictions to every child. Their final replies also count toward the parent's input. Do not add a supervisor merely to replay a known work queue. Deep Agents' interpreter-based dynamic dispatch is beta and unnecessary here.

---

## 8 · Proposed run layout

```text
L2_<run>/
  inputs/        original factsheet, requirements, baseline definitions
  planning/      initial and final domain plans, change reasons
  facts/         exact saved model records, stable IDs, source references
  review/        per-domain and Extra review decisions; historical queue
  assignments/   initial and final ownership records
  domains/       final domain fact files, with readable facts and links
  checkpoints.sqlite3   review-session recovery
  run.json       work manifest, settings, hashes and operational progress
  run.log        one operational timeline
  usage.jsonl    model calls, token usage and attribution
```

This is a proposed logical layout, not a migration instruction. Reuse existing storage names and helpers where compatible during implementation. A new run schema needs an explicit implementation decision; this document does not change one.

---

## 9 · Call count and trade-offs

Bounded context usually means more, smaller calls. The 200K target is not a total token budget. Exact re-reads can increase total input and latency. Avoiding giant calls protects context size; it does not automatically make the run cheaper or the model more accurate.

```text
Approximate minimum invocations = P + C + R + G + A

P = initial planning calls (normally 1)
C = source distribution windows
R = all domain-review pages + all Extra-review pages
G = proposal reconciliation calls
A = final fact-placement pages
```

Add tool-follow-up turns and transport attempts separately. **Illustrative only:** if P=1, C=14, R=12, G=2 and A=12, the workflow starts at 41 model invocations. These counts are invented to show the arithmetic, not measurements of a real factsheet. Real counts depend on generated fact volume, domain count, cross-references and review behavior.

Keep distribution as one call per source window across all planned domains. Sending every window to every domain worker would multiply source reads. The explicit review and final-placement passes provide narrower domain attention without paying that multiplication at initial extraction.

---

## 10 · Implementation and evaluation plan

Build the memory boundary before claiming complete coverage.

1. **Preserve and identify.** Immutable inputs, raw responses, stable IDs, exact source-range references and a complete page manifest. Test round-trip reconstruction, overlap, Unicode and file hashes.
2. **Bound access.** Implement the shared request-size guard and paged reference reader. Test 200K handling, the 250K boundary, oversized single records, multiple tool returns, huge catalogues and valid tool-message pairs. No silent provider truncation.
3. **Run the stages.** Provisional designer, distributor, domain and Extra review, catalogue reconciliation and final placement. Keep responsibilities additive and all raw outputs accessible.
4. **Publish and expose accounting.** Domain facts, plan revisions, assignment reasons and any unresolved IDs. Preserve sibling outputs after failures. Test that no successful zero-Extra example publishes an Extra domain, and that failure never hides unassigned records.
5. **Verify recovery.** Restart an interrupted review session, reuse completed work, keep catalogue versions consistent and prevent concurrent publication from overwriting another task's records.
6. **Evaluate with authorized model calls.** Compare source-fact retention, correct applicability, routing quality, unresolved Extra facts, unnecessary domains, cross-page contradictions, peak input, total tokens, calls and runtime. Include important facts at page boundaries and in the middle of long text.

Acceptance has two dimensions. Offline tests can verify storage integrity, scheduling, reference accounting and the token-boundary implementation. Human source-based review must assess extraction and routing quality. Do not turn those quality observations into an automatic output rejection or repair loop.

---

## 11 · Primary sources

Official documentation and research papers checked on 07 September 2026. The design above is a recommendation derived from these sources and the stated constraints, not a claim that a framework guarantees perfect recall. Current documentation can differ from Deep Agents 0.7.7; installed interfaces remain the implementation authority.

- *Lost in the Middle: How Language Models Use Long Contexts* — information position can affect performance in the models and tasks studied. Motivates bounded review; does not establish a quality threshold for the model in use.
- Deep Agents: Backends — `StateBackend`, durable storage, and shared versus thread-local artifact behavior.
- *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks* — retrieval-based external knowledge. Conclusion drawn here: selective retrieval alone is insufficient for exhaustive coverage.
- Deep Agents: Subagents — specialist configuration, isolated context and returned results.
- LangGraph: Persistence — thread state, checkpointing and recovery.
- *MemGPT: Towards LLMs as Operating Systems* — hierarchical memory and movement between active and external context.
- *Recursive Language Models* — long prompts kept in an external environment and examined in parts. This design does not adopt its interpreter or recursive orchestration.
- OpenAI: Count response input tokens — provider request counting. Runtime support on the selected model still needs validation.
- OpenAI: Create a response — input handling and the distinction between disabled and automatic truncation.
- Deep Agents: Tools and Permissions — bounded file access and capability restrictions. Custom tools need their own reference and path checks.
- Deep Agents: Dynamic subagents — interpreter-based dispatch is a distinct beta feature.
- Deep Agents: Context engineering — input context, offloading, summarization and isolation are separate mechanisms.

No research-model, embedding, token-count API or paid generation calls were made to produce this document. The proposed reviewer, memory tools, schemas and input limits still require implementation and verification.

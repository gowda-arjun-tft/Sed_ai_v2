# Layer 2 schema 7 — completed-run audit

Run: `L2_20260909_171314_855f`  
Comparison: `L2_20260909_123721_13fb` (completed schema 6)  
Audit date: 9 September 2026  
Scope: existing source, saved responses, evidence ledger, ownership, domain Markdown, logs and checkpoints. No model invocation, research call, repair or run recovery.

## Verdict

**The new workflow works operationally and produces useful research context. I would use this output as a research starting point, but not as a complete substitute for the factsheet.**

All 134 recorded evidence entries reach planning, assignment and review. Their fact text survives publication in every assigned domain. The new run is materially faster and cheaper in token consumption than the previous completed run on identical source, plugin and requirements.

The main remaining weakness is **what Read facts chooses to retain and how it groups qualifications**. I found one explicit rent-protection clause absent and one specific responsibility exception reduced to broader context. Assignment completeness cannot repair either automatically. Some differences are also labelled contradictions when the statements can coexist.

### Ratings

These are reviewer judgments, not measured accuracy percentages or statistically calibrated scores.

| Dimension | Rating | Interpretation |
|---|---:|---|
| Operational execution | 9/10 | All jobs completed; no logged database failure; bounded inputs |
| Preservation after extraction | 10/10 for checked invariants | All recorded fact bodies preserved; all final memberships agree with ownership |
| Research-driving usefulness | 8/10 | Strong asset, income, condition and dependency context; targeted omissions remain |
| Factual scope and uncertainty handling | 7.5/10 | Useful qualifications, but some grouped evidence loses scope or overstates contradiction |
| Compactness and navigation | 7/10 | Cleaner Markdown, but large technical paragraphs and repeated domain copies |
| Overall research readiness | **8/10** | Usable with source access and the caveats below; not extraction-completeness certification |

## 1. Measured execution

| Metric | Result |
|---|---:|
| Status | Complete |
| Runtime | 16m 35s |
| Source size | 490,449 bytes; 159,316 tokens |
| Original-source windows | 3: 60,000 / 60,000 / 59,316 tokens |
| Source-window input including overlap | 179,316 tokens |
| Jobs | 12; all completed, all attempt 1 |
| Model calls | 28 |
| Input tokens | 1,062,467 |
| Cached input tokens | 573,490 — included in input, not additional |
| Output tokens | 154,632 |
| Reasoning output tokens | 60,538 — reported subset of output |
| Total tokens | 1,217,099 |
| Largest logged assembled-input estimate | 125,412 tokens |
| Largest provider-reported input | 73,744 tokens |
| Logged warnings / errors | 0 / 0 |
| Recorded evidence entries | 134: 43 + 56 + 35 across the windows |
| Unassigned recorded entries | 0 |
| Final domains | 8 |
| Final fact-to-domain memberships | 347; average 2.59 owners per entry |
| Review issues preserved in audit | 21 |

The local estimate includes conservative allowances and metadata; it is not expected to equal provider billing. Neither logged estimates nor reported inputs approach the 300K target. This run did not exercise the exceptional ceiling or demonstrate 10M-token reliability.

No application job retry occurred. These records do not establish whether an unreported provider-internal transport retry occurred. Absence of a SQLite failure here does not prove that every locking condition is fixed.

### Where the time and calls went

| Stage | Jobs | Model calls | Input tokens | Output tokens |
|---|---:|---:|---:|---:|
| Read facts | 3 | 3 | 183,713 | 60,013 |
| Choose domains | 2 | 2 | 57,320 | 17,804 |
| Assign facts | 2 | 2 | 57,510 | 18,046 |
| Review assignments | 2 | 18 | 688,488 | 37,163 |
| Finalize domain changes | 1 | 1 | 15,034 | 6,148 |
| Update affected assignments | 2 | 2 | 60,402 | 15,458 |

Review accounts for approximately 65% of model-input tokens and 6m 26s of sequential job execution. Checkpoint message writes contain **122 distinct tool calls: 50 `ls`, 1 `grep`, 71 `read_file`**, all in the two observation jobs. There are no recorded web or shell tool calls. Several tools can run in one model turn: 122 tools do not mean 122 model calls.

The additional 16 model turns are associated with reviewer tool use, not evidence of a Python answer-repair loop. Retrieval is the remaining operational cost centre; it is not a failure by itself.

## 2. Preservation and ownership checks

Full-population checks over the saved records found:

- All nine frozen input/prompt hashes and the source-manifest hash match.
- The three understanding evidence lists equal the 134 ledger bodies exactly, in source order.
- Checkpoint human-message records for the two designer jobs collectively contain all 134 fact IDs and every entry's exact fact text. No short-profile-only substitution is indicated.
- Scheduled assignment, review and affected-assignment scopes each cover all 134 active IDs.
- All active IDs have at least one final owner; every domain's `fact_ids` agrees with the authoritative ownership map.
- Every assigned entry's exact fact text appears in its domain Markdown. No missing fact-text projection was found.
- No invalid application fact references were found in saved response objects.
- Review returned 60 correction rows and seven domain proposals. Seven dispositions were accepted, six domain definitions changed and no additional domain was created.
- Final ownership differs from initial ownership for 56 entries. A changed count is not a quality score; the actual operations matter.
- All 21 unresolved audit items are `review_issue` records, not 21 failed jobs or 21 unassigned facts.

The output does not show separate top-level `means`, `applicability`, source bookkeeping or application fact-ID labels in normal domain facts. Necessary historical/proposed qualifications remain in prose, as intended.

## 3. Important findings

Severity is relative importance to research readiness: 0 = negligible, 100 = critical. Scores are judgment, not failure probability.

### A. Missing area/parking rent-protection clause — 65/100

The source explicitly states that different measured areas or parking counts give neither party claims against the other and do not change rent: source line 948, IDs `7da5e5c7`, `8655f6ad`, `554a087f`.

The evidence preserves conflicting areas/parking counts and the tenant's general acceptance of condition and size, but I did not find the specific **no rent adjustment for measurement discrepancies** rule in the ledger or domain output.

Why it matters: a researcher could investigate area discrepancies as an income issue without this supplied contractual qualification. This is an extraction omission, not a lost ownership assignment.

### B. Specific fire-plan responsibility exception not explicit — 50/100

Source line 977, ID `e44cf011`, assigns changes to escape/fire-service plans to the landlord when future official requirements are unrelated to tenant measures or use.

The output explicitly retains tenant fire-plan obligations, and evidence entry 109 retains the broader landlord responsibility for later official orders. However, the particular fire-plan exception is not stated alongside the tenant obligation in entry 126.

This is **partial contextual retention**, not complete absence of all landlord-authority responsibility. Making the exception explicit would prevent a one-sided research brief.

### C. Some “contradictions” are compatible statements or different scopes — 45/100

- Entry 133 calls an asserted rent adjustment and later payment under reservation pending an addendum a contradiction. Both can be true; the unresolved issue is legal/payment status, not necessarily conflicting facts.
- Entry 26 puts different building-area/cost variants under contradictions while removing much of their individual scope association. Different building sections or alternatives are not inherently contradictory.
- Entry 110 gathers index discrepancies and examples from different adjustment periods. It retains dates, but the contradiction wording can encourage comparisons across unlike calculation bases.

The output generally warns against premature reconciliation, which is good. The improvement is narrower: retain each figure's date/scope and distinguish an actual disagreement from an unresolved relationship.

### D. Research context remains bulky — 30/100

The eight domain files total about **99,860 tokens**, including responsibilities and legitimate multi-domain repetition. Individual domains range from 2,339 to 24,137 tokens.

Examples of lower-value detail include emergency-plan symbol explanations, routine emergency instructions, detailed historic representation mechanics and long tender unit-price inventories. Entry 126 combines routine emergency instructions with an important contractual responsibility, so assigning the latter also copies the former.

This is not justification for silently deleting facts in Python. Under the current “keep every assigned entry” contract, better subject/topic grouping during Read facts is the safer place to reduce irrelevant co-travelling detail. There is no exact whole-entry duplicate, but related content recurs across windows and domains.

### E. Three malformed source identifiers — 20/100

Evidence entries 31, 78 and 92 include `8659707`, `13d` and `4b0fb1f` respectively. These do not match the supplied eight-character provenance-ID set.

Application fact IDs and assignments remain valid. This affects internal traceability, not execution or the readability of source-free domain Markdown. No correction was invented during this audit.

## 4. What is retained well

Targeted source/output checks confirm useful research anchors:

- Property identity, address/postcode variants, parcel uncertainty, area and parking discrepancies.
- Groundwater, foundations, historical structural qualifications and water-ingress/drainage disputes.
- Fire-door condition, incomplete maintenance, fire-alarm obsolescence and responsibility questions.
- Lease/rent history, current monthly amount of EUR 78,255.17, adjustment dates and payment reservation.
- Energy consumption/certificate boundaries, gas dependence and proposed envelope works.
- Insurance values, indemnity period, exclusions and differences between coverage records.
- Indicative refurbishment and garage tenders, including proposed/alternative versus completed status.
- Public-law, use-right, access, easement and ownership dependencies.

The previously identified omission of the entire “Building and technical systems” section is not repeated: its 153 supplied provenance anchors are represented in understanding evidence, and those evidence bodies survive final publication. Anchor presence alone is not proof that every nuance is retained.

Missing names of historical representatives, duplicate document labels, repeated room-table lines or old per-unit rent rows are not automatically important research losses. Conversely, a short contractual exception can matter more than a large quantity of retained tender detail.

The lack of new population, employment or market-search findings is not a Layer 2 defect. This layer prepares context; it does not conduct web research. The frozen requirements also limit some market-analysis scope.

## 5. Domain-level research readiness

Ratings concern the inspected context and responsibilities, not downstream research results. Evidence counts describe grouped entries, not atomic facts.

| Domain | Entries | Markdown tokens | Rating | Main observation |
|---|---:|---:|---:|---|
| Asset integrity and operations | 86 | 24,137 | 8/10 | Strong technical coverage; tender detail and mixed-purpose entries add bulk |
| Occupier, lease and income | 60 | 17,430 | 7.5/10 | Rich rent/occupancy context; missing measurement clause and scope issues matter |
| Rights and public law | 60 | 15,778 | 8/10 | Useful legal/authority anchors; clarify contractual exceptions |
| Ground, climate and insurability | 38 | 9,994 | 8/10 | Groundwater and insurance context retained; some broadly assigned operational material |
| Energy, carbon and transition | 8 | 2,339 | 8.5/10 | Compact, useful baseline; eight grouped entries do not mean weak coverage |
| Location, demand and exit | 22 | 7,125 | 8/10 | Relevant use/access/occupancy anchors; external evidence belongs downstream |
| Finance, debt and macro | 48 | 14,797 | 7.5/10 | Income/cost/legal-financing anchors present; extensive tender details reduce focus |
| External dependencies | 25 | 8,260 | 8/10 | Supplier, maintenance and material dependencies support further research |

Each file now has two second-level headings: responsibilities and supplied facts. This avoids hundreds of tiny headings, but topic navigation within the largest files remains limited. German and English evidence coexist; that is a presentation inconsistency, not proof of factual error.

## 6. Comparison with the previous completed run

The factsheet, plugin and requirements hashes match; both runs use `gpt-5.6-luna` at high reasoning. Prompts and pipeline/schema changed, so this is not a controlled measurement of cleanup alone.

| Metric | Previous schema 6 | New schema 7 | Change |
|---|---:|---:|---:|
| Runtime | 24m 41s | 16m 35s | 32.8% lower |
| Jobs | 18 | 12 | 6 fewer |
| Model calls | 37 | 28 | 24.3% lower |
| Input tokens | 1,699,543 | 1,062,467 | 37.5% lower |
| Output tokens | 240,340 | 154,632 | 35.7% lower |
| Total tokens | 1,939,883 | 1,217,099 | 37.3% lower |
| Recorded entries | 264 | 134 | Different grouping/extraction path; not a fact-loss percentage |
| Unassigned entries | 0 | 0 | Both cover their own recorded evidence |

**The efficiency improvement is measured. Overall semantic superiority is not established by fewer entries or fewer tokens.** The new design demonstrably avoids losing already-extracted entries in a second extraction/publication path; it still depends on the first extraction's quality.

## 7. Recommended next actions — not implemented

1. Keep the extract-once, ID-based assignment architecture. Do not add another full-source extraction or answer-repair loop.
2. Tighten Read facts instructions around rules **and their exceptions**, preserving the subject, scope and date of grouped figures. Test with the concrete source examples above without hardcoding property facts into production prompts.
3. Distinguish contradiction, different scope and pending status in the prompt. Do not use Python to reinterpret them.
4. Investigate reviewer directory-navigation overhead before increasing model capacity or adding stages. The 122 tool calls provide a concrete trace to examine.
5. Reuse this run as a regression inventory: compare the same source anchors after any separately authorized prompt change. Do not count all unmatched source IDs as missing facts.

## Method and limitations

The complete saved source and records were machine-scanned. Structural checks cover all recorded entries and all eight domain publications. Semantic findings come from targeted source/output inspection, emphasizing lease qualifications, technical dependencies, conflicting figures and previously reported gaps. **This is not a line-by-line human-equivalent validation of all 159,316 source tokens or an exhaustive semantic recall measurement.**

The source contains 3,539 distinct eight-character IDs; 2,797 are referenced by evidence source fields (79.0%). The 742 unmatched IDs include repeated and administrative material as well as potentially useful details. This is a provenance diagnostic, not a 79% accuracy or recall score.

No execution or research artifacts were edited, and all pre-existing run files retain their original hashes. Opening the checkpoint database with SQLite `mode=ro` nevertheless created checkpoint WAL/SHM sidecar files; those were left in place rather than deleting database files. No run was resumed. This is disclosed because read-only SQL access is not necessarily filesystem-side-effect-free.

Audit support files are under `outputs/layer2-audit-171314/`: `audit_checks.py`, `summary.json`, `source_sections.json` and the original `run_hashes.json` baseline. The initial summary's planning-coverage placeholder was resolved through subsequent read-only checkpoint-write inspection: 134 distinct evidence IDs reached planning. Its initial `run_unchanged` result predates the disclosed sidecar creation.

Run directory: `runs/inputs-new-fact-sheet-9563041d/L2_20260909_171314_855f`. Evidence-entry numbers in this report are one-based positions in its immutable ledger, not new application IDs. Source line references refer to `_internal/inputs/fact_sheet.md`.

# Layer 2 schema-6 run audit — `L2_20260909_065353_b707`

Read-only monitoring and source-to-output accuracy audit of one complete Layer 2 schema-6 run.
Audited 2026-09-09. No file inside the run directory was created, modified or deleted; the run was
never started, resumed, retried or stopped by the auditor. All observation was performed with
read-only scripts held outside the run.

**Run path:** `runs/inputs-new-fact-sheet-9563041d/L2_20260909_065353_b707`

---

## Summary table

| Metric | Result |
|---|---|
| Overall run status | `partial` (20 of 21 jobs complete, 1 failed) |
| Source tokens | 159,316 (`o200k_base`, measured independently) |
| Source windows | 3 |
| Read-facts jobs completed | 3 of 3 |
| Sort-facts jobs completed | 3 of 3 |
| Recorded facts | 409 |
| Finally assigned facts | 409 |
| Unassigned facts | 0 |
| Confirmed missing facts | 31 source bullets (one entire section) |
| Suspected missing facts | 250 source bullets (96 of them high-confidence) |
| Distorted facts | 1 |
| Duplicate facts | 0 |
| Failed jobs | 1 (`design/000002`, `OperationalError`) |
| Model calls | 46 |
| Input tokens | 2,175,522 |
| Cached-input tokens | 1,363,772 |
| Output tokens | 281,166 |
| Total tokens | 2,456,688 |
| Runtime | 30 min 49 s (1,849 s) |
| Evidence database size | 4,235,264 B |
| Checkpoint database size | 5,939,200 B |
| Overall quality rating | **Acceptable with issues** |

---

## 1. Executive conclusion

The orchestration layer performed well. Every source window was registered before dispatch and
processed by both reading stages, the immutable ledger is byte-identical to the raw model output,
all 409 recorded facts received a final owner, no job was retried, no completed model object was
discarded, and the single operational failure stayed visible without blocking sibling publication.
Extraction quality improved substantially over the schema-5 predecessor on byte-identical input:
**409 facts against 157, and source-provenance retention of 77.3% against 69.9%.**

Three defects qualify the result.

1. **One entire source section — `## Building and technical systems`, 31 bullets carrying 153
   provenance identifiers — reaches no output artifact at all.** Read facts captured 130 of those
   153 identifiers, proving the material was legible; Sort facts returned none of them. Nothing in
   the pipeline detects this. The run self-reports `409 recorded facts · 0 unassigned` and
   `unresolved_facts: 0`, which is exactly the false assurance that counter-based coverage produces.
2. **`design/000002` failed with a storage-layer `OperationalError`**, so the subject/evidence group
   for window 3 never reached initial domain planning. The failure is recoverable by resume and its
   practical impact was partly absorbed downstream, but the run is `partial` because of it.
3. **Published Markdown has lost its grouping.** 812 headings carry 932 fact bullets — 1.15 bullets
   per heading. The research output is a wall of one-line sections, worse to read than schema 5
   despite holding 2.6x more material.

Numeric fidelity is strong: of 409 facts, 408 carry only figures traceable to the cited source, and
zero facts cite a provenance identifier that does not exist. No duplicate facts were produced across
the 10,000-token window overlaps, and no applicability misclassification was found.

**Evaluation boundary.** Operational checks verify orchestration and storage. Assignment checks
verify that every *recorded* fact was handled. Source-to-output comparison identifies clear omissions
and distortions. Without a separately prepared human gold-standard inventory, this audit does **not**
claim mathematically proven 100% semantic completeness.

---

## 2. Run configuration and source size

| Item | Value |
|---|---|
| Run ID | `L2_20260909_065353_b707` |
| Schema version | 6 |
| Model | `gpt-5.6-luna`, reasoning effort `high` |
| Deep Agents version | 0.7.7 |
| Started / finished | 2026-09-09T06:53:53Z / 07:24:42Z |
| Chunking | 60,000 size · 10,000 overlap · **50,000 stride** · `o200k_base` · concurrency 5 |
| Context policy | target 300,000 · maximum 350,000 · framing reserve 8,000 · summarization `false` |
| Provider max retries | 3 (transport level only) |

Frozen inputs, all hash-verified at execution start:

| Snapshot | Bytes | SHA-256 (first 16) |
|---|---|---|
| `fact_sheet.md` | 490,449 | `df7320bbca373be7` |
| `domain_plugin.md` | 9,563 | `8c6e06e6d6858e80` |
| `requirements.md` | 7,320 | `0af14326c3ae0afd` |
| six frozen prompts | 20,243 | per-file, all recorded |

The plugin hash is identical to the schema-5 run `L2_20260908_155442_b6d1`, so the domain baseline is
unchanged and the two runs are directly comparable.

**Source:** `inputs/new_fact_sheet.md`, a Bad Homburg / Gonzenheim courthouse factsheet.
490,449 bytes, 485,464 characters, 1,444 lines, no BOM, 20 sections, **159,316 tokens**.

The source is not prose. It is already an inventory of **1,382 atomic fact units** (1,350 bullets plus
32 table rows), and almost every unit carries parenthesised 8-hex provenance identifiers from the
upstream extraction — **3,548 occurrences, 3,539 distinct**. This audit exploits that structure to
trace individual facts through the pipeline rather than relying on counters.

---

## 3. Operational performance

| Measure | Value |
|---|---|
| Total runtime | 1,849 s (30 min 49 s) |
| Jobs | 21 — 20 complete, 1 failed, 0 pending, 0 running |
| Model calls | 46 |
| Attempts | **every job at `attempt=1`** — histogram `{1: 21}` |
| Response files stored | 20 (one per completed job), **0 empty objects** |
| Peak assembled input estimate | 127,189 tokens (42% of the 300,000 target) |
| Jobs over 300K target | 0 |
| Jobs over 350K ceiling | 0 |
| History archiving events | **0** |
| Provider timeouts / permission errors | none |
| Filesystem failures | one SQLite `OperationalError` (§14) |

**Native concurrency operated correctly.** `understanding` and `distribution` are the only
non-retrieval stages, and both dispatched all three windows in a single batch — the three
`understanding` jobs were scheduled inside the same second at 06:53:54 and ran simultaneously. The
four retrieval stages ran strictly sequentially, which is correct: `jobs.py:44` sets
`retrieval = stage not in {"understanding", "distribution"}` and forces concurrency 1 with sequential
`ainvoke` for those stages. Sequential progress there is designed behaviour, not a stall.

**Input accounting never came under pressure.** All 32 assembled-input checks logged `reason=normal`.
No job approached either threshold, so the lossless pointer-offload path in
`InputBudget.before_model` never executed and no `/history/` directory exists.

---

## 4. Stage-by-stage execution results

| Stage | Prompt | Jobs | Wall time | Longest job | Result |
|---|---|---|---|---|---|
| `understanding` | 01 Read facts | 3 ✓ | 164 s | 163.7 s | 154 evidence rows |
| `design` | 02 Choose domains | 1 ✓ / **1 failed** | 68 s | 49.9 s | 8 domains created |
| `distribution` | 03 Sort facts | 3 ✓ | 255 s | 254.8 s | 409 facts + inline owners |
| `observations` | 04 Review domains | 6 ✓ | 655 s | 160.6 s | 77 observations |
| `catalogue` | 05 Finalize domains | 1 ✓ | 125 s | 124.2 s | 77 dispositions, 6 domains revised |
| `assignments` | 06 Assign facts | 6 ✓ | 517 s | 108.8 s | 409 facts owned |

**Read facts** — one model call per window, no tool turns (correctly: no tools are exposed).
Windows returned 55 / 53 / 46 evidence rows, 154 total, against 141 in schema 5 (+9%).
Instruction isolation is genuinely enforced: `domain_plugin` and `requirements` were absent from the
evidence index during this stage and appear only at the stage boundary, so window reading could not
have been steered by the requirement document.

**Choose domains** — page 1 produced the 8 baseline domains. Page 2 failed (§14).

**Sort facts** — 101 / 73 / 235 facts, one call each, mode `extract_and_assign` throughout because the
8 domain definitions always fitted inline. Multi-domain assignment worked at extraction time:
158 facts with 1 domain, 214 with 2, 37 with 3.

**Review** — 6 pages, 30 calls. Tool use was highly uneven: pages 1 and 4 spent 8 and 12 calls
retrieving evidence, pages 2, 3 and 5 answered directly in 1 call each. This is the first
confirmation that the schema-6 retrieval surface works end to end — `ls`, `glob`, `grep`, `read_file`
against the frozen evidence index, with input growing monotonically 43,607 → 70,267 across turns.
Observations are substantive, e.g. conflicting cadastral identity for parcel 123/1, an easement whose
use-right terms are truncated mid-document, and ownership records that "agree on the owner name but
differ in evidential strength".

**Finalize domains** — all 77 proposals received an explicit disposition (46 `accepted`,
31 `already represented`), so no `unresolved_proposal` audit was raised. Six of eight domains had
responsibilities revised; d0005 and d0008 were returned untouched and carried forward unchanged by
`apply_domains`. **No domain was added or removed: 8 initial, 8 final.**

**Assign facts** — 6 pages, all 409 facts owned, zero unassigned.

---

## 5. Source-window processing coverage

The manifest matches an independent recomputation of `source_windows()` exactly.

| id | tokens | start_byte | end_byte | new_start_byte | verdict |
|---|---|---|---|---|---|
| s000001 | 60,000 | 0 | 174,958 | 0 | MATCH |
| s000002 | 60,000 | 140,365 | 329,456 | 174,958 | MATCH |
| s000003 | 59,316 | 299,878 | 490,449 | 329,456 | MATCH |

- **Policy preserved.** 60,000 size, 10,000 overlap, 50,000 stride. Windows 2 and 3 carry exactly
  10,000 overlap tokens.
- **No redundant tail.** Nominal starts are 0 / 50,000 / 100,000. The third window ends exactly at
  token 159,316 and the loop terminates, so no fourth window from start 150,000 is emitted.
- **Lossless partition, no dropped characters.** Concatenating the three `new_content` slices
  reproduces the source exactly — 485,464 of 485,464 characters. `new_start_byte` chains
  0 → 174,958 → 329,456 → 490,449 with no gap and no overlap. `input_bom_bytes` is 0 for all three.
  Unicode boundary handling is therefore verified byte-exact, including the source's own pre-existing
  mojibake (`fÅr Bodenforschung`, `FlÑchenaufstellung`), which passes through unchanged.
- **Every window reached both reading stages.** 3 of 3 `understanding` jobs and 3 of 3 `distribution`
  jobs completed. Registration precedes dispatch structurally: `indexed_source` writes each window
  into the evidence index (24 pages, 8 per window, with navigation links) *before* yielding it, so a
  window cannot be processed without being registered.
- **Both window seams fall mid-section** — cut 1 inside `## Property and site`, cut 2 inside
  `## Areas and plans` — which is where cross-boundary loss or duplication would appear. Neither
  occurred (§10).

---

## 6. Fact-retention funnel

Measured by tracing the source's own 3,539 distinct provenance identifiers through each artifact.

| Stage | Source IDs present | Share |
|---|---|---|
| Source (denominator) | 3,539 | 100.0% |
| → Read facts raw responses | 2,245 | 63.4% |
| → Sort facts raw responses | 2,734 | 77.3% |
| → immutable ledger `facts.jsonl` | 2,734 | 77.3% |
| → review (all 409 facts paged) | 2,734 | 77.3% |
| → final assignment (all 409 owned) | 2,734 | 77.3% |
| → **published `domains/*.md`** | **3** | **0.1%** |
| unresolved.md | 0 | 0.0% |

Object-level counts along the same path:

```
1,382 source bullets
  → 154 Read-facts evidence rows          (independent pass, not a feeder to Sort facts)
  → 409 Sort-facts rows returned
  → 409 ledger facts                       (0 lost, byte-identical multiset)
  → 409 facts paged into review            (77 observations on 137 facts)
  → 409 facts finally assigned             (0 unassigned, 867 owner rows)
  → 932 bullets published across 8 domains
```

Three retention facts matter.

- **Sort facts is authoritative, and Read facts material is discarded.** 369 identifiers reached
  Read facts but not Sort facts. The two stages read the same original windows independently; only
  Sort facts feeds the ledger. Read facts' extra 369 identifiers exist solely in its raw responses.
- **Python loses nothing.** Ledger bodies are an identical multiset to the raw Sort facts bodies —
  0 in raw but not ledger, 0 in ledger but not raw, and 409 distinct `fact_id` values with no
  collisions. Between the model's output and the immutable record there is zero attrition.
- **Provenance is stripped at publication by design.** `publication.py:71` excludes the `source` key
  from every rendered fact, dropping 2,731 of 2,734 identifiers. A human reading `domains/*.md`
  cannot trace any fact back to its source document. This is intentional ("no technical IDs, byte
  offsets, source bookkeeping") but it removes all auditability from the deliverable.

---

## 7. Confirmed missing facts

### 7.1 `## Building and technical systems` — entire section absent. Severity: **Critical**

| | |
|---|---|
| Source location | `inputs/new_fact_sheet.md` lines **1235–1268**, bytes 435,925–453,048 (17,124 B) |
| Source window | **s000003** `new_content` |
| Source units | **31 bullets**, carrying **153 distinct provenance IDs** |
| IDs in Read facts | **130 of 153** — the material was read and understood |
| IDs in Sort facts | **0** |
| IDs in `_internal/facts.jsonl` | **0** |
| IDs in `domains/*.md` | **0** |
| IDs in `unresolved.md` | **0** |
| Job | `distribution/000003` (completed successfully, returned 235 facts) |

Content probes confirm absence independently of the identifier method:

| Probe term | Occurrences in source | Occurrences in ledger |
|---|---|---|
| `Gewahrsam` | 3 | **0** |
| `Kühlraum` | 4 | **0** |
| `Sprinkler` | 3 | **0** |
| `Feststellanlage` | 12 | 1 |

Exact source excerpts now absent from every Layer 2 record:

```
- The undated 2006 Flächenaufstellung, GEB. A+B Gericht.pdf, the only document speaking to these
  rooms and a tier 5 estimate (indicative), records on the ground floor that room 9a includes a
  Wartehalle with an actual area of 73,45 …

- … records ground-floor room 10 as a Windfang with an actual area of 19,36 and VF classification …

- … records ground-floor room 11 as a Büro with an actual area of 22,65 and HNF 2 classification …
```

94 distinct room identifiers appear in this section; only 22 appear anywhere in the ledger, and those
come from the separate room schedules in `Condition and repair` and `Areas and plans`.

**Why this is Critical rather than High.** The pipeline reports complete success for this material.
`run.json` records `"recorded_facts": 409, "owned_facts": 409, "unresolved_facts": 0`; `README.md`
publishes "409 recorded facts · 0 unassigned"; `unresolved.md` contains no reference to it. No audit
kind exists for "source region produced no facts", because Python deliberately performs no semantic
inspection of model output. An entire section of technical-systems evidence is therefore lost
**silently and undetectably from within the system**. This is precisely the failure mode that
assignment-coverage metrics cannot see.

**Mitigating context, stated fairly.** The section is a highly repetitive room-by-room area schedule
explicitly marked "tier 5 estimate (indicative)" and "the only document speaking to these rooms".
Comparable room-schedule material was extracted from other sections. A plausible reading is that the
model judged it duplicative and low-tier. That is a defensible editorial judgement — but it was made
without record, and the same silent mechanism would drop a high-value section just as invisibly.

---

## 8. Suspected missing facts requiring human review

Bullet-level coverage, where a bullet counts as retained if at least one of its provenance IDs
appears in the ledger:

| Section | Bullets | In ledger | Coverage | Not in ledger |
|---|---|---|---|---|
| Condition and repair | 305 | 248 | 81% | 57 |
| Property and site | 323 | 208 | **64%** | 115 |
| Areas and plans | 224 | 174 | 78% | 50 |
| The lease | 158 | 143 | 91% | 15 |
| Costs and offers | 122 | 121 | 99% | 1 |
| Identity and title | 77 | 72 | 94% | 5 |
| **Building and technical systems** | 31 | **0** | **0%** | **31** |
| Fire safety | 19 | 15 | 79% | 4 |
| Service charges | 28 | 27 | 96% | 1 |
| Easements, charges and encumbrances | 21 | 21 | 100% | 0 |
| Energy performance | 10 | 10 | 100% | 0 |
| Tenancy and income | 7 | 6 | 86% | 1 |
| Insurance | 6 | 6 | 100% | 0 |
| Index | 4 | 4 | 100% | 0 |
| Environmental contamination | 5 | 5 | 100% | 0 |
| Documents and information management | 8 | 7 | 88% | 1 |
| Not covered | 2 | 0 | n/a | (no IDs) |
| Sources | 32 | 0 | n/a | (30 of 32 carry no IDs) |
| **Total** | **1,382** | **1,067** | **77.2%** | **315** |

Of the 315 bullets with no ledger identifier, 34 carry no provenance ID at all and are unmeasurable
by this method (32 `Sources` table rows, 2 `Not covered` lines). That leaves **281 measurable
candidate omissions**, of which 31 are confirmed above, giving **250 suspected**.

Narrowing the 250 by content probe — searching each bullet's rarest distinctive tokens in the ledger
text — yields:

- **96 bullets with no distinctive token found in the ledger** — high-confidence omissions.
- **62 bullets whose substance is echoed** despite the identifier being absent — likely retained
  under different wording, so genuinely only suspected.
- The remaining 123 had at least one identifier in Read facts but none in Sort facts — seen, then
  dropped at extraction.

Representative high-confidence candidates for human review:

| Source line | Section | Excerpt | IDs |
|---|---|---|---|
| 30 | Condition and repair | "The Windaufnahme is referred to Prüfbericht Nr. 2 vom 22.6.1988 and Prüfbericht Nr. 1 vom 18.5.1988." | `7b65f1f8`, `36065b2f` |
| 33 | Condition and repair | "The Baugrundangaben refer to Gutachten des Hessischen Landesamtes für Bodenforschung - Az 321-353/88 Bau/Ge vom 25.5.1988 …" | `40c4c2d8`, `39f00189` |
| 34 | Condition and repair | "The Baugrundangaben are based on the Gutachten … vom 25.4.1988 and refer to Prüfbericht Nr. 5 vom 23.7.1989" | `aa39da65`, `a7cab7e7` |
| 12 | Condition and repair | "A chemische Untersuchung des Grundwassers zur Betonaggressivität was carried out, and the attached Untersuchungsbefund is specifically referenced." | `f2badc83` |

`## Property and site` at **64%** is the weakest measurable section and holds 115 of the 315 gaps.
It is also the section containing window seam 1, and it is the largest section after
`Condition and repair`. It warrants targeted human review.

**Method limitation.** Identifier absence is evidence, not proof: the model may capture a bullet's
substance without copying its identifier string. Conversely, an identifier that is present proves the
bullet was seen. The content probe reduces false positives but cannot eliminate them, because the
source is largely German technical vocabulary while the ledger is English prose, so paraphrase can
legitimately drop every probe token.

---

## 9. Distorted or incorrectly qualified facts

Numeric fidelity was tested by canonicalising every figure so that German `249.067,51` and English
`249,067.51` compare equal, then checking each fact's figures against the source bullets its
provenance IDs resolve to, with tolerance extended to the whole containing section.

| Check | Result |
|---|---|
| Facts citing provenance IDs that resolve to real source bullets | **406** |
| Facts citing IDs that resolve to nothing | **0** |
| Facts citing no provenance ID at all | 3 |
| Facts with figures absent from the cited source | **1** |
| Entity/counterparty name distortion found | none |
| Lost qualifications or exclusions found | none |
| Applicability misclassification found | **none** |

**Zero invented provenance identifiers across 409 facts** is a strong signal against fabrication.

### 9.1 `f-4f1b9a8ca362024da0a2-000082` — derived total presented as a source figure. Severity: **Low**

Output, `_internal/facts.jsonl`:

> "…replacement of 23 light heads with LED at EUR 1,300 each, two new bollard lights at EUR 1,000
> each and nine wall lights at EUR 1,100 each, **total EUR 41,800** within an estimated EUR 54,300
> package."

Source, line 298 (window s000001):

```
- The indicative tier 5 kostenschaetzung includes Austausch Leuchtenkopf gegen LED for 23,00 Stck at
  1.300,00 € each, totalling 29.900,00 €; neue Pollerleuchten for 2,00 Stck at 1.000,00 € each,
  totalling 2.000,00 €; and Wandleuchte austauschen for 9,00 Stck at 1.100,00 € each,
  totalling 9.900,00 €. (67da4b05, b01d7a2c, ea012742)
```

29,900 + 2,000 + 9,900 = 41,800. The arithmetic is correct but the total is **not stated in the
source**; the model computed it and reported it as recorded. `54,300` and `12,500` are genuine source
figures, and applicability is correctly marked `Proposed/indicative`. Minor, but it crosses the
calculation boundary the project draws.

### 9.2 Applicability discipline — no errors found

| Term appearing in `applicability` | Facts |
|---|---|
| historic | 65 |
| proposed | 65 |
| indicative | 52 |
| unknown | 23 |
| specified | 16 |
| operating | 3 |
| installed | 3 |
| approved | 1 |

Twelve facts were flagged automatically for mixing "current/installed" with "proposed/indicative"
language. On inspection all twelve are **correct hedging, not errors** — e.g.
`"Historic indicative room schedule; current applicability unknown"`. None of the four error classes
specified for this audit occurred: no proposed item reported as installed, no approved alternative
reported as operating, no historic catalogue entry reported as current, and no unknown applicability
converted into certainty. Sampled facts explicitly resist that conversion, for example
`evidence[0]` of window 1: *"the 6047 m² figure is one document value, not an uncontested total"*,
followed by cross-references to the four conflicting area figures.

**Coverage limit.** 143 of 409 facts (35%) phrase applicability using one of the six controlled terms;
the remaining 65% use free prose, which is often richer but cannot be filtered or audited
mechanically — only read. The finding above rests on sampling plus full automated screening of the
controlled-vocabulary subset, not on exhaustive reading of all 409.

---

## 10. Duplicate or overlapping facts

| Check | Result |
|---|---|
| Exact duplicate fact bodies in the ledger | **0** |
| Near-duplicate pairs across window seams (8-token shingle Jaccard > 0.5) | **0** |
| Duplicate `fact_id` values | 0 |

The 10,000-token overlap produced **no duplication at all**, at either seam. This is the clearest
success in the run: the `03_sort_facts.md` instruction — "Use overlap_context only to understand
continuity. Do not reproduce overlap-only information." — is being followed exactly, across two
seams that both fall mid-section.

---

## 11. Domain-assignment quality

| Domain | Name | Facts |
|---|---|---|
| d0001 | Asset Integrity, Systems & Operational Resilience | 210 |
| d0002 | Occupier, Lease, Income & Counterparty Economics | 182 |
| d0003 | Rights, Public Law & Ownership Governance | 217 |
| d0004 | Ground, Physical Climate & Insurability | 59 |
| d0005 | Energy, Carbon & Transition | 29 |
| d0006 | Location, Demand, Market, Valuation & Exit | 38 |
| d0007 | Finance, Debt & Macro Transmission | 106 |
| d0008 | External Dependencies, Geopolitics, Trade & Supply Chains | 26 |

- **409 of 409 facts assigned; 0 unassigned; 867 owner rows.**
- **Multi-domain assignment is working**: 108 facts with 1 domain, 171 with 2, 105 with 3, 23 with 4,
  2 with 5. 301 of 409 facts (74%) carry more than one owner, so relevant cross-domain facts are not
  being forced into a single domain.
- No domain is empty and none holds a degenerate share.

### Reviewer influence converges without being executed

Review requests that name individual facts have **no executor**: final ownership is re-derived in
stage 06, which receives facts, initial owners and final definitions — not the observations.
Observations flow only into stage 05, reshaping domain definitions and recording dispositions.

Tested on the one explicit removal request, observation 11 of `observations/000002`:

| | |
|---|---|
| Reviewer asked | "Remove ownership from this domain; retain d0003 and d0004" |
| Initial owners | `d0003`, `d0004`, `d0007` |
| **Final owners** | **`d0003`, `d0004`** |

The removal happened. Because stage 06 could not have read the request, this is **independent
convergence**, not execution. That validates the "no approval loop" design, but it also means
reviewer per-fact judgements are not guaranteed to land, and no record distinguishes a request that
converged from one that was silently ignored.

### Published output legibility. Severity: **Medium**

| File | Bytes | `##` headings | Fact bullets |
|---|---|---|---|
| `rights-public-law-and-ownership-governance.md` | 118,366 | 203 | 226 |
| `asset-integrity-systems-and-operational-resilience.md` | 130,772 | 195 | 219 |
| `occupier-lease-income-and-counterparty-economics.md` | 95,303 | 166 | 192 |
| `finance-debt-and-macro-transmission.md` | 62,542 | 102 | 114 |
| `ground-physical-climate-and-insurability.md` | 39,874 | 59 | 67 |
| `location-demand-market-valuation-and-exit.md` | 21,226 | 34 | 47 |
| `energy-carbon-and-transition.md` | 20,467 | 27 | 35 |
| `external-dependencies-geopolitics-trade-and-supply-chains.md` | 17,620 | 26 | 32 |
| **Total** | **506,170** | **812** | **932** |

**1.15 bullets per heading.** The cause is upstream: `03_sort_facts.md` asks the model to "group
related facts with consistent, useful section labels", but it minted 381 distinct labels for 409
facts, **95% of them holding exactly one fact**. Window 3 is the extreme — 235 facts, 235 distinct
labels. Since `publish.py:26` groups by section (`GROUP BY section ORDER BY min(seq)`), the output
becomes one heading per fact.

This is a regression: schema 5 had 118 labels for 157 facts, 1.33 facts per label with 82%
singletons. Schema 6 holds 2.6x more information and reads worse.

On the positive side, no raw JSON leaked into the published Markdown — **0 `~~~~json` fences** across
all eight files, so the `readable()` renderer handled every value shape it met.

---

## 12. Unresolved and unconventional model output

`unresolved.md` contains exactly two items, and both are correct.

**Item 1 — `unprocessed_assignment_fields`.** An assignment row carried an extra `evidence_refs`
field beyond `fact_id`, `domain_ids` and `reason`. `apply_owners` preserved the complete value and
audited it rather than discarding it.
Response: `_internal/trace/responses/assignments/000001/45c5a577…/response.json`

**Item 2 — `operational_failure`.** `design/000002`, `error_type: OperationalError`. The failure is
published in the human-facing output rather than hidden.

| Preservation check | Result |
|---|---|
| Response files for completed jobs | 20 of 20 |
| Empty or unconventional objects discarded | **0** — none discarded, none rejected |
| Ledger entries removed or rewritten | 0 |
| Content-driven repair or semantic retry loops | **none** — all 21 jobs at `attempt=1` |
| Unusable IDs surfaced | 1 (§12.1, not audited by Python) |

### 12.1 One unusable fact ID accepted without audit. Severity: **Low**

`_internal/trace/responses/observations/000002/123bc353…/response.json`, observation 11:

```json
"fact_ids": ["f-f4f1b9a8ca362024da0a2-000090"],
"change": "Remove ownership from this domain; retain d0003 and d0004.",
"reason": "… recorded in f-4f1b9a8ca362024da0a2-000091."
```

The identifier has a **doubled `f`**: `f-f4f1b9a8…` where the ledger prefix is `f-4f1b9a8…`. The
intended target exists, and the same observation spells the sibling identifier correctly, so it is a
transcription slip rather than a hallucinated fact.

The defect is that **Python never checks it**. `review()` in `stages.py:132` stores each observation
verbatim with no validation of `fact_ids` against the ledger, and no audit kind covers an
unresolvable observation reference — unlike `apply_domains`, which validates `proposal_id`, and
`apply_owners`, which audits `unknown_domain`. The dangling reference reaches `domain_plan.md`
unmarked. 1 of 137 references (0.7%).

---

## 13. Runtime, model calls, tokens and storage

### Runtime by stage

| Stage | Wall time | Share | Jobs | Sum of job elapsed | Longest job |
|---|---|---|---|---|---|
| `understanding` | 164 s | 8.9% | 3 | 407.9 s | 163.7 s |
| `design` | 68 s | 3.7% | 2 | 67.6 s | 49.9 s |
| `distribution` | 255 s | 13.8% | 3 | 588.9 s | 254.8 s |
| `observations` | 655 s | **35.4%** | 6 | 652.1 s | 160.6 s |
| `catalogue` | 125 s | 6.8% | 1 | 124.2 s | 124.2 s |
| `assignments` | 517 s | 28.0% | 6 | 502.0 s | 108.8 s |
| **Total** | **1,849 s** | 100% | 21 | — | — |

Concurrency is visible in the arithmetic: for `understanding` and `distribution` the sum of job
elapsed times (407.9 s, 588.9 s) far exceeds wall time (164 s, 255 s), a 2.5x and 2.3x speed-up. For
the four retrieval stages the two figures are nearly equal, confirming sequential execution.

**Review and assignment together consume 63% of runtime** for 12 of 21 jobs. They are the scaling
bottleneck, both because they are sequential and because they page over all 409 facts.

### Slowest jobs

| Job | Elapsed | Likely cause |
|---|---|---|
| `distribution/000003` | 254.8 s | Largest output of the run — 235 facts, 37,618 output tokens |
| `distribution/000001` | 184.3 s | 101 facts, 26,628 output tokens |
| `understanding/000002` | 163.7 s | Densest window, 922 provenance IDs echoed |
| `observations/000001` | 160.6 s | 8 model calls with tool retrieval |
| `distribution/000002` | 149.8 s | 73 facts |

Every slow job is slow because it produced a lot of output or made many turns. No job was slow for
an unexplained reason, and no stall occurred.

### Tokens (measured, provider-reported)

| Measure | Value |
|---|---|
| Model calls | 46 |
| Input tokens | 2,175,522 |
| Cached-input tokens | 1,363,772 (62.7%) |
| Cache-creation input tokens | 811,612 |
| Uncached input (derived) | 811,750 |
| Output tokens | 281,166 |
| Reasoning output tokens | 100,318 (35.7% of output) |
| **Total tokens** | **2,456,688** |
| Input per call — average / max | 47,293 / 70,847 |
| Output per call — average / max | 6,112 / 37,618 |
| Tokens per recorded fact | 6,006 |

### Cost — **estimate, not measured**

Priced at published `gpt-5.6-luna` short-context rates. The maximum single-call input was 70,847
tokens, far below the 272,000-token long-context threshold, so no surcharge applies.

| Component | Tokens | Rate | Cost |
|---|---|---|---|
| Cached input | 1,363,772 | $0.02 / M | $0.0273 |
| Cache writes | 811,612 | $0.25 / M | $0.2029 |
| Plain input | 138 | $0.20 / M | $0.0000 |
| Output | 281,166 | $1.20 / M | $0.3374 |
| **Total** | | | **≈ $0.57** |

This assumes cache-write tokens are billed at the write rate instead of the base input rate. If they
are billed in addition, the total is ≈ $0.73. The repository contains no pricing table, so this
remains an external estimate.

**Cache caveat.** Read facts ran at 99.995% cache hit (60,952 of 60,955 input tokens on the first
call) because the identical fact sheet and identical `01_read_facts.md` had run the previous day.
Sort facts saw `cached=0` on all three calls. **A first run on genuinely new source text will not see
these numbers**; measured cost and latency here are best-case.

### Storage

| Artifact | Size | Files |
|---|---|---|
| `_internal/trace/checkpoints.sqlite3` | 5,939,200 B | 1 |
| `_internal/trace/evidence.sqlite3` | 4,235,264 B | 1 |
| `_internal/trace/publications/` | 727,644 B | 12 |
| `_internal/trace/responses/` | 699,741 B | 20 |
| `_internal/inputs/` | 527,575 B | 9 |
| `domains/` | 506,170 B | 8 |
| `_internal/facts.jsonl` | 457,700 B | 1 |
| `_internal/trace/usage.jsonl` | 15,780 B | 1 |
| `run.log` | 7,983 B | 1 |
| `_internal/trace/history/` | 0 B | 0 |
| **Run total** | **13,477,170 B** | **65** |

Evidence index contents: 569 blobs, 563 paths, 1,677 snapshot member rows, 867 owner rows, and
projection collections of 409 ledger / 409 initial owners / 409 final owners / 409 decisions /
77 observations / 77 dispositions / 8 domains / 3 subjects / 2 audit items.

**Growth is reasonable and a large improvement.** 13.5 MB for a 490 KB source is 27x input size,
against schema 5's 29.0 MB (59x) for the same input — a 54% reduction achieved while storing 2.6x
more facts. The saving comes from `checkpoints.sqlite3` dropping from 26.1 MB to 5.9 MB.

WAL behaviour was healthy: `checkpoints.sqlite3-wal` grew monotonically to 4.1 MB, then checkpointed
into the main database (4 KB → 2.4 MB → 5.9 MB) and finished at 0 B. `evidence.sqlite3-wal` peaked at
13.6 MB during the assignment stage as the `owners` table filled, then also drained to 0 B. Nothing
grew without bound; only 65 files exist in total.

---

## 14. Failures, retries, stalls and breaking points

### 14.1 `design/000002` — `OperationalError`. Severity: **High**

```
06:57:30 job_scheduled design/000002 attempt=1 input_estimate=38773
06:57:31 input_estimate tokens=38796 reason=normal
06:57:34 input_estimate tokens=40909 reason=normal      ← tool-use turn
06:57:48 job_failed  design/000002 attempt=1 elapsed=17.73 error_type=OperationalError
```

`OperationalError` is `sqlite3.OperationalError` — a storage fault, not a model fault. The model was
working normally: two turns on thread `18f41046`, the second at 40,909 tokens after a tool call.

**What was lost.** Domain planning pages the Read facts records against a 40,000-token budget:

| Record | Tokens | Evidence rows | Page |
|---|---|---|---|
| s000001 | 14,409 | 55 | 1 |
| s000002 | 23,513 | 53 | 1 (37,922 ≤ 40,000) |
| **s000003** | **19,569** | **46** | **2 — failed** |

So the subject profile and 46 evidence rows for window 3 — bytes 329,456–490,449, covering the tail
of `Areas and plans` plus all fifteen remaining sections including `The lease`,
`Costs and offers` and `Tenancy and income` — never reached **initial** domain planning.

**Bounding the impact.** Page 1 had already produced the 8 baseline domains, identical in name to
schema 5, and page 2's role was to propose additions or responsibility updates. More importantly,
review *did* see all 409 facts including every window-3 fact, and `catalogue` then revised six of
eight domain definitions in light of them. So window 3's material influenced the **final**
definitions through review even though it missed initial design. The accurate statement is
"initial domains designed blind to window 3; final definitions informed by it" — not "domains
designed blind to fifteen sections".

**Recoverability.** 7 checkpoint rows persist for thread `18f41046`, and `run_jobs` resumes by exact
thread ID via `aget_state`. A resume would retry this page from its checkpoint. Not attempted —
read-only audit.

**Sibling preservation worked.** The run continued into `distribution` with the 8 domains from page 1,
completed the remaining 18 jobs, published all eight domains, and surfaced the failure in
`unresolved.md`. Completed results continued to be saved after the failure.

### 14.2 Exception detail is not persisted. Severity: **Medium**

`jobs.py:145` stores only `type(exc).__name__`, and the logger writes only `error_type=%s`. **No
exception message or traceback is preserved anywhere in the run.** The run's own artifacts therefore
cannot say which SQLite operation failed.

Candidates that cannot be distinguished from the evidence: contention on the single shared
`aiosqlite` connection behind `AsyncSqliteSaver` (`checkpoints.sqlite3-wal` was 861 KB and growing at
that moment), or `EvidenceStore.initialize()` re-running `PRAGMA journal_mode=WAL` plus `executescript`
DDL on every construction — and it is constructed fresh in `EvidenceBackend.__init__` on each graph
build and again inside `InputBudget.before_model`. It is **not** a lock timeout:
`connect(timeout=60)` would need 60 s and the job died after 17.73 s.

The authors already knew this surface is fragile — `jobs.py:32` carries the comment *"max_concurrency=1
inside a checkpointed graph can deadlock its pending SQLite writes during exception cleanup."*

**Why schema 6 hit this and schema 5 did not.** Schema 5 ran design as a single job. Schema 6
extracted richer Read facts output (154 rows vs 141), pushing the records past the 40,000-token page
budget into two pages — and the second page met the new SQLite and retrieval surface. Better
extraction exposed the fault.

### 14.3 Input estimator overshoots by ~1.9x on retrieval stages. Severity: **Medium**

| Logged estimate | Provider actual | Ratio |
|---|---|---|
| 109,675 | 57,365 | 1.91x |
| 117,331 | 62,945 | 1.86x |
| 124,958 | 66,920 | 1.87x |

On Read facts the same estimator was accurate to **1%** (69,547 estimated vs 60,955 actual, less the
deliberate 8,000 reserve). Divergence appears only once tool messages enter the conversation:
`estimate()` serialises each message via `model_dump()`, so `id`, `additional_kwargs`,
`response_metadata`, `usage_metadata` and tool-call scaffolding are all counted as prompt tokens.

Consequence: on tool-using stages the 300K target and 350K ceiling behave like roughly **160K and
185K real provider tokens**. The direction is safe — it pages and archives earlier than necessary,
never later — but it wastes more than half the window and is the exact mechanism by which
`InputSizeError` could reject an input the provider would have accepted. Harmless in this run, which
peaked at 42% of target.

### 14.4 No breaking point reached

| Guard | Peak observed | Limit | Headroom |
|---|---|---|---|
| Assembled input estimate | 127,189 | 300,000 target | 58% unused |
| Assembled input estimate | 127,189 | 350,000 ceiling | 64% unused |
| Single-call provider input | 70,847 | 272,000 (long-context) | 74% unused |
| Source windows | 3 | unbounded | — |
| Failed jobs blocking publication | 0 | — | — |

**Mechanisms that remain untested by this run**, and should not be scored as working:

- **Context-history archiving** — `InputBudget.before_model` never reached its archive branch; no
  `/history/` pages exist.
- **Oversized-roster comparison** (Phase 2 check 9) — `complete_definitions` always fitted with 8
  compact domains, so every stage took the inline path (`extract_and_assign`, `mode="update"`,
  `definition_scope="complete"`). The `compare`/`reconcile` machinery never ran.
- **Extract-once with separate ownership comparisons** (Phase 2 check 10) — never triggered, since
  definitions always fitted alongside the source.
- **Provider retry, timeout and permission handling** — no such event occurred.

---

## 15. Overall rating

### Acceptable with issues

**Working well:** orchestration and job accounting; window policy and Unicode safety, verified
byte-exact; ledger immutability with zero attrition from raw output; provenance honesty with zero
invented identifiers; numeric fidelity at 408 of 409; zero overlap duplication; complete assignment
coverage with healthy multi-domain distribution; visible failure handling with sibling preservation;
storage growth down 54% while holding 2.6x more facts; and a real quality gain over schema 5
(409 vs 157 facts, 77.3% vs 69.9% provenance retention).

**Not "Working well"** because one entire source section is missing from every output artifact while
the run reports complete coverage, and because a storage-layer fault left the run `partial` and cost
one subject group its place in initial domain design.

**Not "Unreliable"** because nothing the model produced was lost, altered, repaired or retried;
the failure was contained, visible and recoverable; and the published deliverable is complete and
usable for seven eighths of the source.

---

## 16. Prioritized improvements

1. **Add a source-region coverage observation.** Severity Critical. After Sort facts, record for each
   source window — or better, each byte range between section headings — how many facts were
   returned, and audit ranges that produced none. This is bookkeeping over Python's own dispatch
   records, not semantic inspection of model output, so it stays inside the `AGENTS.md` boundary. It
   is the only change that would have surfaced §7.1. Nothing today can.
2. **Persist exception messages and tracebacks.** Severity High. Store `str(exc)` and the formatted
   traceback beside `error_type` in `run.json` and the log. Without it §14.1 cannot be diagnosed, let
   alone fixed.
3. **Harden the SQLite surface.** Severity High. Run `initialize()` once per process rather than on
   every `EvidenceStore` construction, and hold one connection per stage instead of per operation.
   `design/000002` is the second SQLite-related hazard the code itself documents.
4. **Fix section-label grouping.** Severity Medium. Strengthen `03_sort_facts.md` to require reuse of
   a small, stable label set — for example, instruct the model to prefer an existing label and cap the
   count relative to fact volume. At 95% singletons the published Markdown is less readable than
   schema 5 despite holding far more.
5. **Correct the input estimator for tool-using stages.** Severity Medium. Count message *content*
   rather than the full `model_dump()`, so the 300K/350K policy applies to something close to real
   provider tokens instead of 1.9x of them.
6. **Validate observation `fact_ids` against the ledger.** Severity Low. Add an audit kind for an
   unresolvable reference, matching the existing treatment of `proposal_id` and `unknown_domain`.
7. **Consider retaining a provenance handle in published Markdown.** Severity Low. 2,731 of 2,734
   identifiers are dropped at publication, leaving the deliverable unauditable. A compact per-fact
   source handle would preserve traceability without reintroducing byte offsets or catalogue IDs.
8. **Exercise the untested paths deliberately.** Severity Low. A fixture with a large domain roster
   and one exceeding the context target would cover the `compare`/`reconcile` machinery, the separate
   ownership pass, and history archiving — currently three unverified mechanisms.

---

## 17. Evaluation limitations

- **No human gold-standard inventory exists.** This audit therefore does not claim proven 100%
  semantic completeness. It establishes a measured lower bound on omissions and distortions.
- **The provenance-identifier method is asymmetric.** A present identifier proves a bullet was seen.
  An absent identifier is evidence of omission but not proof, because substance can be captured
  without copying the identifier string. The 250 suspected omissions in §8 require human judgement;
  only the 31 in §7.1 are confirmed by two independent methods.
- **Content probes can produce false positives.** The source is largely German technical vocabulary
  while the ledger is English prose, so legitimate paraphrase can drop every probe token.
- **Numeric checking is pooled at section level, not bullet level.** A figure correctly present in the
  source but attached to the wrong neighbouring fact within the same section would not be flagged. The
  single distortion in §9.1 is a lower bound.
- **Dotted dates are excluded from numeric comparison** to avoid partial-match artefacts; they were
  reviewed as strings instead.
- **Applicability was screened exhaustively only for the 35% of facts using controlled vocabulary**;
  the remaining 65% use free prose and were sampled, not exhaustively read.
- **Entity-name distortion was screened, not exhaustively verified.** No instance was found, but
  proving absence across 409 facts would require full manual reading.
- **Cost figures are external estimates**, not measured billing. The repository contains no pricing
  table. Token counts are provider-reported and measured; the money is inferred.
- **Cache effects make latency and cost best-case.** Read facts ran at 99.995% cache hit because
  identical input ran the day before. A cold run will be slower and dearer.
- **Three mechanisms were never exercised** — history archiving, oversized-roster comparison, and the
  separate ownership pass — and are reported as untested rather than working.
- **The auditor's own tooling required three corrections** during the audit (number-separator
  equivalence between German and English formats, a greedy token span across list separators, and
  partial matching inside dotted dates). Earlier intermediate counts were higher and wrong; the
  figures in this report are from the corrected tooling.

---

*Audit performed 2026-09-09 against `runs/inputs-new-fact-sheet-9563041d/L2_20260909_065353_b707`.
Comparison baseline: `L2_20260908_155442_b6d1` (schema 5, byte-identical source).*

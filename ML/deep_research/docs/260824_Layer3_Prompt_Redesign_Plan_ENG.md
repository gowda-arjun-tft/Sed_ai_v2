# Layer 3 prompt redesign — plan for Codex

**Scope: prompt files only. No harness, runner, tool or schema changes.**
Evidence run: `runs/inputs-1-…/L3_20260821_182919_b675` (8 domain reports, 1 synthesis,
55 findings, 22 register entries). Repo prompts are byte-identical to the run-frozen
copies, so every diagnosis below maps onto the current files.

---

## 1. The objective the prompts must serve

One sentence, to be treated as the contract for every edit below:

> **Find current and emerging risks that can affect this asset's value — via income, capital
> expenditure, loss of use, insurability, compliance cost, liquidity or exit — by researching
> outward from the supplied facts, and state each risk once, at its root cause, with its value
> transmission.**

The current prompts optimise for something else: evidence-audit completeness. They produce a
register of what the data room is missing, rated on hypothetical life-safety severity, with no
value pathway. That is the gap between what was asked and what was written.

---

## 2. What the last run actually produced (measured)

| # | Failure mode | Measurement | Prompt cause (section below) |
|---|---|---|---|
| 1 | **Internal-risk echo** — supplied defects re-presented as findings | 27 of 55 domain findings (49%) are led by a gap/conflict in the supplied file, not by researched evidence; Asset Integrity 9 of 13 | §4.1, §4.2 |
| 2 | **Generic-framework recitals as "new evidence"** | 8 of 22 register entries cite a national law/standard (ArbStättV, ASR, DIBt, GEG…) as the new evidence; 3 more cite *where records would live* (ALKIS, Grundbuch) as if that were evidence | §4.3 (academic), §4.1 |
| 3 | **Fragmentation** — one root cause split into many risks | 22 register entries collapse to ~10 root causes. R1–R4+R13 all = "incomplete statutory safety assurance"; R10/R11 both = below-grade water; R12/R20 both = incomplete works/procurement | §4.2 (SKILL), §4.7 (synthesis merge rule) |
| 4 | **"No data" noise** | A mandatory `Missing evidence` list on all 55 findings and all 22 register entries (11% of register text); "unknown" ×32, "missing" ×30 in the synthesis alone | §4.2 (report spec orders it) |
| 5 | **No valuation linkage** | 9 passing mentions of value in 6,486 synthesis words; no per-risk value field; the mandated causal chain **ends at "building or people effect"** | §4.2, §4.4 (economist), §4.7 |
| 6 | **Impact inflation** | Impact High on 18 of 22 entries, mostly hypothetical life-safety worst cases; Likelihood Unknown on 8 | §4.6 (shared_rules scale) |
| 7 | **Verifier over-spend on the wrong claims** | citation-verifier: 219 of 525 model calls, 476 of 1,481 searches, 23.9% of tokens — largely verifying that statutes say what they plainly say | §4.8 (verifier) |
| 8 | **Lens roles misfire** | academic = "laws" guarantees framework recitals in all 8 domains; historian drifts to precedent; economist is gated behind "established pathways" and never completes value transmission; practitioner re-walks the supplied defect list | §4.3–§4.5 |

What already works and must be preserved: the skeptic's nearby/current scan (U2 works,
parkhaus fire, bus-route changes — all found and dated), the LEO II lease discovery, the
tiered-geography rule, primary-source discipline, direct source links, and the ban on
recommendations/investment advice.

---

## 3. Root-cause analysis of the lens roles

The five lenses are defined by **evidence method** (laws / operations / money / history /
doubt), not by **research question**. On a single building, a method split makes every lens
re-walk the same systems from a different angle, which produces five overlapping accounts of
the same supplied defects — the direct source of fragmentation and overlap. Two names actively
mislead the model: "academic" pulls toward literature and statutes (→ recitals), "historian"
pulls toward precedent (→ irrelevant history). And no lens owns the question the user actually
asked: *what does this do to the asset's value?*

**Fix without code changes:** keep the five filenames and subagent names
(`practitioner`, `academic`, `skeptic`, `economist`, `historian` — they are wired in
`contracts.py`), but rewrite each file so the *role* is a research question, not a method:

| File (unchanged) | New role | Owns the question |
|---|---|---|
| `practitioner.md` | **Site investigator** | What can actually fail at this address, and what does public evidence *add* to each supplied defect? |
| `academic.md` | **Applicability checker** | Which obligations bite *this* building because of a supplied characteristic — deviation, dated deadline inside the hold, cost trigger? |
| `skeptic.md` | **Local & current scanner** | What is happening around the property now and through the hold, and where do the supplied interpretations break? |
| `economist.md` | **Valuation-transmission analyst** | For each exposure, what is the value mechanism, direction and rough magnitude class? |
| `historian.md` | **External-shock & continuity analyst** | What forward regime, dependency, occupier-continuity or geopolitical change reaches this asset? |

*(Optional, flagged as a code change and therefore out of scope here: renaming the files and
`LENS_NAMES`/`LENS_DESCRIPTIONS` to match the new roles.)*

---

## 4. Change specification, file by file

### 4.1 `layer3/prompts/shared_rules.md`

Keep: input-authority rules, primary-source discipline, tiered proximity, search anchoring,
the likelihood/impact scale *definitions*, output boundaries.

**Change A — extend the causal chain to value.** Replace the chain

```
new evidence → property fact → exposure → vulnerability → building or people effect → time horizon
```

with

```
new evidence → property fact → exposure → vulnerability → effect on building, people or operations
→ value transmission (income | CapEx | loss of use | insurability | compliance cost | liquidity/exit)
→ time horizon
```

and add: *"A risk with no plausible value transmission is `Context only` even when the
building effect is real. State the transmission mechanism and direction; never a price,
a valuation figure, or advice."*

**Change B — kill the internal echo.** Add one rule under "Research rules":

> *"The supplied property file is known to the reader. A supplied defect, gap or
> contradiction is a research anchor, not a finding. Report it only when public research has
> added, dated, contradicted or priced something about it. If research adds nothing, the
> anchor goes to the one-line `Not researchable further` list — never to a risk block."*

**Change C — evidence-class honesty.** Add:

> *"`New evidence` must be property-specific or locally dated. A national law, technical
> standard, market statistic, or the name of a register where records would live
> (Grundbuch, ALKIS, Baulasten) is not new evidence; it may appear only inside the linkage
> explanation of a finding whose new evidence is property-specific."*

**Change D — recalibrate impact.** Extend the impact definitions with:

> *"Rate impact on the realistic asset effect supported by the evidence, not on the worst
> conceivable outcome of the hazard class. `High` requires an ongoing, announced, repeated
> or directly evidenced trigger — a documentation gap alone is at most `Medium` and its
> likelihood refers to the probability of the adverse condition existing, not to the
> certainty that records are missing."*

**Acceptance:** the words "value transmission" appear in the chain; the four added rules
present; the file stays under ~90 lines.

### 4.2 `layer3/SKILL.md`

Keep: the 7-step STORM procedure shape, one `task` per lens in one response, verification
clusters, "final assistant response is authoritative", the ban list.

**Change A — findings are causal families.** In step 4 and in the report spec, define:

> *"One finding = one root cause. If two candidate findings share the same root cause, the
> same missing record, or the same trigger, they are one finding with multiple effects
> listed inside it. Enumerate effects within the block; never split them into siblings."*
> (Concretely: the last run's four fire-assurance blocks R1–R4 must become one.)

**Change B — the report block.** Replace the current block fields with:

```
- Risk finding            (root cause, one sentence)
- New/current evidence    (property-specific or locally dated only)
- Existing property fact  (one line; the anchor, not the defect list)
- Property linkage
- Value transmission      (mechanism → direction; magnitude class if supportable)
- Likelihood: Low|Medium|High|Unknown   Impact: Low|Medium|High|Unknown
- Time horizon and status
- Sources
```

`Missing evidence` is **removed from the block**. Add one final report section instead:

```
## Evidence gaps (single table)
| Gap | Blocks which finding(s) | Where the record lives |
```

and one line-per-item list `## Supplied anchors with nothing found` for anchors research
could not extend (replaces today's per-block no-data prose).

**Change C — step 2 task content.** Each lens task must carry: the property address/district
block, the anchors, **and the instruction "research outward from these anchors; do not
re-audit the supplied file"**.

**Acceptance:** `Missing evidence` absent from the block spec; `Value transmission` present;
the causal-family rule present; the two new terminal sections specified.

### 4.3 `layer3/prompts/lenses/academic.md` → applicability checker

Full replacement:

```markdown
# Academic lens — what actually binds this building

Own regulatory and technical applicability for this specific asset. Start from the supplied
characteristics (age, systems, use as a court, garage, works programme) and establish only:
(a) obligations this building deviates from, (b) dated requirements that fall due within the
hold, (c) requirements whose cost or scope is triggered by a supplied fact.

The test for reporting anything: name the supplied characteristic that creates the
applicability, the effective date, and the cost or compliance consequence for this building.
A framework that applies identically to every comparable building in Germany is context —
never report it, cite it, or verify it as a finding. Do not enumerate a statute's content;
state the delta between what it requires and what the supplied records show.

Prefer enacted primary records; separate enacted from proposed. When applicability cannot be
determined from a supplied fact, write one line naming the missing fact and move on.
```

### 4.4 `layer3/prompts/lenses/economist.md` → valuation-transmission analyst

Full replacement:

```markdown
# Economist lens — value transmission

Own the translation of exposures into asset-value effect. For each anchor and each exposure
suggested by the assignment, establish the mechanism and direction through which it reaches
value: rental income, recoverability, CapEx and works cost, loss of use or void, insurability
and premiums, compliance cost, buyer pool, financing terms, or exit timing.

Start from the property fact, not from macro data. Rates, inflation, construction prices,
market statistics and benchmarks may be used only to size or date a transmission that a
property fact has opened. State magnitude as a class (immaterial / meaningful / material to
value) with the evidence for that class; where the class cannot be supported, say which single
number would settle it.

You are required to state value direction and mechanism. You are prohibited from stating a
price or valuation figure, proposing a transaction response, or giving an investment
conclusion. If an exposure has no plausible value transmission, say so in one line — that is
a useful result.
```

### 4.5 `layer3/prompts/lenses/practitioner.md`, `skeptic.md`, `historian.md`

**practitioner.md** — keep the operational ownership, add the outward-research rule and drop
the audit invitation. Replace the second paragraph with:

> *"For each supplied defect or anomaly, research outward: the operator, contractor,
> manufacturer, product line, permit authority or service provider it names. Establish what
> public evidence adds — recalls, discontinuations, insolvency, announced works, authority
> notices, capacity constraints. The supplied condition itself is the anchor, never the
> finding. When public evidence cannot extend an anchor, record it in one line under the
> report's `Supplied anchors with nothing found` list."*

**skeptic.md** — closest to correct; keep whole. Add one sentence at the end:

> *"For every local development you establish, hand the value question to the report:
> name which access, cost, use or demand channel it touches."*

**historian.md** — reframe forward. Replace the first sentence and the history paragraph:

> *"Own forward-looking external change and continuity. Lead with: occupier continuity
> (state budget, court reform, e-justice and space policy), energy and utility dependency,
> installed-equipment vendor and sanctions exposure, specialist labour and materials,
> cyber and physical threat environment of a public justice building. Historical records may
> be used only to date or size a forward pathway already anchored in a supplied fact — one
> sentence of comparison at most, and never as a finding on their own."*

### 4.6 ~~`LENS_DESCRIPTIONS` in `layer3/prompts.py`~~ — WITHDRAWN (user ruling 260824)

**No Python file may be touched, including prompt strings embedded in `.py` files.**
`LENS_DESCRIPTIONS` and `domain_message()` stay byte-identical. The behavioural change is
carried entirely by the Markdown prompt files: the lens role redefinitions live in the lens
`.md` files (which the coordinator's subagents receive as their system prompts), and the
value-transmission requirement lives in `SKILL.md`, `shared_rules.md` and `synthesis.md`.

A further consequence of the no-Python rule: **every string pinned by `tests/` must be
preserved verbatim in the rewritten prompts** (including the five lens heading subtitles,
`new evidence → property fact → exposure → vulnerability`, `Likelihood: Low | Medium | High |
Unknown`, the synthesis section names, and the verifier verdict labels), so that no test file
needs editing. The chain is therefore *extended at the tail*, never rewritten.

### 4.7 `layer3/prompts/synthesis.md`

**Change A — the merge rule** (the single line that caused 22 rows for ~10 causes). Replace

> "Merge findings only when they share the same trigger, property dependency, exposure,
> vulnerability and effect."

with

> *"Merge findings that share a root cause, a missing record, or a common trigger into one
> register entry per causal family; enumerate the distinct effects inside the entry. Keep
> genuinely distinct causes separate even when they share a financial consequence. The
> register should contain causal families, not building systems — if two entries could be
> fixed by the same action or settled by the same record, they are one entry."*

**Change B — the register block**: mirror §4.2's block (add `Value transmission`, delete
`Missing evidence` per block, add the single `Evidence gaps` table and the
`Supplied anchors with nothing found` list as terminal sections).

**Change C — ordering**: *"Order the register by value materiality (impact × likelihood,
value transmission first), not by domain of origin."*

**Acceptance for the next run:** register ≤ 12 entries for this asset; every entry carries a
`Value transmission` line; no per-entry missing-evidence prose.

### 4.8 `layer3/prompts/verifier.md`

Keep verdicts and linkage classifications. Add a scope rule at the top:

> *"Verify claims in this priority: (1) property-specific facts and dated local events,
> (2) value-relevant figures, dates and deadlines, (3) quoted contractual or portfolio
> records. Do not verify that a national statute or technical standard exists or says what
> it plainly says — classify such citations as framework context in one line and move on."*

**Expected effect:** the verifier (currently 42% of model calls, 24% of tokens) concentrates
on the claims that can actually be wrong.

### 4.9 Layer 2 — `layer2/prompts/chunk_router.md` (+ mandate wording in `planner_prompt.md`)

Carried over from `260821_Generic_Output_Diagnosis_ENG.md` §"Areas of improvement" #1/#7,
restated here because it is half of the "extract from what I gave it" complaint:

- The router must emit, per domain: (a) verbatim facts as now, (b) **a deduplicated list of
  specific open questions and anomalies as first-class output** ("garage gate failed —
  status, cost, operational impact?"), (c) **an address/geo block** (street, district
  Gonzenheim, neighbours) so downstream searches have anchors. One mission paragraph, not
  one per chunk.
- Mandates in `planner_prompt.md`: append to each mandate one sentence — *"State every
  supported risk's value transmission for this asset."*

---

## 5. Acceptance tests for the first run after the changes

1. **Echo test:** ≤ 15% of findings led by a supplied-file gap (last run: 49%). Every
   finding's `New/current evidence` is property-specific or locally dated — zero entries
   whose new evidence is a bare statute or a register name (last run: ≥ 11 of 22).
2. **Fragmentation test:** synthesis register ≤ 12 causal-family entries for this asset
   (last run: 22); the four fire-assurance entries appear as one.
3. **Valuation test:** 100% of register entries carry a `Value transmission` line with
   mechanism + direction (last run: 0).
4. **Noise test:** exactly one `Evidence gaps` table and one `Supplied anchors with nothing
   found` list per report; no `Missing evidence` field inside any risk block (last run: 55).
5. **Calibration test:** Impact `High` only with an ongoing/announced/evidenced trigger
   (last run: 18 of 22 High).
6. **Preserved behaviour:** nearby/current findings (U2, parkhaus, bus routes) still present
   and dated; still zero recommendations/advice sentences; direct source links retained.

## 6. Explicitly out of scope

- **Any `.py` file, without exception** — including prompt strings inside `prompts.py`
  (`LENS_DESCRIPTIONS`, `domain_message`, `synthesis_message`) and all test files. Only these
  Markdown files may change: `layer3/SKILL.md`, `layer3/prompts/shared_rules.md`,
  `layer3/prompts/verifier.md`, `layer3/prompts/synthesis.md`, the five
  `layer3/prompts/lenses/*.md`, `layer2/prompts/chunk_router.md`,
  `layer2/prompts/planner_prompt.md`.
- Renaming lens files/subagent names (`contracts.py`).
- Any change to tools, runner, schema, checks, or the verifier's tool surface.
- Adding limits or output caps of any kind.

---

## 7. Addendum (260824) — synthesis fidelity and telegraphic density

Added after a second user review of run `L3_20260821_182919_b675`. Two further measured defects,
two further rule sets. Same scope: prompt content only.

### 7.1 The synthesizer compresses by abstracting, not by deduplicating (measured)

Comparing the eight domain reports (24,565 words) with the synthesis (6,486 words):

| Specific fact class | In domain reports | Survives into synthesis |
|---|---|---|
| Euro amounts | 49 distinct | 7 (**14%**) |
| Specific numbers (areas, flows, kW, %) | 86 distinct | 21 (**24%**) |
| Dates / years | 90 distinct | 32 (**36%**) |
| § / paragraph references | 72 distinct | 26 (**36%**) |
| Source links | 215 distinct | 102 (**46%**) |

The model reads "compact" as "less precise": it merges by generalising and throws the payload
away. **Fidelity rule for `synthesis.md`:** compression comes from removing duplication and
narration, never from dropping specifics. A merged register entry carries over every date,
amount, quantity, identifier and source link from the entries it merges (semicolon-separated
fact fragments); a specific may be omitted only when the identical fact already appears
elsewhere in the synthesis. Fact retention per word is the target, not word count.

### 7.2 Narration overhead (measured)

The English is not classically bloated (median sentence 13 words, ~1% repeated sentences). The
fat is **evidence-status narration**: across the nine reports (31,051 words) the word
"evidence" appears 310×, "the supplied" 88×, "supplied records" 44× — sentences describing what
could not be established instead of stating facts. **Density rules for `shared_rules.md` /
`SKILL.md` / lens prompts:**

- Telegraphic fact lines inside risk-block fields; fragments preferred over sentences.
  Teaching example: `Gate failed since 03/2025; repair unscheduled; 41 of 98 spaces unusable` —
  never "The subject garage roller gate is reported failed or immobile, which may…".
- Payload test: every line carries a number, date, name, place, identifier, source link or
  classification; a line with none is deleted in self-review, not reworded.
- No connective or meta filler (however, moreover, furthermore, it should be noted…); no
  restating the question; no describing what the research did — only what it found.
- Each fact stated once per report; later mentions refer back, never re-explain.
- Evidence-status prose is banned from findings: unknowns live once in the `Evidence gaps`
  table or the `Supplied anchors with nothing found` list.

These are style/fidelity constraints, not numeric caps — none may be expressed as a maximum
word, line or finding count.

### 7.3 Additional acceptance tests for the next run

7. **Fidelity test:** ≥ 80% of the distinct euro amounts, numbers, dates and § references
   present in the domain reports appear in the synthesis (last run: 14–36%).
8. **Density test:** occurrences of "the supplied"/"supplied records" per 1,000 words fall by
   half; no finding block contains a sentence without a payload element.

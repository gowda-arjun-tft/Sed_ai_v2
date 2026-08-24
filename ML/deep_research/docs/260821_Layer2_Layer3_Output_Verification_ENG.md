# Archived schema-5 Layer 2 & Layer 3 output verification

> Historical run audit only. This document records the retired direct-research/reviewer workflow
> and is not the current schema-6 STORM architecture contract. See
> `260818_Deep_Research_Module_Architecture_ENG.html` at the repository root for the active design.

Verification only. No code changed. Every number is measured from
`runs/L2_20260820_968d` and `runs/L3_20260821_29a2`.

## Verdict

**The research is legitimate and it does catch patterns.** The substance is good.
The **form** is wrong in three specific, measurable ways, and you identified all
three correctly.

| | Finding |
|---|---|
| Layer 2 | Efficient (1 model call) and 97.2% faithful. One regression: the `where` locator is gone. |
| Layer 3 content | Real. Caught a direct contradiction of a data-room assertion from a primary source. |
| Layer 3 form | Cannot say "no risk" — **0 occurrences** in 56,163 words. No risk is rated or sized. 16.8% of each report is inter-agent plumbing. |

---

## Layer 2 — good

```
1 model call   12,831 input   40,295 output (22,997 reasoning)   53,126 total
467-line sheet -> 182 context entries across 8 missions
```

One call. The loop is gone. This is the shape it should be.

**Fidelity 97.2%.** Of 249 quoted segments, 242 appear byte-exact in the fact
sheet after Unicode normalisation. The 7 misses are all in
`asset-integrity` and all the same fault: the agent put **its own summary
sentence** in the `fact` field instead of a quote —

> "302 physical files; 268 unique hashes; 236 read, 34 duplicate, 31 unreadable…"

That is the agent's arithmetic presented as a document quote. 2.8%, contained,
but it is the one place Layer 2 stops transcribing and starts writing.

### The one regression: `where` is gone

Context entries are now `{section, fact, means}`. The locator —
`"file · page · document date"` — has been dropped, and `report.py`'s four checks
no longer verify mission shape at all beyond "valid JSON".

**Measured downstream consequence.** Across all eight Layer 3 reports:

```
".pdf" references          0
"page N" references        0
"document dated"           0
generic "property-file" /
"data-room" / "supplied record"   86
```

Every property-side claim in the entire Layer 3 output is attributed to an
unnamed blob, because Layer 3 has no locator to name. **This is the single
highest-value thing to restore**, and it costs nothing in tokens — a locator is
shorter than the hedge sentence that currently replaces it.

---

## Layer 3 content — legitimate, and it catches patterns

Verified against the source. The real catches:

1. **The data room says the site is unplanned `§34 BauGB` with no
   Bebauungsplan. The municipality publishes "Bebauungsplan Nr. 117" covering
   "Auf der Steinkaut".** A direct contradiction of a data-room assertion, found
   in the primary public record. This is the highest-value finding in the run and
   exactly what the system exists to do.
2. Parking allocation internally inconsistent: 58 + 39 vs 55 + 34 — both total
   89, so the total is right and the split is not.
3. DM 213,000 uncapped vs DM 200,000 after the statutory cap for ten spaces.
4. Rent 66,232.61 → 72,458.48 → 78,255.17 = **+7.8% / +9.4% / +8.0%**, reconciled
   arithmetically, against a lease **7.5% CPI threshold**. Every step exceeds the
   threshold. That is a genuine pattern, not a transcription.
5. The FMC maintenance framework does not transfer on sale → an Opex cliff at
   closing that the file does not price.
6. Eurohypo charge unreleased; printed land-charge amounts inconsistent.
7. Heilquellen-/Trinkwasserschutzgebiet → drainage, fire-water and works
   conditionality.

I am satisfied with the substance. I am not satisfied with the form.

---

## The three problems you named — all confirmed

### 1. It is not risk-first, and it cannot say "fine"

Searched all eight reports **and** the final answer:

```
"no risk" / "no material risk" / "no issue" / "no concern"
"working fine" / "no action required"                          →  0 matches
severity / likelihood / high risk / medium risk / low risk
risk rating / quantum                                          →  0 matches each
```

118 finding blocks, by status:

```
unknown      45   38%
supported    36   31%
inference    35   30%
immaterial    2    2%
```

And `supported` does **not** mean cleared. The one I pulled establishes site
identity from the file, then closes: *"The parcel inconsistency is a
document-control risk rather than evidence of a different asset."* A supported
identification still carries a risk tail.

The two `immaterial` blocks are not "no risk here" either — they are
methodological notes explaining why comparable assets cannot answer title
questions, at 600+ characters each.

**The system has no vocabulary for "fine".** It can say established, unverified,
inferred. It cannot say *"checked, no risk, working as documented for the given
information"* — which is what a reader needs on the domains that are clean, and
which is what makes the domains that are dirty stand out.

### 2. Explanation crowds out fact — and 16.8% is not for the reader

232,057 characters across eight reports (~58,014 tokens, 28,629 words). Where
every character goes:

```
Decision finding       70,314   32.1%
Evidence and basis     68,627   31.3%
Property consequence   41,968   19.1%
Boundary or handoff    36,923   16.8%   ← no human needs a word of this
Status                  1,446    0.7%
headings / other       12,779    5.5%
```

`Boundary or handoff` is one agent telling another agent what to pick up — in a
design where Python routes nothing between them and the agents never speak. It
appears **118 times**. And it is not written once and forgotten:

```
8 domain reports written                    232,057 chars
reviewer reads all 8                        232,057 chars of input
synthesis reads all 8 + the review          259,006 chars of input
→ the handoff share alone: 38,985 x 3 ≈ 117,000 chars billed, zero reader value
```

Hedge density across the eight reports: `property-file` ×52, `Obtain ` ×42,
`should be` ×37, `not independently verified` ×14, `unverified` ×12. One citation
per 146 words.

### 3. Token efficiency — one real win, one regression

The search fix landed:

```
                  per-search input    reasoning
previous run           56,138           3,621
this run               31,009           1,054
```

But the run total went **up**: 29.8M vs 26.4M, because agent calls went 157 → 290
and per-call input 59,490 → 80,139.

In money terms — uncached input is what bills at full rate:

```
model        uncached in 2,178,594   out 178,561    (90.6% cached — cheap)
web_search   uncached in 5,294,355   out 295,030    (86.7% uncached)
```

Search is still ~70% of real cost. The agent side is now 90.6% cached, which
means prompt reuse is working; the growth there is largely paid at cache rates.

### 4. Duplicate published output

**Five of eight `.partial.md` files are byte-identical to their `.md`.** About
117 KB of the published bundle is a copy of itself. Only the three domains that
received a clarification round actually differ. The file open in your editor,
`asset-integrity…partial.md`, is byte-identical to the final.

### 5. The mandated report shape is being ignored, and that is what multiplies volume

`five_questions.md` mandates eight named sections ending in
`## Evidence saturation`. The reports instead use `## Practice — <title>` and
`## Authority — <title>` as **repeated block headers, 118 of them**, each with the
five-field template. The five questions became a taxonomy prefix on every finding
rather than five sections. That single drift is the structural driver of the
volume: 118 blocks × 5 labelled fields ≈ 590 prose paragraphs per property.

---

## What I would change

Four changes. Only the first two touch the model.

**1. Make the finding contract risk-first and fact-only.** Replace the five-field
block with:

```
### <finding>
risk: none | low | medium | high        ← "none" must be sayable
basis: <fact, or exact quote + citation marker>
effect: <one line: what it does to income, cost, value, timing, or exit>
resolve: <the single document or authority that would settle it, or "-">
```

`Boundary or handoff` is deleted. `Decision finding` and `Evidence and basis`
merge into `basis` — currently they say the same thing twice at 32% + 31%.
Crucially, **`risk: none` must be a legal, expected outcome**, with a one-line
basis and nothing else. A clean domain should be four lines, not 20,000
characters.

**2. Restore `where` in Layer 2.** One field, and it converts 86 vague
"property-file" references into named documents. Cheaper than the hedging it
replaces.

**3. Stop publishing `.partial.md` when it equals the final.** Pure dump.

**4. Drop `## Evidence saturation` from the mandated shape.** It tells the agent
that the extent of its searching is part of the deliverable. It is not.

Expected effect on the deliverable, from the measured composition: removing
handoffs (16.8%), de-duplicating the two overlapping evidence fields, and
allowing `risk: none` should take eight reports from ~58,000 tokens to roughly
15,000–20,000 — without losing one of the seven real findings above, all of which
survive as a `basis` line plus an `effect` line.

---

## Answering your questions directly

**Is it legit?** Yes. The Bebauungsplan Nr. 117 contradiction alone justifies the
run — a data-room assertion refuted from the primary municipal record.

**Does it catch the pattern?** Yes. Rent steps against the CPI threshold, the
parking split that doesn't match its own total, the capped-vs-uncapped payment,
the non-transferring maintenance contract. These are pattern catches, not
transcription.

**Am I satisfied?** With the findings, yes. With the packaging, no — and the
specific reason is that **nothing in the output distinguishes "this is a problem"
from "this is a paragraph".** 118 blocks all look alike, all hedge alike, and
none of them can say "no risk". That is a contract problem, not a model problem.

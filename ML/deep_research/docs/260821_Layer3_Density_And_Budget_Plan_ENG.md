# Archived schema-5 Layer 3 density and budget plan

> Historical run analysis only. The measurements and recommendations below describe the retired
> direct-research/reviewer workflow, not the current schema-6 domain-scoped STORM architecture.
> See `260818_Deep_Research_Module_Architecture_ENG.html` at the repository root for the active
> design.

Plan. No code changed. Web research as requested; every claim carries its source. Measurements are
from the installed stack and `runs/L3_20260821_29a2`.

## 0. Your premise is right about quality and wrong about cost

Price sheet, fetched from OpenAI docs: `gpt-5.6-luna` input **$0.20** / cached input **$0.02** /
cache write **$0.25** / output **$1.20** per 1M; web search **$10.00 per 1k calls, plus search
content tokens billed at model rates**
(<https://developers.openai.com/api/docs/pricing>).

Applied to the measured run — 29,822,727 tokens, **$4.58**:

| line item | tokens | $ | share |
|---|---|---|---|
| web_search **tool fee** (197 × $10/1k) | — | 1.970 | **43.0%** |
| web_search fresh input | 5.29M | 1.059 | 23.1% |
| model cache writes | 2.18M | 0.544 | 11.9% |
| model cached reads | 21.06M | 0.421 | 9.2% |
| web_search output | 0.30M | 0.354 | 7.7% |
| model output | 0.18M | 0.214 | 4.7% |
| remainder | 0.82M | 0.017 | 0.4% |

**Retrieval is 74.2% of spend. Every output token in the run together is 12.4%. The eight published
reports specifically are $0.060 — 1.3%.**

Two marginal numbers decide everything:

```
one web_search call = $0.01725      one model turn = $0.00407
→ a search costs 4.2x a model turn
→ one avoided search pays for 14,375 output tokens
→ the entire eight-report corpus costs the same as 3.5 searches
```

So: **compacting the output cannot save more than ~$0.57 and realistically saves ~$0.07.** Do it
anyway — dense risk-first output is the deliverable you asked for and the reports are unusable as
they stand. But it must be funded as a **quality** change. The cost fix is the search budget.

`$4.58` is a floor: search-leg cache writes log as zero (see §2), so true cost is up to ~$4.84.

---

## 1. Live bug in the STORM code already built

All six subagents carry only `_NoFilesystemMiddleware`. **None carries the project's summarization
middleware**, and parent middleware does not propagate to explicit subagents — deepagents applies
only `spec["middleware"]` (`graph.py:698-702`; `permissions` propagates, middleware does not).

Measured on the built graph:

```
practitioner   middleware=['_NoFilesystemMiddleware']  project_summarizer=False
academic       middleware=['_NoFilesystemMiddleware']  project_summarizer=False
skeptic        middleware=['_NoFilesystemMiddleware']  project_summarizer=False
economist      middleware=['_NoFilesystemMiddleware']  project_summarizer=False
historian      middleware=['_NoFilesystemMiddleware']  project_summarizer=False
citation-verifier  middleware=['_NoFilesystemMiddleware']  project_summarizer=False

harness DEFAULT for gpt-5.6-luna: trigger ('fraction', 0.85), keep ('fraction', 0.1)
  max_input_tokens 1,050,000  →  default trigger ~892,500 tokens
  project trigger                              180,000 tokens
  → an unfixed lens carries 5.0x the intended context
```

**48 sessions per property (6 subagents × 8 domains) are configured to carry five times the context
budget the project set.** Fix: add `context_middleware(model, backend)` to each spec's `middleware`
list in `layer3/llm.py::_subagents`. One line, and it must land before any eight-domain run.

Credit where due: the built code *did* dodge the two traps next to it. `FilesystemMiddleware` is
required scaffolding and `read_file` is mandatory inside it — `_NoFilesystemMiddleware` handles that
— and replacing the base instance by name silently zeroes `_permissions`, which the per-spec
`permissions` key avoids.

---

## 2. Ranked levers

Ranked by effect on the **$4.58**, not by novelty.

| # | lever | kind | effect here | cost |
|---|---|---|---|---|
| 1 | **Search budget per domain, coordinator-allocated, enforced in the tool** | structural | Attacks the 74.2%. Turns the 8×5 plan from **$12–19** into **$4.0–5.5**. Deterministic. | ~20 lines in `research_tools.py::_search`: a per-session counter + an allocation. Needs a **floor** as well as a ceiling. |
| 2 | **Fix the lens context policy** (§1) | config | 48 sessions at 5× intended context. | 1 line |
| 3 | **`reasoning_effort` per step** | API param | Largest raw number in the repo: `backup_low_L3_20260821_8c04` ran the same 8 domains for **1,210,873** tokens vs 29,822,727 — 24.6×, and **17 searches vs 197**. Provider-documented as the *tool-call* control: *"Switch to a lower `reasoning_effort`. This reduces exploration depth"* (GPT-5 prompting guide). | 1 line, but **discount it**: that run isn't like-for-like — 4 of 8 domains ran zero searches, 29% of the published volume, `status: failed_validation`. Per published character it's ~7.2×, not 24.6×. Medium is untested. |
| 4 | **Verdict enum + coverage ledger** | output contract | Small token effect (~$0.007) but the **only** lever that produces what you asked for. `shared_rules.md` defines four statuses and none means "checked, clean" — which is why "no risk"/"no material risk"/"no issue"/"working fine"/"no action required" return **zero matches** across all eight reports. No prompt wording emits a value the vocabulary lacks. | Schema + prompt. §3. |
| 5 | **`text.verbosity="low"`** | API param | Ceiling is all model output = **$0.214 (4.7%)**. Cookbook measures output scaling roughly linearly: low 560 → medium 849 → high 1288, so low ≈ 0.66× medium. | 1 line. Two traps below. |
| 6 | **`prompt_cache_key`** | API param | Not a saving — **insurance worth up to $3.8**. If the 90.6% hit rate collapses, 21M tokens move from $0.02 to $0.20/1M. | 1 param + prompt-ordering discipline. |
| 7 | Structured output | structural | **Not a token lever.** Measured on this project's own 118 findings with tiktoken o200k: markdown 50,312 / TSV 47,888 (0.95×) / compact JSON 50,270 (0.999×). Use it for shape, not size. |
| 8 | Per-unit prompt budgets | wording | Direction documented (*"Give clear and concrete length constraints"*, GPT-5.2 guide). But length-instruction violation rates are **37–49%** (arXiv 2406.17744), so budget the **finding**, not the report, and check the fragment. |
| 9 | `max_output_tokens` | API param | **Not a density lever.** Hard cut → `status="incomplete"`, possibly before any visible text; you pay input and reasoning for nothing. Blast-radius cap only, with a status check. |
| 10 | `reasoning.context="current_turn"` | API param | **Dead on this stack — do not adopt.** With `store=False` and no `include=["reasoning.encrypted_content"]`, LangChain drops reasoning from replayed input, so `all_turns` has nothing to render. Total model-leg reasoning is 51,537 tokens = **0.22%** of model input. I was wrong to be excited about this one. |
| 11 | Chain of Density | wording | Real, but measured on 72-token news summaries, N=100, κ=0.112, human preference peaking at step 2–3 of 5. Each pass is a full extra generation over the whole draft. At most one bounded self-review pass, after §3 lands. |

### `verbosity` — verified end to end on the installed stack

```python
m = init_chat_model("openai:gpt-5.6-luna", use_responses_api=True, verbosity="low")
m._get_request_payload(...)   # → {'model': 'gpt-5.6-luna', 'text': {'verbosity': 'low'}, ...}
```

`verbosity` is a named field on the installed `ChatOpenAI` and is auto-nested into `text.verbosity`.
Two traps, both measured:

```
bare kwarg override  → {'verbosity': 'high'}     works
text={...} override  → {'verbosity': 'low'}      SILENTLY IGNORED
```

Per-step density must use the bare `verbosity=` kwarg or `.bind(verbosity=...)`. And the provider's
guidance is to set the parameter globally and put narrow exceptions in prose, **not the reverse**:
*"GPT-5 is trained to respond to natural-language verbosity overrides in the prompt for specific
contexts where you might want the model to deviate from the global default."*

**Unverified:** the luna model page does not list `verbosity`, and the 560→849→1288 measurement is
gpt-5-mini. One API call settles it — see §6 gate 4.

### Two config hazards that must ship together

- LangChain converts `reasoning_effort` → `reasoning` **only when `reasoning` is absent**. Changing
  `layer2/harness.py:26` without `layer3/llm.py:58` in the same commit ships both keys and likely
  400s every Layer 3 call.
- Two settings modules disagree: `layer2/settings.py` is `"max"`, `layer3/settings.py` is `"high"`.

### The usage bug, confirmed

```
Responses InputTokensDetails fields : ['cache_write_tokens', 'cached_tokens']
LangChain InputTokenDetails keys    : ['audio', 'cache_creation', 'cache_read']
```

`usage.py` looks for `cache_creation`. That is correct for the **agent** leg (LangChain normalises
it) and wrong for the **search** leg, which reads the raw Responses object where the field is
`cache_write_tokens`. All 197 search-leg cache writes log as zero. Add `"cache_write_tokens"` to the
key tuple before quoting any cost number.

---

## 3. The output contract — what you actually asked for

Measured per finding (118 findings, 232,057 chars, 1,967 chars each):

| field | chars | share | verdict |
|---|---|---|---|
| Decision finding | 596 | 32.1% | **cap, don't cut** — this is the answer. One clause, not a paragraph. |
| Evidence and basis | 582 | 31.3% | **protect** — the only auditable content. Move the quote to the citation record, keep the id inline. |
| Property consequence | 356 | 19.1% | **conditional** — required when verdict ≠ no-risk, absent otherwise. |
| Boundary or handoff | 313 | 16.8% | **move, don't delete** — `reviewer.md` is instructed to analyse cross-domain chains, so deleting it breaks a consumer. Convert to an edge list. |
| Status | 12 | 0.7% | **keep and add a second axis** — 38% unknown is an *evidence* state, not a *risk* state. Conflating them is exactly why zero risk verdicts appeared. |

```markdown
# <Domain name>
VERDICT no-risk | findings 15 | risk 3 (1 high, 2 med) | unknown 4 | searches 18/20

## Coverage
practice     checked  no-risk   | authority    checked  risk R2,R7
economics    checked  no-risk   | comparables  checked  unknown U1
challenge    checked  risk R11
not-checked  none

## Findings
R2  risk:high  supported  Milieuschutz applies to the parcel
    ev  §172 BauGB designation, Bad Homburg, 2023-11-14 [c:9f2a1c]
    csq unit sale needs conversion consent; blocks the exit plan
    ho  rights -> location.demand (exit route)

N5  no-risk    supported  Lift certification current to 2029-03
    ev  TÜV Hessen cert 2024-03-11 [c:4b70de]

U1  unknown    unknown    Ground-contamination register entry not retrievable
    ev  Hessen Altlastenkataster: no public record for FlSt 214/3 [c:e1c9a0]
    csq price risk unquantified until the Kataster extract is obtained

## Handoffs
R2 -> location-demand-market: conversion consent gates the exit route
```

Why each part:

- **`VERDICT` line, mandatory, first.** Makes *"no risk, working fine for the given information"* a
  **single line** — literally what you asked for, and currently unsatisfiable. ~90 chars replaces
  hedging that occupies the 32.1% budget today.
- **`Coverage` ledger.** The mechanism, not the wording. Nothing today *forces* a clean statement, so
  none appears. A row per mandated facet makes absence-of-risk a required output — and makes an
  `asset-integrity`-style zero-search domain visible in the artifact, not only in the logs.
- **Row ids with a verdict-class prefix.** Replaces 313 chars/finding of handoff prose with a 2–3
  char referent; the `Handoffs` block costs ~60 chars per edge.
- **Two axes** — `verdict ∈ {no-risk, risk:low|med|high, blocked}` × `status ∈ {supported,
  inference, unknown, immaterial}`. The 38% unknown mass keeps its honest label without being
  silently recoded as risk.
- **`csq` omitted on `no-risk` rows** — the 19.1% consequence budget stops being paid for findings
  with no consequence.

### The density target

| | measured | target |
|---|---|---|
| words / domain | 3,580 | ≤2,500 |
| chars / finding | 1,967 | ~1,350 |
| **findings / 1,000 words** | **4.12** | **≥6.0** |

**Optimise findings-per-1,000-words, not length.** That is the operational definition of what you
asked for: facts per word up 46%, not words down 30%.

Two corrections to earlier framing of mine. The 56,163-word headline **double-counts** the
`.partial.md` snapshots — reader-facing total is 36,553 words, so the real overshoot against a
3,000-word norm is **1.19×**, not 19×. And **do not budget below ~2,500 words**: a 1,200–1,500 cap
would be a 60% cut with no evidence behind it, against your own instruction that quality must not be
compromised.

**Prerequisite.** Appended fragments are concatenated with no separator —
`"...tax conditions.## Authority — title and cadastral..."` — so `re.split(r'^## ', flags=re.M)`
finds 11 blocks where 118 exist, and the reviewer and synthesis agents read those files. A table
format will be malformed the same way. Fix the separator first.

---

## 4. Is the 8×5 fan-out affordable?

**As written: no.**

```
sessions   8 + 40 + 32-48 + 1 = 81-97
searches   unbudgeted; anchored on the measured 17.9/session → 545-865
search $   545-865 × $0.01725 = $9.4-14.9
total      $12-19 / property   (~95-140M raw tokens)   = 2.6-4.1x today
```

**But the session count is not the problem.** A model turn is $0.00407; forty extra sessions sharing
a byte-identical >1,024-token prefix cost about **$0.05** in cache writes. Five `task` calls in one
message run concurrently, and a lens can return a 59-char pointer to a 200,000-char brief it wrote
into shared state. **Fan-out is nearly free.**

The problem is that **search is unbudgeted and unbudgetable by the provider**: `recursion_limit` is
9,999 and inherited by subagents; `max_tool_calls` caps only *built-in* tools and `search_web` is a
custom `@tool`; there is no cap in `settings.py`. Effort=high produced 197 searches where effort=low
produced 17, from the same prompt. Multiply that by 40.

**Budgeted fan-out — the recommendation:**

```
sessions   8 coordinators + 40 lens + 8-16 verifiers + 1 synthesis = 57-65
budget     20 searches per DOMAIN, coordinator-allocated across 5 lenses, floor 2 each
           verifier spot-checks ≤2/domain  →  ≤176 total
search $   ≤176 × $0.01725 = $3.03
total      $4.0-5.5 / property   (~30-45M raw)
```

**Same money as today, for five perspectives, adversarial verification and a risk-first contract.**
The parallelism is paid for out of the $10/1k fee that budgeting recovers.

Three faithfulness notes from the research:

1. **Parallel lenses *are* STORM-shaped.** The paper runs N parallel perspective conversations with
   fresh retrieval per question. What STORM avoids is five *writers* — one article stage reads one
   shared URL-indexed reference table. So keep the fan-out; have lenses emit **evidence rows into the
   shared store**, not mini-reports.
2. STORM's shipped defaults are **3 perspectives × 3 turns × 3 queries × top-3**, not the paper's
   5×5. Three lenses is the reference implementation's own answer if five proves unaffordable.
3. **There is no published STORM or Co-STORM cost figure anywhere.** Do not write "STORM is proven
   efficient" in any document.

**Size per domain, not uniformly.** Two of eight domains consumed 61% of model tokens and 70% of
search tokens (Ground 68 searches, Energy 58); three ran ≤18 model calls; `asset-integrity` ran
**zero** searches and published 12 uncited findings. A flat 5×8 spends the same on both ends.

**Replace most verifiers with a join.** 63 of 183 logged citations (**34.4%**) render nowhere; 9 of
195 inline markers dangle. Both are deterministic checks, and `check_report.md` already runs one —
"14 checks · 13 passed · 1 failed", the failure being *"Every emitted citation marker resolves to
verified evidence"*. Keep 1–2 adversarial verifiers per domain for quote fidelity on tier-2/3
sources — that is judgement. The other 30–46 sessions catch what a join catches free.

**The risk nobody has written down.** The measured clarification pass **destroyed the prior pass's
evidence base**: Ground's initial session logged 29 citations and **zero** render in the published
report, after a session costing 4.77M tokens. The plan runs a self-review-and-revision step on all
eight domains — it replicates that destructive rewrite eight times. This needs a hard assertion, not
a hope.

---

## 5. Traps in deepagents 0.7.7

Established by constructed-graph probes, no API calls.

**Already handled by the built code:** `FilesystemMiddleware` is required scaffolding and `read_file`
is mandatory within it; replacing the base instance by name silently zeroes `_permissions`.

**Live or still to come:**

1. **Parent middleware does not propagate to subagents** — §1. Live now.
2. **A `task` result over 80,000 chars is evicted** and replaced by a ~1,617-char pointer;
   `task` is not in `TOOLS_EXCLUDED_FROM_EVICTION`. Either cap briefs or have each lens `write_file`
   and return a pointer.
3. **`response_format` on a subagent JSON-escapes the brief** (~2–3% inflation) and pushes toward
   that threshold. Plain markdown for prose; schema only for small objects.
4. **`ProviderStrategy` has no retry and never returns `None`** — it raises
   `StructuredOutputValidationError`. And `structured_response` is **silently absent** if the model
   emits any tool call on the final turn, so every schema-bearing step must end tool-call-free.
5. **Harness profiles are a process-global dict keyed by model spec, and registrations merge rather
   than replace.** All eight pipelines share one profile; per-pipeline behaviour must come from
   `create_deep_agent` arguments.
6. **Cache constraint.** Tool definitions, ordering and schemas must be byte-identical between
   requests for prefix hits, and there is a **~15 requests/min per key** limit. Keep the same tool
   list in the same order for all 40 lenses; shard `prompt_cache_key` per domain.
7. **Subagents cannot delegate** — no subagent receives `task`. The plan is one level, so fine, but
   it caps the design.

---

## 6. Implementation order

1. **`context_middleware` on all six subagent specs** (§1). Before any run.
2. **`"cache_write_tokens"`** added to the usage key tuple. Before quoting any cost.
3. **Fragment separator** fixed. Before any table format.
4. **Search budget** — ceiling 20/domain, floor 1/domain and 2/lens, enforced in
   `research_tools.py::_search`, allocated by the coordinator.
5. **Output contract** (§3) — verdict enum, coverage ledger, row ids, handoff edge list.
6. **`verbosity="low"` + `reasoning_effort`** in one commit across both settings modules.
7. **Deterministic citation join** reported, never gating; verifiers cut to 1–2 per domain.

## 7. One live domain before eight

Run **Ground, Physical Climate & Insurability** — the tail domain, 10.9M tokens and 68 searches. If
the budget holds there it holds everywhere.

| # | measurement | pass |
|---|---|---|
| 1 | search calls, total and per lens | ≤20 for the domain (baseline 68). The counter must be **observed firing** at least once. No lens at zero. |
| 2 | domain cost on the verified price sheet | ≤$0.57 (1/8 of today). Report dollars **and** raw tokens. |
| 3 | model-leg cache hit rate | ≥80% (baseline 90.6%) |
| 4 | **parameter readback, one call** | `response.text.verbosity` and `response.reasoning.*` present and equal to what was set; no 400. **Cheapest experiment available — it settles whether luna honours `text.verbosity` at all.** |
| 5 | report density | ≤2,500 words, ≥15 findings, **≥6.0 findings/1,000 words** (baseline 4.12), ≥1 explicit `no-risk`, coverage ledger complete |
| 6 | citation integrity | logged citations rendering **100%** (baseline 65.6%); inline markers resolving **100%** (baseline 95.4%) |
| 7 | **revision non-destructiveness** | post-review report retains **≥95%** of pre-review citation ids. Baseline for this domain: **0 of 29.** |
| 8 | brief handling | zero lens `task` results evicted |
| 9 | verifier value | the 2 verifiers find ≥1 defect the deterministic checks did not. If none, cut them. |
| 10 | **the A/B that decides the architecture** | same domain, same budget: (a) one session with five facet sections, (b) 1 coordinator + 5 lens sessions. **Fan-out passes only if it yields ≥20% more distinct cited sources or ≥1 additional material risk at ≤1.2× the cost.** |

Gate 10 matters because the five lenses **already existed as five facets inside one session** —
`five_questions.md` said verbatim *"Use these as five facets of one domain decision, not personas"*,
and the 118 fragment ids split practice 27 / authority 40 / economics 23 / comparables 11 /
challenge 16. The fair counter: the published artifact collapsed to 11 H2 headings run-wide, so the
facet structure was generated but did not survive into the deliverable. That is a real argument for
promoting facets to sessions — and gate 10 is the only thing that settles whether it buys research or
just costs money.

---

## 8. Open, and honestly so

- **Does luna honour `text.verbosity`?** Wired and verified in the payload; not enumerated on the
  model page. One call settles it.
- **Effort at medium** — never run. The 24.6× figure is 7.2× per published character and that run
  failed validation.
- **Intra-domain lens duplication** — the number that decides whether 40 lenses waste retrieval.
  Unmeasurable without running it. Cross-domain overlap is low (mean Jaccard 0.06, 197/197 distinct
  queries), and that is a **floor** for intra-domain, since the eight domains have disjoint mandates
  while five lenses share one.
- **Query cache returns zero hits on 197 unique queries.** One pair had token-set Jaccard 1.0 and
  still missed — lowercase, strip punctuation and sort tokens before hashing is free. Do **not** use
  a blind 0.85 semantic threshold: `Wassertiefe_Szenario2` vs `Szenario3` sits at 0.86 and must not
  collapse.
- **Retrieval waste, measured but unattacked:** 861 sources fetched → 163 indexed (18.9%) → 97
  distinct cited (11.3%), 47MB downloaded. A precision fix attacks the 74.2% without adding a
  session, and nobody has costed it.

# Layer 3 Plain-Research Redesign Plan (2026-08-31)

Scope: Layer 3 only. Layer 2 missions, the 8 domain boundaries, sequential execution, the source
store, checkpointing and the final synthesis call are unchanged. Baseline for all targets: run C04
(8,068,941 tokens, 196 model calls, 254 paid searches, 45 cited / 155 opened sources).

## Goal

Cut Layer 3 billed cost by ≥60% while holding or improving fact quality. "Good facts" is defined
measurably: every finding carries a source id + URL from an *opened* source (never a search
snippet), citation accuracy on a manual sample ≥ C04, contradictions preserved, and no drop in
property-linked risks found.

## The two measured cost levers

| Lever | Measured basis (C04) | Attack |
|---|---|---|
| A. Search implementation | 49.9% of all tokens are inside `search_web` provider calls (~16k tokens each; frontier model + reasoning per call) | Cheap search model + hard search budget |
| B. Agent structure | 5 lenses + verifier + coordinator = 94.7% of actor tokens; 96% of model-phase tokens are history replay; 228 overlapping cross-lens queries; 71% of opened sources never cited | One direct researcher per domain; replay discipline |

Prompt tuning alone is proven insufficient: C04 (prompt v2 + compaction) cut only 19% vs C02.

## Target architecture

```text
Layer 2 missions (unchanged)
        ↓
8 × domain researcher — ONE Deep Agent per domain, sequential
   tools: search_web, read_source (direct, no subagents)
   prompt: mission + anchor block
         + five-perspective checklist (sections, not agents)
         + evidence discipline + self-verification pass
   budgets: max 15 searches, max 12 opened sources per domain
        ↓
8 × domains/<name>/final.md
        ↓
deterministic post-run check (cited URL ∈ opened sources)
        ↓
1 × tool-free synthesis call (unchanged)
```

Removed from the default path: the 5 lens subagents, the citation-verifier clusters, the
coordinator wrapper, the compare-five-briefs stage, and the apply-verdicts stage. The verifier
survives as an optional `--verify` audit mode, sampled, off by default.

## Workstreams (in ship order)

### WS1 — Cheap search call (independent; ship and A/B first)

The search call keeps its shape (`responses.create` + `web_search` tool) but stops using the
frontier model with reasoning for what is a retrieval errand.

- `layer2/settings.py` / `layer3/settings.py`: add `SEARCH_MODEL_SPEC` (a mini-tier model),
  `SEARCH_REASONING_EFFORT = "minimal"`. Freeze both into `run.json` at `create_run` so runs stay
  reproducible.
- `providers/openai_search.py`: use the search model + minimal effort; keep
  `search_context_size`/`verbosity` at `low` and `store=False`.
- `research_tools.py::_search`: normalize the cache key (casefold, collapse whitespace, strip
  punctuation) — C04 paid 6 exact-duplicate searches the byte-level cache missed.
- Expected effect: search-phase tokens similar or lower, billed search cost cut ~80–90%
  (mini-tier per-token price), i.e. roughly 40–45% off the total Layer 3 bill on its own.
- Risk: weaker hit quality. Mitigation: A/B one domain re-run before WS2 lands; the searcher only
  returns candidate URLs — evidence still comes from `read_source`, so quality risk is bounded.

### WS2 — One direct researcher per domain (the core change)

- `contracts.py`: add `RESEARCHER_NAME = "domain-researcher"`; keep `LENS_NAMES`/`VERIFIER_NAME`
  only where the audit mode needs them.
- New `prompts/researcher.md`: merge `shared_rules.md` + the five lens mandates as a **conditional
  checklist** (operational exposure, applicable regulation, nearby developments, value
  transmission, external/geopolitical dependency — investigate each only where the mission makes
  it material) + the evidence rules now in `verifier.md` (primary sources first, quote fidelity,
  claim-vs-inference separation).
- Rewrite `SKILL.md` procedure: anchor block → plan queries against the checklist → search / read
  / **distill immediately** loop within budget → draft findings (unchanged linkage chain and
  one-root-cause rule) → self-verification pass (re-check every quote and citation against
  already-opened source text; a claim supported only by a snippet is downgraded or re-read) →
  final report. Report format section stays as-is.
- `llm.py`: `create_domain_researcher_harness` = `create_deep_agent` with
  `tools=make_research_tools(RESEARCHER_NAME)`, `subagents=[]`, and the eviction + summarization
  middleware **on the main agent** (today only subagents get compaction; the researcher is now the
  looping context).
- `runner.py`: swap the coordinator harness for the researcher harness; loop unchanged.
- `pipeline/create_run.py`: `SCHEMA_VERSION` 7 → 8, `HARNESS_NAME` →
  `"domain_plain_research_direct_output"`, `context_management.applies_to` →
  `"domain_researcher"`. Old runs keep replaying under schema 7; no migration.
- `prompts.py`: add `researcher_system_prompt`; keep `verifier_system_prompt` for audit mode;
  delete lens plumbing.
- Expected effect: per domain, ~24.5 model calls (17 lens + 4.6 verifier + 3 coordinator) drop to
  ~10–12, and one history replays instead of seven.

### WS3 — Hard budgets, enforced server-side (the C03 guard)

C03 proved the loops expand to fill whatever the settings allow (high settings: 13.49× tokens on
an identical prompt). Budgets must live in the tool layer, not the prompt.

- `research_tools.py`: per-domain counters (persisted next to the query log so resume is safe).
  Over budget, `search_web` returns "Search budget exhausted — synthesize from already-opened
  sources" instead of searching; same pattern for `read_source`. Budget hits are logged via
  `record_event`.
- `settings.py` → `run.json`: `SEARCH_BUDGET_PER_DOMAIN = 15`, `READ_BUDGET_PER_DOMAIN = 12`
  (C04 spent ~30 searches and ~19 opens per domain and never cited 71% of opens; the budget is
  sized above what the final reports actually used).

### WS4 — Replay discipline for the merged agent

96% of C04 model-phase tokens were input replay. The merged agent's history is longer than any
single lens's, so without this WS2 gives back part of its savings.

- Tighten the run-frozen policy for the researcher: `eviction_trigger_tokens` 150k → 100k,
  `eviction_keep_tool_results` 6 → 4 (eviction is lossless — bodies re-serve from
  `sources/text/` on demand).
- `researcher.md` rule: after each `read_source`, write the extracted facts (with source id)
  into the running notes *before* the next tool call, so evicting the raw body costs nothing.
- Summarization settings unchanged.

### WS5 — Fact-quality guards replacing the verifier

- **Deterministic citation check** (new step in `pipeline/run_checks.py`): every URL cited in a
  domain final must appear in `sources/index.jsonl` (i.e., was actually opened). A citation to a
  never-opened URL is exactly the snippet-citation failure the verifier existed to catch — this
  check finds it with zero tokens and fails the domain to `retry_failed`.
- **Self-verification pass** inside the researcher prompt (WS2) — quotes re-checked against
  opened text before finalizing.
- **Optional audit mode**: `--verify` on the CLI registers the citation-verifier subagent and
  instructs one sampled verification task per domain (all High-impact findings), not per-claim
  clusters. Default off.

### WS6 — Instrumentation and the C05 comparison

- `usage.py::summarize_usage`: add per-phase token split (model vs web_search) and an estimated
  billed-cost field using cached-input discounting — raw token totals mis-rank cache-heavy runs
  (C03: 50M of 68M model input was cache-served).
- Run **C05** from the same Layer 2 source (`L2_20260821_113445_4a51`), low settings, and record
  it in `L3_COMPARISON_INDEX.md` per its tracking rule.

## Acceptance criteria (C05 vs C04)

| Metric | C04 | C05 target |
|---|---:|---|
| Total tokens | 8.07M | ≤ 4.0M (−50%) |
| Estimated billed cost | baseline | ≤ 40% of C04 (−60%; WS1 discount included) |
| Paid calls (model + search) | 450 | ≤ 220 |
| Property-linked risks found | baseline | ≥ 90% of C04's, no lost High-impact finding |
| Unique cited sources | 45 | ≥ 40 |
| Opened-vs-cited ratio | 29% | ≥ 50% |
| Citation accuracy (manual 20-claim sample) | baseline | ≥ C04 |
| Deterministic citation check | n/a | 0 never-opened citations |

If C05 misses the quality bar, the fallback order is: raise budgets → enable sampled audit mode →
only then reconsider a second research pass. Do not reintroduce lens agents.

## Explicitly out of scope

Layer 2; parallel domain execution (reduces wall-clock, not cost, and raises rate-limit risk);
changing the final report format; changing the frontier model for research reasoning.

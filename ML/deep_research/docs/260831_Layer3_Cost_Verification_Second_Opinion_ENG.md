# Layer 3 Cost Verification — Second Opinion (2026-08-31)

Independent verification of the external (Codex) analysis "remove the five lenses, use one direct
research agent per domain". All numbers below were recomputed from the raw `usage.jsonl`,
`sources/index.jsonl`, `sources/queries.jsonl` and the final domain reports of runs C01–C04.
No code was changed. Layer 2 was not inspected or modified.

## Verdict

**The Codex report is numerically correct and directionally right.** Every headline figure
reproduces exactly from the raw run logs. The recommended plain-research architecture (one direct
domain agent + one synthesis call) is sound and matches the branch name `plain_research`.

**But it misses the single largest cost item:** across C02, C03 and C04, **~50% of all Layer 3
tokens are consumed inside the `search_web` provider calls themselves**, not in the agent loops.
Removing lenses reduces the *number* of searches; it does not touch the *cost per search*. Both
levers are needed to reach the claimed 60–75% saving.

## 1. Claim-by-claim verification

| Codex claim | Verified | Evidence |
|---|---|---|
| SKILL.md mandates 5 lens tasks per domain | ✅ | `layer3/SKILL.md:29` |
| llm.py builds six looping subagents (5 lenses + verifier) | ✅ | `layer3/llm.py:66` |
| Each `search_web` is a paid Responses call (same model, with reasoning) | ✅ | `layer3/providers/openai_search.py:141` |
| C04 split: lenses 82.6% / verifier 12.1% / coordinator 5.0% / synthesis 0.4% | ✅ | Recomputed from `usage.jsonl`, exact match incl. 6,665,951 / 972,491 / 400,091 / 30,408 tokens |
| C04 totals: 196 model calls, 254 web calls, 8,068,941 tokens | ✅ | Exact match |
| ~56 paid calls per domain | ✅ | (196+254)/8 = 56.25 |
| 40 mandatory lens assignments | ✅ | 5 lenses × 8 domains |
| 155 unique opened URLs, 45 unique URLs cited in domain finals | ✅ | `sources/index.jsonl`: 155 unique normalized URLs; exactly 45 unique URLs across `domains/**/*.md` |
| C03 vs C02 (identical prompts): 13.49× tokens, 4.56× searches, 2.64× model calls | ✅ | 134,286,382/9,956,758 = 13.49; 1481/325 = 4.56; 525/199 = 2.64 |
| Coordinator adds ~3 model calls per domain | ✅ | 24/8 = 3 |
| Verifier uses the same model and may re-search/re-open sources | ✅ | `layer3/prompts/verifier.md` ("Open every cited source … Search for an original source"); single `MODEL_SPEC` for all agents |
| Lenses issue semantically similar queries | ✅ | 228 same-domain cross-lens query pairs with ≥50% significant-word overlap (of 260 queries); only 6 exact duplicates (absorbed by the query cache) |
| Domains run sequentially | ✅ | `layer3/runner.py:195` |

Additional waste confirmation: **71% of opened sources (110 of 155) never appear in any final
domain report.** Every opened source's full text also sits in a looping agent's history and is
re-sent on each subsequent model call.

## 2. What the Codex report misses

### 2.1 The search implementation is half the bill (biggest single lever)

`search_web` is implemented as a full `responses.create` call on the frontier model with a
`web_search` tool and reasoning enabled (`openai_search.py:141`). Per-phase token split, recomputed:

| Run | Model-phase tokens | Search-phase tokens | Search share | Avg tokens/search |
|---|---:|---:|---:|---:|
| C02 (low) | 5,037,523 | 4,919,235 | 49.4% | 15,136 |
| C03 (high) | 69,137,817 | 65,148,565 | 48.5% | 43,990 |
| C04 (low) | 4,042,442 | 4,026,499 | 49.9% | 15,853 |

Codex's per-actor table folds these tokens into the lens shares, so the report reads as "the lens
agents are expensive" when half the expense is the search provider design. Consequences:

- Even after merging to one agent per domain, every remaining search still costs ~16k tokens (low)
  to ~44k tokens (high). A merged agent doing 15 searches/domain still burns ~1.9M tokens on
  search alone across 8 domains.
- Swapping the search call to a cheap model or a dedicated search endpoint is an **independent,
  architecture-neutral lever worth up to ~40–50% of total Layer 3 tokens** — it survives any
  redesign and can ship before it.
- The C03 blowup was equally a search blowup: high `search_context_size` tripled per-search cost
  *and* the loops issued 4.56× more searches; the search phase alone grew 13.2×.

### 2.2 Model-phase cost is context replay, not generation

In C04's model phase: 3,879,418 input tokens vs 163,024 output tokens — **96% of model-phase
tokens are history replay** (44% of input was cache-served). The cost driver is how much source
text sits in a looping context and how often it is re-sent. Two implications for the redesign:

- A single merged domain agent accumulates a *longer* history than any individual lens. Without
  discipline, part of the lens savings is given back as replay. The C04 compaction barely engaged
  (10 compacted source results, 0 summarization calls, 0 calls over the 200k soft target), so
  existing eviction settings will not protect the merged agent by default — tighten
  `EVICTION_TRIGGER_TOKENS` / keep-counts for the new agent shape.
- `read_source` itself is free (direct HTTP fetch, no API call). Its cost is entirely the retained
  text being replayed. A "distill after reading" habit (agent extracts what it needs, eviction
  drops the raw text) is worth more than reducing the number of reads.

### 2.3 Token counts overstate cost on cache-heavy runs

Cached input tokens are billed at a steep discount. C03 had 49.9M of 68.3M model-phase input
tokens cache-served; its *cost* multiple vs C02 is therefore lower than the 13.49× token multiple.
The comparison methodology should track estimated cost (uncached input + discounted cached input +
output) alongside raw tokens, or C05-vs-C04 conclusions may mis-rank options.

### 2.4 The 60–75% saving needs both levers

Rough per-domain arithmetic from C04 (≈1.0M tokens/domain): merging 5 lenses + verifier +
coordinator into one agent plausibly halves searches (~30 → ~15/domain) and cuts model calls
(~24.5 → ~12/domain), but the merged agent's longer history raises average input per call. The
merge alone lands around **40–60%** savings. The 60–75% target is realistic only when combined
with a cheaper search implementation and/or an explicit search budget per domain. This does not
change the recommendation — it changes what must ship together.

## 3. Agreement with the redesign, with three amendments

The keep/remove table in the Codex report is agreed, including: keep the five perspectives as a
prompt checklist, keep the 8 domain boundaries, keep the synthesis call, keep source cache /
checkpointing / compaction, keep sequential execution initially, remove the lens agents, the
coordinator wrapper, the compare-briefs stage, and the default per-claim verifier. Amendments:

1. **Add: replace or downgrade the search provider call.** Route `search_web` to a cheap model or
   a dedicated search API; keep `search_context_size`/`verbosity` at `low`. This is the largest
   single saving and is independent of the agent merge.
2. **Add: hard search/read budget per domain** (e.g. max 15 searches, max 12 opened sources),
   logged when hit. C03 proves the loops expand to fill whatever the settings allow; a budget cap
   is the only structural guard against a repeat.
3. **Keep a self-verification pass inside the domain agent's prompt** (re-check quotes against
   already-opened sources before finalizing; flag claims relying on snippets). The skeptic lens
   and per-claim verifier were the two mechanisms countering confirmation bias and citation drift;
   removing both without a prompt-level substitute risks a measurable citation-accuracy
   regression. The proposed C05-vs-C04 manual citation sample is the right test for whether this
   substitute suffices.

## 4. C05 evaluation additions

The Codex comparison metrics (risks found, external factors, unique sources, citation correctness
sample, generic findings, calls/tokens/runtime/cost) are right. Add:

- **Search-phase vs model-phase token split** — to attribute savings to the correct lever.
- **Estimated billed cost** using cached-token discounting, not raw token totals.
- **Opened-vs-cited source ratio** — C04 wasted 71% of opened sources; the merged agent should
  materially improve this.
- Per the run-tracking rule in `L3_COMPARISON_INDEX.md`, assign the next complete run `C05` and
  record its frozen settings there.

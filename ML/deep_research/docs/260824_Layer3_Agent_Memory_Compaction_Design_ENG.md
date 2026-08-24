# Layer 3 agent memory & compaction — station-by-station design

Date: 2026-08-24 · Status: **implemented** (see §6) · Evidence: measured from run
`L3_20260821_182919_b675` (`usage.jsonl`, 2,033 records) and verified against deepagents 0.7.7 /
langchain 1.3.15.

---

## 1. Baseline before this implementation (measured, not assumed)

**No memory management was active in the measured baseline.** Three facts establish this:

1. `configure_harness()` (`layer2/harness.py:47`) excludes `SummarizationMiddleware` and applies to
   **both** layers — Layer 3 imports the same harness profile.
2. `SUMMARIZATION_TRIGGER_TOKENS = 180_000` / `SUMMARIZATION_KEEP_TOKENS = 100_000`
   (`layer2/settings.py:15-16`) were **imported by nothing**. The comment "Layer 3 still uses these
   to compact its long research conversations" was false — dead configuration, since deleted.
3. deepagents' built-in tool-result offloading (>20k tokens → `/large_tool_results/`) needs a
   filesystem backend. `_NoFilesystemMiddleware` (`layer3/llm.py:34`) removes it for every agent,
   so there is no offloading target. Every `read_source` dump stays verbatim in the lens history
   forever and is re-sent on every subsequent turn.

The only working mechanism is **context isolation**: a lens keeps its million-token working
conversation to itself and returns one brief; the coordinator never sees the search history.

### Measured context growth per actor (one run, 8 domains)

| Actor | Model calls | Peak input/call | Avg input/call | Sum tokens | Share |
|---|---:|---:|---:|---:|---:|
| historian | 61 | **743,054** | 258,760 | 15.87M | 23.0% |
| skeptic | 47 | 614,672 | 177,328 | 8.41M | 12.2% |
| academic | 58 | 522,813 | 198,098 | 11.58M | 16.8% |
| practitioner | 64 | 397,456 | 156,815 | 10.12M | 14.7% |
| economist | 51 | 388,308 | 141,245 | 7.28M | 10.5% |
| citation-verifier | 219 | 279,488 | 66,672 | 14.92M | 21.6% |
| domain-storm-coordinator | 24 | 63,230 | 31,593 | 0.89M | 1.3% |
| property-synthesis | 1 | 47,657 | 47,657 | 0.06M | 0.1% |

- **Lenses + verifier = 98.7% of all model tokens.** Memory design matters at exactly two
  stations; everywhere else it is unnecessary or harmful.
- 73.1% of the 68.3M input tokens were cached prefix reads — caching absorbs part of the
  quadratic re-send, but cached tokens are not free, and cache hits vanish on any provider restart.
- `MODEL_INPUT_TOKEN_LIMIT = 200_000` was stale metadata by 5×. The window is now read rather than
  assumed: `init_chat_model("openai:gpt-5.6-luna").profile` reports
  **`max_input_tokens = 1,050,000`** (and `max_output_tokens = 128,000`). The historian therefore
  finished at **70.8% of the real window** on a mid-sized fact sheet. A heavier property overflows,
  the lens call throws, the whole domain fails, and `--retry-failed` restarts it from turn zero on
  a fresh thread — re-billing all five lenses.

### What the lenses were actually carrying

From the same run's source store, the payload eviction targets:

| | Stored source texts |
|---|---:|
| Files | 625 |
| Total | 15.1 MB ≈ **3.77M tokens** |
| Median | 8.1 KB ≈ 2k tokens |
| p90 | 26.5 KB ≈ 6.6k tokens |
| **Max** | **1.22 MB ≈ 305k tokens in a single source** |

The median source is small; the tail is what kills a context. One stored source is larger than most
models' entire window.

---

## 2. The train map

```
 S0 ──────► S1 ──────► S2 ×5 ─────► S3 ──────► S4 ×4-6 ───► S5 ──────► S6
 load       coordinator LENS LOOP    coordinator VERIFIER     coordinator SYNTHESIS
 missions   fan-out     search+read  digest+draft LOOP        final       single call
 (no LLM)   (1 turn)    (loop, web)  (1-2 turns)  (loop, web) report      (1 turn)
                        ▲ MEMORY     ✗ never      ▲ MEMORY    (1 turn)    ✗ never
                          NEEDED       compact      NEEDED                  compact
```

| Station | Input | LLM output | Loop? | Peak seen | Memory? | Why |
|---|---|---|---|---:|---|---|
| **S0** Mission load | `mission_md/*.md` + planner | — (no LLM) | no | — | **No** | Pure file I/O |
| **S1** Coordinator fan-out | SKILL + domain message (~15k) | Anchor block + 5 `task` calls | no | 63k | **No** | 3 turns per domain, small |
| **S2** Lens research ×5 | shared_rules + lens prompt + task (~2k) | Queries, reads, final brief | **yes** — search/read until done | **743k** | **YES** | Unbounded growth: each `read_source` result (10–100k+) stays forever |
| **S3** Coordinator digest + draft | 5 briefs land in coordinator history | Draft findings, verify clusters | no | 63k | **No — actively harmful** | The history *is* the state: briefs, conflicts, draft. Summarizing here loses exactly the specifics the synthesis-fidelity work protects |
| **S4** Verifier ×4–6 | shared_rules + verifier + cluster claims | Verdicts per claim | **yes** — reads sources | 279k | **Yes (lighter)** | Same shape as S2, shorter life |
| **S5** Coordinator final report | Verifier verdicts in history | Corrected domain Markdown | no | 63k | **No** | One closing turn |
| **S6** Synthesis | 8 domain reports in one message (~48k) | Risk landscape Markdown | no | 48k | **No — never** | Single stateless call. Any compaction = the information loss already fought once. If 8 reports ever exceed the window, the answer is map-reduce (pairwise reconcile), not middleware |
| Layer 2 chunk router | one 50k chunk | one JSON object | no | ~55k | **No** | One fresh invocation per chunk — nothing accumulates. (This confirms the intuition: *loop + web tools → memory; single call → none.*) |
| Cross-run store (`/memories/`) | — | — | — | — | **No — rejected** | Every finding must trace to *this run's* source store. Prior-run "knowledge" contaminates evidence provenance and is untraceable in the citation chain |

---

## 3. Design for S2/S4: offload first (lossless), summarize second (lossy)

Two mechanisms, applied in order. Both live only in the lens and verifier subagent specs
(`layer3/llm.py::_subagents`) — the coordinator and synthesizer keep no memory middleware.

### 3.1 Mechanism 1 — evidence eviction (lossless, no extra LLM call)

The generic deepagents offloading writes big tool results to a virtual filesystem and points the
agent at `read_file`. CDI does not need that detour, because **the system already has a better
archive**: every fetched source is persisted in `sources/raw/` + `sources/text/`, and
`read_source` serves repeat calls **from that disk cache with no network fetch and no provider
cost** (`research_tools.py::_read` checks `record_for_url` first).

So eviction is a pointer swap — and **no custom middleware is needed**, because
`ClearToolUsesEdit` + `ContextEditingMiddleware`
(`langchain.agents.middleware`, mirroring Anthropic's `clear_tool_uses_20250919`) already does
exactly this and is configured, not written:

| Requirement | Configuration |
|---|---|
| Clear only old `read_source` bodies | `exclude_tools=("search_web",)` |
| Never touch the most recent K | `keep=6` |
| Pointer text naming the recovery path | `placeholder=...` |
| Coarse batches, to spare the prompt cache | `clear_at_least` |
| Idempotent | marks `response_metadata.context_editing.cleared` |
| Nothing permanently lost | edits a `deepcopy` and calls `request.override(...)`, so **`state["messages"]` and the checkpoint keep the full history** |

The URL survives for free: `clear_tool_inputs` defaults to `False`, so the AI message's
`read_source(url=...)` call stays intact beside the cleared result. The model can always see what
to re-read, and a static placeholder suffices.

Properties: zero information loss, zero summarizer cost, the agent re-pulls exactly the sources it
still needs.

**Known limitation.** `keep` counts tool *results*, not their size. A single oversized source inside
the keep window — the run above held one of ~305k tokens — is not evictable. That case is what the
summarizer backstop and the `ContextOverflowError` path exist for.

### 3.2 Mechanism 2 — early rolling `SummarizationMiddleware`

After source eviction, older reasoning is summarized before a lens approaches the model window:

- **Correction to an earlier draft of this section.** It claimed `gpt-5.6-luna` has no model
  profile, so the middleware would fall back to 170k tokens / keep 6 messages and fire far too
  early. That is wrong: the profile exists and reports `max_input_tokens = 1,050,000`, so
  `compute_summarization_defaults` returns `trigger=("fraction", 0.85)` ≈ 892k. The fallback never
  applies. The practical consequence is the opposite of the warning — with defaults the summarizer
  would almost never fire, so **eviction is the load-bearing mechanism and the summarizer is a
  backstop**.
- The operating target is 200k tokens. Normal source eviction starts at 150k and keeps six recent
  tool results. If the edited request still exceeds 170k, an emergency pass clears every remaining
  `read_source` body while preserving its URL and source id; `search_web` remains exempt.
- Summarization then triggers at an absolute 170k and retains approximately 70k recent tokens.
  `trim_tokens_to_summarize=None` is explicit, so the complete older portion reaches the summary
  model instead of LangChain's default final 4k-token slice.
- The reason to enable it at all beyond thresholds: with the middleware active a
  `ContextOverflowError` forces summarize-and-retry **instead of failing the domain** — closing the
  failure mode where `--retry-failed` re-bills the entire domain from turn zero.
- Deep Agents still archives earlier dialogue for audit. CDI replaces its wrapper text so it does
  not advertise that inaccessible path as a recovery tool; evidence recovery uses the retained
  URL and source id with `read_source`.

### 3.3 The summary contract (what must survive compaction)

The summary prompt is a fidelity contract, same philosophy as `synthesis.md` — compress by
removing narration, never specifics:

1. The anchor block verbatim (address, district, parcel, occupier, systems, suppliers).
2. Every confirmed property fact, each with source id + URL.
3. Findings so far as full causal chains (new evidence → … → value transmission → horizon).
4. Contradictions and unknowns, verbatim.
5. **Every query already run, verbatim** — a re-run query is served free from
   `sources/query_cache/`, so preserving query strings converts memory loss into cache hits.
6. Source ids already read (so the lens re-reads rather than re-searches).
7. Open questions and the current procedure step.

### 3.4 Why "no context loss" is defensible here

Active context necessarily thins — 1M tokens cannot stay inside one prompt. But nothing becomes
unrecoverable, because durability already lives outside the conversation:

| Layer | Where | Recovery path |
|---|---|---|
| Raw evidence | `sources/raw/`, `sources/text/` | `read_source(url)` — local, free |
| Search results | `sources/query_cache/` | re-issue the same query — local, free |
| Query log | `sources/queries.jsonl` | audit, dedup |
| Full message history | `checkpoints.sqlite3` | resume/inspection |
| Compacted state | in-context summary | carries pointers to all of the above |

### 3.5 Cost interaction with prompt caching (the honest trade-off)

Eviction and summarization **rewrite history and break the prefix cache** (73.1% hit rate today).
Rewriting every turn would trade cheap cached tokens for expensive fresh ones. Therefore compact
**coarsely**: evict in large batches at a high trigger, so long cached runs persist between rare
rewrites. Net effect still strongly positive — the quadratic term disappears: historian-shaped
lenses drop from ~15.9M to an estimated 5–7M tokens, and the run's dominant stations (98.7% of
tokens) shrink roughly by half.

---

## 4. What NOT to build, and why

| Rejected | Reason |
|---|---|
| Summarization on the coordinator (S3/S5) | Peak 63k in a 1.05M window; its history is the merge state — compacting it is where specifics die |
| Any compaction into synthesis (S6) | Single call, 48k input. The 86%-of-euro-amounts loss came from *model-side* abstraction; adding machine-side compression compounds it |
| `StoreBackend` `/memories/` cross-run memory | Breaks evidence provenance; a due-diligence finding may only rest on this run's stored sources |
| Filesystem tools for lenses (generic offloading route) | `read_source` + the source store already are the retrieval tool; exposing `read_file`/`ls` adds surface without adding capability |
| Trimming/truncating model *output* | Out of scope by standing rule: no machine grading, normalization, or repair of what the model says |
| Layer 2 memory middleware | Stateless single-turn calls; nothing to compact |

---

## 5. The one framework obstacle

`configure_harness()` excludes `SummarizationMiddleware` **by name**, and `create_deep_agent`
re-applies `excluded_middleware` to each subagent stack **after** merging caller middleware
(`deepagents/graph.py:693-709`). So passing a plain summarizer instance is dropped in silence.

The public `SummarizationMiddleware` alias reports the shared name only for its exact implementation;
subclasses fall back to `type(self).__name__`. A thin CDI subclass therefore survives the filter,
which means:

- the framework's own default-configured summarizer stays off **everywhere**;
- the coordinator and synthesizer are untouched;
- `excluded_middleware` is unchanged, while the harness test now distinguishes implicit from
  explicitly configured CDI summarization.

## 6. As implemented

| File | Change |
|---|---|
| `layer3/memory.py` | **new** — `CdiResearchSummarization` subclass, `evidence_eviction()`, `research_summarization()`, `CDI_SUMMARY_PROMPT` (§3.3 contract) |
| `layer3/settings.py` | new-run defaults: soft target 200k, normal eviction 150k / keep 6, emergency eviction 170k / keep 0, summary 170k / keep 70k |
| `layer3/llm.py` | `_subagents(run_dir, *, model=None, backend=None)`; per-spec middleware order `[_NoFilesystemMiddleware, ContextEditingMiddleware, CdiResearchSummarization]`; `_model_and_backend()` helper so a graph and its subagents share one model |
| `layer2/settings.py` | dead `SUMMARIZATION_*` deleted; `MODEL_INPUT_TOKEN_LIMIT` 200_000 → 1_050_000 |
| `layer3/pipeline/create_run.py` | versioned `context_management` snapshot in `run.json`; runtime reads this snapshot and versionless runs stay unchanged |
| `tests/test_layer3_memory*.py` | framework, eviction, early-summary, frozen-policy, legacy and cache tests |

Middleware order matters: `wrap_model_call` composes first-as-outermost, so eviction runs before
the summarizer and the summarizer counts tokens on already-evicted messages — cheap-and-lossless
ahead of expensive-and-lossy.

### Verified offline

- Offline tests cover the complete repository plus the early-compaction policy without a live API call.
- The load-bearing property is pinned by driving the *real* filter: given a stack of
  `[framework summarizer, eviction, CdiResearchSummarization]` and the run's own harness profile,
  `_apply_excluded_middleware` returns `["ContextEditingMiddleware", "CdiResearchSummarization"]`.
- Eviction is proven on a synthetic 24-read history and one 400k-token recent source: old bodies
  clear first, emergency eviction handles the oversized keep-window source, `search_web` remains,
  URLs and source ids survive, and a second pass is a no-op.
- The summarizer receives unique markers from both ends of a greater-than-4k old portion, pinning
  the removal of the framework's hidden 4k trim.
- Coordinator and synthesizer captured at the `create_deep_agent` boundary carry
  `["FilesystemMiddleware"]` only.
- Model profile asserted at 1,050,000, so a provider change that shrinks the window fails a test
  rather than overflowing at runtime.

### Not yet verified — needs a live run

Peak-context reduction and report quality can only be measured against real traffic. One domain,
compared to `L3_20260821_182919_b675/usage.jsonl`: (a) peak lens input drops from ~400–740k into
the ~150–200k band; (b) report structure and source links unchanged; (c) an evicted URL is re-read
and served from the store with no new `sources/index.jsonl` entry; (d) the run still resumes, with
`LANGGRAPH_STRICT_MSGPACK=true` set at `runner.py:37`.

**Expected result:** peak lens context ~743k → ~150–200k, overflow becoming recoverable rather than
fatal, lens + verifier spend roughly halved, and zero loss of recoverable evidence — the archive was
never the conversation; it was always the source store and the checkpoints.

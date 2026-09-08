# Layer 3 Cost and Context Baseline

Status: **describes the implemented pipeline and its measured operating costs** · Consolidated 08 September 2026 from the Layer 3 cost verification and plain-research redesign plan of 31 August 2026, the agent-memory and compaction design of 24 August 2026, and the eight-domain architecture ticket write-up. Historical run comparisons are labelled as such.

Why the current Layer 3 looks the way it does, what it costs, which parts of the redesign shipped and which did not.

---

## 1 · What runs today

Data Intelligence produces a property fact sheet. Layer 2 routes its facts into domain buckets. Layer 3 researches each domain and synthesizes them. Layer 4 adds an external-influence pass over the Layer 3 reports.

Layer 3 does **not** create eight simultaneous subagents. It uses **one reusable direct researcher, invoked sequentially across the domain assignments**, then one tool-free synthesis call. Each researcher sees only `search_web` and `read_source`; the synthesis call has no tools.

### The eight baseline research domains

1. **Asset Integrity, Systems & Operational Resilience** — structure, envelope, mechanical and electrical systems, utilities, maintenance, defects, capacity, resilience and operational dependencies.
2. **Occupier, Lease, Income & Counterparty Economics** — occupiers, leases, rent, indexation, service charges, arrears, obligations, income continuity and counterparty strength.
3. **Rights, Public Law & Ownership Governance** — ownership, title, property rights, permits, planning, lawful use, governance restrictions, regulatory duties and property taxes.
4. **Ground, Physical Climate & Insurability** — ground conditions, contamination, flood, storm, heat, fire, water, physical climate exposure, vulnerability and insurability.
5. **Energy, Carbon & Transition** — consumption, fuels, certificates, emissions, benchmarks, transition requirements, compliance dates and their cost or value effects.
6. **Location, Demand, Market, Valuation & Exit** — location, transport, amenities, demographics, employment, regional economy, supply and demand, vacancy, rents, yields, valuation, liquidity and exit risk.
7. **Finance, Debt & Macro Transmission** — debt, rates, maturity, covenants, leverage, liquidity, refinancing, inflation, credit, foreign exchange and property-specific macro transmission.
8. **External Dependencies, Geopolitics, Trade & Supply Chains** — energy supply, equipment, materials, labour, vendors, technology, commodities, countries, transport routes, sanctions, geopolitical events, cyber threats and supply-chain continuity.

The authoritative roster lives in the Layer 2 configuration, not in this document. Under the proposed target architecture this baseline becomes a plugin default that a reviewed catalogue may extend.

**What the eight-domain shape achieved:** clear ownership per domain, separation of property facts from internal conditions and external influences, domain-specific rather than overlapping research, a traceable handoff across layers, individual outputs before cross-domain synthesis, and resumable independently stored stages.

---

## 2 · The two measured cost levers

Verified by recomputing every figure from the raw `usage.jsonl`, `sources/index.jsonl`, `sources/queries.jsonl` and final reports of the C01–C04 runs (**historical**, pre-redesign, five lenses plus verifier plus coordinator).

### Lever A · The search implementation is about half the bill

`search_web` is implemented as a full `responses.create` call on the frontier model with a `web_search` tool and reasoning enabled. Per-phase token split:

| Historical run | Model-phase tokens | Search-phase tokens | Search share | Avg tokens/search |
| --- | ---: | ---: | ---: | ---: |
| C02 (low settings) | 5,037,523 | 4,919,235 | 49.4% | 15,136 |
| C03 (high settings) | 69,137,817 | 65,148,565 | 48.5% | 43,990 |
| C04 (low settings) | 4,042,442 | 4,026,499 | 49.9% | 15,853 |

Per-actor tables fold these tokens into the agent shares, so a naive reading blames the research agents when half the expense is the search-provider design. Consequences:

- Even with one agent per domain, every remaining search still costs roughly 16k tokens at low settings and up to 44k at high settings.
- Routing the search call to a cheaper model or a dedicated search endpoint is an **independent, architecture-neutral lever** worth a large share of Layer 3 tokens. It survives any redesign and can ship before one.
- The C03 blow-up was equally a search blow-up: a higher search context size tripled per-search cost while the loops issued 4.56× more searches, so the search phase alone grew 13.2×.

**Still true after the redesign.** In the run pair of 02 September 2026 the search phase was **39.1% of Layer 3 tokens (270 calls, 31,575 tokens each)** and **28.8% of Layer 4 tokens (105 calls, 35,884 tokens each)**, with reasoning effort frozen at `high`. The lever remains open.

### Lever B · Model-phase cost is context replay, not generation

In C04's model phase: 3,879,418 input tokens against 163,024 output tokens — **96% of model-phase tokens were history replay**, 44% of that cache-served. Implications:

- A single merged domain agent accumulates a longer history than any individual lens did. Without replay discipline, part of the merge saving is given back.
- `read_source` itself costs nothing at the provider (a direct HTTP fetch). Its cost is entirely the retained text being replayed. A "distil immediately after reading" habit is worth more than reducing the number of reads.
- **Cached input is billed at a steep discount,** so raw token totals overstate cost on cache-heavy runs. Track estimated cost (uncached input, discounted cached input, output) alongside tokens, or run comparisons will mis-rank options.

Also confirmed historically: **71% of opened sources (110 of 155) never appeared in any final domain report**, while every opened source's full text sat in a looping agent's history and was re-sent on each subsequent call.

---

## 3 · The redesign: what shipped and what did not

The plain-research redesign (31 August 2026) aimed to cut billed cost by at least 60% while holding fact quality, defined measurably: every finding carries a source id and URL from an *opened* source, citation accuracy on a manual sample at least as good as the baseline, contradictions preserved, and no drop in property-linked risks found. Prompt tuning alone had proven insufficient — C04, with a revised prompt and compaction, cut only 19% against C02.

| Workstream | Intent | Status as of 08 September 2026 |
| --- | --- | --- |
| **WS1 · Cheap search call** | Route `search_web` to a mini-tier model at minimal reasoning; normalize the cache key | **Not implemented.** The provider still uses the frontier model with the run's reasoning effort. Cache keys are whitespace-normalized only. |
| **WS2 · One direct researcher per domain** | Replace five lenses, the verifier and the coordinator with one looping researcher; move eviction and summarization onto the main agent; schema 8; harness `domain_plain_research_direct_output` | **Implemented.** Lens, shared-rules and verifier prompts were deleted; the five perspectives survive as a conditional checklist inside the skill. |
| **WS3 · Hard search and read budgets in the tool layer** | Per-domain counters; over budget, the tool returns a synthesize-from-what-you-have message | **Not implemented.** No budget counters exist. |
| **WS4 · Replay discipline** | Tighten eviction to 100k trigger and keep 4; distil facts before the next tool call | **Partly.** Eviction runs at 150k keeping 6 (emergency at 170k keeping 0); the tighter values were not adopted. The distil habit is in the prompt. |
| **WS5 · Fact-quality guards replacing the verifier** | A deterministic citation check that fails a domain, plus prompt self-verification, plus an optional sampled audit mode | **Superseded in part.** The prompt self-verification pass shipped. The status-changing citation check is now **forbidden** by the repository's output-freedom rules, which bar checks that change run status or trigger content repair. `run_checks.py` remains observational only. An equivalent citation report is acceptable as a non-gating diagnostic. |
| **WS6 · Instrumentation** | Per-phase token split and an estimated billed-cost field | **Partly.** `summarize_usage` reports model versus web-search call counts and token fields; there is no estimated-cost field. |

Historical acceptance targets (C05 against C04) were: total tokens ≤ 4.0M, estimated billed cost ≤ 40% of C04, paid calls ≤ 220, property-linked risks ≥ 90% of C04 with no lost high-impact finding, unique cited sources ≥ 40, opened-versus-cited ratio ≥ 50%, citation accuracy at least equal, and zero never-opened citations. The fallback order if quality missed the bar was: raise budgets, then enable sampled audit mode, then reconsider a second research pass — and not to reintroduce lens agents.

**Measured outcome of the shipped shape** (run pair of 02 September 2026, a different property from C04, so not a like-for-like C05): Layer 3 used 21.8M tokens across 140 model calls and 270 searches; Layer 4 used 13.1M tokens across 119 model calls and 105 searches. Layer 3 cited 104 distinct URLs of 202 distinct sources opened (a 51% opened-to-cited ratio, against 29% historically) and had two citations to records stored without readable text.

---

## 4 · Context management as implemented

Two mechanisms on the looping researcher, applied in order: lossless eviction first, lossy summarization second. Neither touches the tool-free synthesis call.

### 4.1 Evidence eviction — lossless, no extra model call

Every fetched source is already persisted in `sources/raw/` and `sources/text/`, and `read_source` serves a repeat call from that store with no network fetch and no provider cost. Eviction is therefore a pointer swap, configured rather than written, using the framework's context-editing middleware:

| Requirement | Configuration |
| --- | --- |
| Clear only older `read_source` bodies | exclude the search tool from eviction |
| Never touch the most recent results | keep 6 |
| Pointer text naming the recovery path | a placeholder that names `read_source` and the retained source id |
| Coarse batches, to spare the prompt cache | batch clearing at a high trigger |
| Idempotent | cleared results are marked in message metadata |
| Nothing permanently lost | the edit is applied to a copy of the request, so `state["messages"]` and the checkpoint keep the full history |

The URL survives for free: tool inputs are not cleared, so the call beside the cleared result still shows what to re-read.

**Known limitation.** The keep count counts tool results, not their size. A single oversized source inside the keep window is not evictable — one such source measured about 305k tokens. That case is why the emergency pass and the summarizer backstop exist.

### 4.2 Early rolling summarization — the backstop

- The model profile reports a 1,050,000-token input limit, so the framework's own default trigger would sit near 892k and would almost never fire. **Eviction is therefore the load-bearing mechanism and the summarizer is a backstop.**
- The operating target is 200k tokens. Normal eviction starts at 150k keeping six recent tool results; if the edited request still exceeds 170k, an emergency pass clears every remaining source body while preserving its URL and source id.
- Summarization triggers at an absolute 170k and retains roughly 70k recent tokens. The trim-before-summarizing setting is explicitly disabled so the complete older portion reaches the summary model instead of the framework's default final slice.
- The reason to enable it at all beyond thresholds: with the middleware active, a context overflow forces summarize-and-retry instead of failing the domain, closing the failure mode where a retry re-bills the domain from turn zero.

**Observed:** in the run pair of 02 September 2026 neither layer triggered summarization. Layer 3 had five model calls above 150k input (maximum 170,000) and Layer 4 none (maximum 143,075). Compaction cleared 2,489 and 3,801 source results respectively.

### 4.3 The summary contract — what must survive compaction

Compress by removing narration, never specifics. Carry forward, in order:

1. The complete asset dependency and resilience ledger, including every applicability state.
2. Every confirmed property fact with its source id and URL, plus material supplied dependencies that remain baseline context rather than risks.
3. Every finding and external frontier as causal nodes and edges, with geographic scale and supported relationships.
4. Explored branches marked supported, conditional, rejected or unresolved, with the evidence controlling that status.
5. Contradictions, competing readings, applicability limits and material unknowns, verbatim.
6. **Every search query already issued, verbatim** — a repeated query is served free from the run's query cache, so preserving the strings converts memory loss into cache hits.
7. Every opened URL and source id, so a later turn re-reads rather than re-searches.
8. Open research questions and the current procedure step.

### 4.4 Why "no context loss" is defensible

Active context necessarily thins; a million tokens cannot stay inside one prompt. Nothing becomes unrecoverable because durability lives outside the conversation:

| Layer | Where | Recovery path |
| --- | --- | --- |
| Raw evidence | `sources/raw/`, `sources/text/` | `read_source(url)` — local, free |
| Search results | `sources/query_cache/` | re-issue the same query — local, free |
| Query log | `sources/queries.jsonl` | audit and deduplication |
| Full message history | `checkpoints.sqlite3` | resume and inspection |
| Compacted state | the in-context summary | carries pointers to all of the above |

### 4.5 Cost interaction with prompt caching

Eviction and summarization rewrite history and break the prefix cache, which ran at a 73% hit rate. Rewriting every turn would trade cheap cached tokens for expensive fresh ones. Compact **coarsely**: evict in large batches at a high trigger, so long cached stretches persist between rare rewrites.

### 4.6 The one framework obstacle

The harness profile excludes summarization middleware **by name**, and the graph builder re-applies that exclusion after merging caller middleware, so passing a plain summarizer instance is dropped in silence. The public middleware alias reports the shared name only for its exact implementation; a subclass falls back to its own class name. A thin subclass therefore survives the filter, which means the framework's default-configured summarizer stays off everywhere, the tool-free calls are untouched, and the exclusion list needs no change.

Middleware order matters: model-call wrappers compose first-as-outermost, so eviction runs before the summarizer and the summarizer counts tokens on already-evicted messages — cheap and lossless ahead of expensive and lossy.

---

## 5 · What was deliberately not built

| Rejected | Reason |
| --- | --- |
| Summarization on tool-free calls | Their peak input is small against the window, and their history *is* the merge state — compacting it is where specifics die. |
| Any compaction into synthesis | A single call with modest input. Fidelity loss there comes from model-side abstraction; machine-side compression compounds it. |
| Cross-run or cross-property memory | Breaks evidence provenance; a due-diligence finding may rest only on this run's stored sources. |
| Filesystem tools for researchers | `read_source` plus the source store already are the retrieval path; exposing file tools adds surface without capability. |
| Trimming or truncating model output | Barred by the standing output-freedom rule: no machine grading, normalization or repair of what the model says. |
| Layer 2 memory middleware | Stateless single-turn calls; nothing to compact. |
| Parallel domain execution | Reduces wall-clock, not cost, and raises rate-limit risk. |

---

## 6 · Open items

1. **Cheaper search proxy (WS1).** Unchanged and still the largest controllable cost lever at 29–39% of tokens.
2. **Search and read budgets (WS3).** The historical C03 run proved loops expand to fill whatever the settings allow; no structural guard exists today.
3. **Estimated billed cost in usage (WS6).** Raw token totals mis-rank cache-heavy runs.
4. **Citation traceability as an observational report.** Two Layer 3 citations pointed at records stored without readable text, and several cited URLs differ from the fetched URL by a tracking parameter. A non-gating diagnostic would surface both; a status-changing check would not be permitted.
5. **Document ingestion.** The single largest quality lever remaining; specified separately.

Run-comparison indexes live inside their run group rather than in this documentation set; the historical C01–C05 index sits in the run folder of the property it measured.

# Layer 3 and Layer 4 World Model Redesign

Status: **audit of the live pipeline plus recommendations**; not implemented · Evidence date 02 September 2026, analysis 03 September 2026, filed in this documentation set 08 September 2026 · Repository: `Sed_ai_v2` (branch `plain_research`, HEAD `dc9d79e`) · Runs audited: `L3_20260902_120424_e0de`, `L4_20260902_132142_bb9f` · Scope: architecture, research strategy and prompt audit; no files changed, no runs started, no repository model or search API invoked.

**Relationship to the target architecture.** This document audits the pipeline as it runs today: eight fixed domains, one direct researcher, two tools. The separate target architecture proposes dynamic plugin-driven domains, a source scout and selector, a shared document-ingestion service and a Layer 4 dependency graph. The two are complementary, and the overlap is recorded in section 16: several findings here are already answered by that design, while the world-model findings (sections 4, 6, 8 and 9) and the prompt changes (section 11) are additional and apply to either domain model.

Every statement carries one label: **[Repo]** Confirmed repository behavior · **[Run]** Confirmed run evidence · **[Doc]** Confirmed official-documentation fact · **[Inf]** Inference · **[Rec]** Recommendation.

Method note. Repository and run artifacts were read directly; PDF bytes were inspected offline with PyMuPDF; official OpenAI and Deep Agents facts were verified against the installed SDKs (`openai` 2.46.0, `deepagents` 0.7.7) and current official documentation pages. Four domains (Asset Integrity, Occupier, Energy, Location) were traced by independent readers and their strongest loss claims re-verified by direct pattern search; the other four domains and all six prompts were traced and audited directly by the author.

---

## 1. Executive decision

**[Rec] Adopt Option C: one property-level "place and world baseline" research stage, run once per property inside Layer 3 before the eight domain researchers, reused verbatim by every Layer 3 domain, every Layer 4 researcher and both syntheses.** Keep the eight domains, the single direct researcher, the two tools, StateBackend, SQLite checkpoints, verbatim Markdown and tool-free synthesis. Change five things, in this order:

1. **Ingestion (deterministic code):** add a born-digital PDF text tier with page markers beneath `read_source`, a document map for long documents, tracking-parameter stripping in URL normalisation, and an explicit extraction status. **[Run]** All 25 distinct unreadable Layer 4 sources are born-digital PDFs with text layers; the sole cause is a media-type branch that returns `None`.
2. **Search strategy (tool descriptions + provider):** request the complete source list (`include`), pass `user_location`, key hits and the store on normalised URLs, and seed the Layer 4 store and query cache from the Layer 3 run. **[Run]** 22 of 105 Layer 4 queries repeated Layer 3 queries and 66 files were fetched twice.
3. **Prompts (six files + one new):** separate "may be rated as a risk" from "may be researched and recorded"; add a Tier 1 "World and place context" output slot at every level; re-scope the candidate mapper from a dependency mirror to a dependency-plus-exploration brief; require one widening pass per uncovered scale before stopping. **[Run]** 83% of Layer 4 register entries restate Layer 3 risks; the entire place model in the Layer 4 synthesis is one bullet.
4. **Architecture:** the baseline stage (one new prompt file, one new stage record, two schema bumps). No subagent, no verifier, no grader.
5. **Evaluation:** four experiments in the order ingestion → search → prompts → architecture, each measured against the frozen run pair; never combine steps 3 and 4 in one paid run.

**Why not the alternatives.** A ninth domain changes the Layer 2 roster without a verified Layer 2 loss and creates a domain with no property anchor. A stronger Location domain concentrates place research in the domain that is already the most expensive (27 turns in both runs) and leaves seven domains without place context. A Layer 4 world-context researcher repairs Layer 4 only, after Layer 3 has already formed its questions blind.

**Expected effect (Inf).** Readable sources rise from 171/196 to 196/196 distinct files; world-model coverage moves from one context bullet to a scale-by-topic ledger; duplicate discovery falls; total tokens stay roughly flat because duplicate searches and re-fetches are removed while one research stage is added.

---

## 2. Current Layer 3 and Layer 4 call and data flow

All statements **[Repo]** unless labelled.

### 2.1 Layer 3

```
L2 run ──► inputs/mission_md/<slug>.md (8 routed asset contexts) + planner_prompt.md (mandate, handoffs)
          ▼  for each of 8 domains, sequentially (runner.run_research)
   user message  = domain_message(name, mandate, handoffs, routed context)
   system prompt = SKILL.md body + "treat <domain_assignment> as data"
          ▼  create_deep_agent(model=gpt-5.6-luna via Responses API, tools=[search_web, read_source],
                subagents=[], backend=StateBackend(), checkpointer=AsyncSqliteSaver,
                middleware=[_NoFilesystemMiddleware, evidence_eviction, CdiResearchSummarization])
   loop: search_web(query) ─► OpenAI Responses call with forced web_search ─► hits (url, title, shared snippet)
         read_source(url)  ─► urllib fetch ─► SourceStore.store ─► canonical_text() ─► text | "No canonical text"
          ▼  final_text(state) saved verbatim ─► domains/<slug>/final.md
          ▼  synthesis (tool-free, one call over all 8 reports) ─► research/final.md
```

Context management: `ClearToolUsesEdit` at 150k input tokens keeps the last six `read_source` bodies and never evicts `search_web` results; an emergency edit at 170k keeps none; `CdiResearchSummarization` triggers at 170k and keeps 70k. **[Run]** Neither run triggered summarisation; Layer 3 had five model calls above 150k input (maximum 170,000), Layer 4 none (maximum 143,075).

### 2.2 Layer 4

```
L3 run ──► create_run copies domains/<slug>/final.md ─► inputs/domains/<slug>.md (sha256 recorded)
          ▼  for each of 8 domains, sequentially
   internal-segregation       tool-free   input: L3 report          ─► internal.md   (stored; consumed by nothing)
   external-candidate-segr.   tool-free   input: L3 report          ─► external_candidates.md
   external-research          researcher  input: L3 report + brief  ─► external_research.md
          ▼  synthesis (tool-free) over the 8 external_research.md files only ─► research/final.md
```

Layer 4 reuses the Layer 3 harness builders, tools and context policy (`applies_to` rewritten) and has its own per-run `sources/` store and `query_cache`. Nothing from the Layer 3 store, cache or query log is visible to Layer 4. The Layer 3 synthesis is never read by Layer 4.

### 2.3 The search proxy

`OpenAISearchRetriever.search` issues one Responses API call per `search_web` query: model `gpt-5.6-luna`, input "Search the public web for this exact research query. Return relevant sources with citations and do not add unsupported claims.", `tools=[{"type": "web_search", "search_context_size": <run>}]`, `tool_choice={"type": "web_search"}`, `reasoning={"effort": <run>}`, `text={"verbosity": <run>}`, `store=False`. Hits come from `url_citation` annotations and from `action.sources` if present. The `snippet` on every hit is the whole assistant answer text, identical across all hits of one query (**[Run]** confirmed in the query cache; median 1.6–1.75k characters). **[Run]** The search phase consumed 39.1% of Layer 3 and 28.8% of Layer 4 tokens at 31.6k / 35.9k tokens per call, because every call is a frontier-model reasoning turn at effort `high`.

### 2.4 Fetch and extraction

`_fetch`: `urllib`, User-Agent `CDI-Deep-Research/1.0`, `Accept` including `application/pdf;q=0.8`, no language preference, 30 s timeout, 10 MiB cap, SSRF-safe redirect handler. `canonical_text()` decodes `text/plain`, `text/markdown`, `application/json` and strips `text/html` / `application/xhtml+xml`; every other media type returns `None`. No PDF branch, no JavaScript rendering, no per-fetch retry.

### 2.5 Volumes observed **[Run]**

| Metric | Layer 3 | Layer 4 |
|---|---|---|
| Wall time | 60 min | 53 min |
| Model calls | 140 | 119 (8 internal + 8 candidates + 102 research + 1 synthesis) |
| Web-search calls | 270 | 105 |
| Total tokens | 21,815,404 | 13,081,063 |
| Cached input tokens | 7,659,513 | 4,553,013 |
| Output tokens (reasoning) | 456,623 (303,308) | 371,509 (242,491) |
| Stored source records / with text | 209 / 181 | 197 / 171 |
| Distinct unreadable files | 26 (all PDF) | 25 (all PDF) |
| Numbered domain findings | 36 risks (2 Established, 34 Conditional) | 46 external findings |
| Synthesis register entries | 33 | 41 (4 Established, of which 2 hybrid; 37 Conditional) |

Layer 4 stage cost: internal 97,710 tokens (0.7%), candidates 86,523 (0.7%), research 12,852,486 (98.3%), synthesis 44,344 (0.3%). Research stage per domain (model tokens | search tokens | turns | seconds): Asset 0.51M | 0.42M | 6 | 208; Occupier 0.30M | 0.24M | 5 | 163; Rights 0.80M | 0.51M | 9 | 366; Ground 0.32M | 0.19M | 5 | 131; Energy 0.48M | 0.24M | 9 | 267; Location 2.77M | 1.30M | 27 | 427; Finance 0.25M | 0.26M | 4 | 139; External Dependencies 3.66M | 0.61M | 37 | 343. Two domains took 65% of research tokens.

---

## 3. Root causes of missing source content

### 3.1 The 26 unreadable records: exact technical cause

**[Run]** All 26 Layer 4 records with `canonical_text_available: false` are `application/pdf` (25 distinct files; one Bebauungsplan file under two URLs). Every file starts with `%PDF-`, none is encrypted, and PyMuPDF opens all 25 with an extractable text layer (1,414 to 654,568 characters; no image-only document; three documents have one or two empty pages). Layer 3 shows the same pattern (28 records, 26 distinct files) with exactly one image-only scan (a 1985 gazette: 64 pages, 0 characters, 64 page images, 10.2 MB).

**[Repo]** The cause is one branch: `canonical_text()` returns `None` for media types outside the HTML/text/JSON set, so `SourceStore.store` writes raw bytes, records `text_path: ""`, and `read_source` returns "Stored <sha> (application/pdf, N bytes). No canonical text is available for verification". Nothing failed at network, size, encoding or access level for these records.

### 3.2 The twelve candidate causes against the evidence

| Cause | Observed? | Evidence |
|---|---|---|
| Search result is only a snippet | Yes, as a discipline risk | **[Run]** Layer 3 Asset report cites the textless `GVBL/2020/00062.pdf` with specific content ("three-year period", validity dates); the Layer 4 Asset report correctly declares the same record an evidence gap. **[Inf]** The Layer 3 claim rests on the search answer text. Layer 4 cited no unreadable record. |
| Redirect or canonical-URL mismatch | Yes, in traceability | **[Run]** 7 Layer 3 and 2 Layer 4 cited URLs are absent from the index because the fetched URL carried `?utm_source=openai` (651/1,069 Layer 3 hit URLs, 249/449 Layer 4) or a `_en`/`.html` variant; `normalize_url` keeps query strings. The `hlNUG.hessen.de` typo in a query shows host aliases also matter. |
| Born-digital PDF | Yes, dominant | 25/25 Layer 4, 25/26 Layer 3. |
| Scanned PDF | Yes, one file | Layer 3 1985 gazette. |
| JavaScript-rendered page | Not as a failure | **[Run]** One `text/html` record flagged text-available holds 26 characters ("Bürgerservice Hessenrecht"); the HLNUG data portal returned only a shell. **[Doc/Run]** Statistics office, census, INKAR and Wegweiser Kommune UIs are JavaScript shells; their APIs or static exports are not. |
| Anti-bot or access restriction | Not in these runs | **[Doc]** Observed in the source survey: broker research 403, Bundesanzeiger captcha, Bundesbank Swagger shell, ECB data portal 503. |
| Incorrect MIME type | Not observed | All PDFs declared `application/pdf`. |
| Oversized source | Not in these runs | Largest stored file 10,215,065 bytes; the 2026-08-25 extraction study measured cap rejections in an earlier run. |
| Malformed encoding | Not observed | `iso-8859-1` declared and decoded correctly for statute pages. |
| Table/layout loss | By design | HTML cells become ` | `-separated; PDF tables are lost entirely. |
| Paywall / authentication | Not in these runs | **[Doc]** Broker and gif reports are gated. |
| Summary instead of underlying record | Yes, structurally | The shared snippet is itself a summary; secondary pages were opened where the primary PDF (statistics table, gazette, market report, budget chapter) could not be read. |

### 3.3 Why search finds what read_source cannot use

**[Repo]** The search tool has already read the page server-side (its answer text quotes figures from PDFs), while `read_source` refetches raw bytes locally and converts only HTML/text/JSON. **[Run]** The one Layer 3 population/employment query returned six official hits (state population bulletin PDF with municipal counts, city economy page, employment-agency district statistics, regional labour forecast PDF, city finance page, state GDP release). The researcher opened one HTML page; no figure reached any report. **[Inf]** Two of the six were PDFs; the model saw the numbers in the answer text, could not verify them, and dropped them.

### 3.4 Deployment note **[Repo]**

PyMuPDF 1.28.0, pypdf 6.14.2 and Docling are installed in the `compute` environment but unused on the main branch. The unmerged `docling-web-extraction` branch prototyped a Docling reader with `pages`/`find` arguments and LangGraph interrupts.

---

## 4. Root causes of incomplete world-model coverage

Five causes compound along the pipeline.

### 4.1 Layer 3 researches only what a pathway already justifies

**[Repo]** Layer 3 SKILL: "Do not force generic national law, statistics, market data, history or world news into the report. They matter only when applicability and transmission to this property are demonstrated." · "Use national statistics only where a property transmission pathway is shown." · Stop rule: stop a question when "no property linkage is established." · `Context only` = "no supported property pathway", placed in the final mixed section.

**[Run]** The Location researcher, whose Layer 2 mandate names "catchment, demographics, employment and regional economy", issued one such query in 40. The tokens "population", "employment", "demograph", "commuter", "GDP" and "regional econom" do not occur in either synthesis. The one surviving place fact is "approximately 55,000 residents and a Rhein-Main location", carried as `Context only`.

**[Inf]** The wording conflates two decisions: whether a fact may be rated as a risk (correctly pathway-gated) and whether it may be researched and recorded (which the world model needs regardless). Because the second is gated by the first, unlinked facts die at discovery.

### 4.2 The handoff is a risk list, not a world inventory

**[Run]** "Dependencies requiring external research" holds 73 items across eight domains, overwhelmingly property-internal record gaps (lease addenda, debt terms, certificates, valuation) with a minority of outward frontiers (municipal heat planning, U2 access geometry, EPBD transposition, NIS2 scope, DK III capacity). **[Run]** The candidate briefs mirror the Layer 3 risk lists: Asset brief items 1–7 = Layer 3 risks 1–7; Rights brief factors 2, 3, 5, 6 = Layer 3 risks 1–4; Finance brief factors 1, 3, 4, 6 = Layer 3 risks 1–4. Restatement share of Layer 4 numbered findings versus Layer 3 risks: Asset 7/8, Occupier 4/6, Rights 3/3, Ground 4/5, Energy 6/7, Location 4/5, Finance 4/5, External Dependencies 6/7 — about 38 of 46. At synthesis level 34 of 41 entries (83%) restate a numbered Layer 3 synthesis risk; only one entry (commercial energy-price easing) is a direction absent from Layer 3.

**[Inf]** The mapper is told it is "neither evidence nor a discovery boundary", but its contract ("Account for every material Layer 3 dependency once", "Do not generate research questions, search strings or searchable anchors") produces a brief whose only anchors are Layer 3's own dependencies and links. A researcher told to "Begin with Layer 3's asset facts" and to scan world conditions "only when a plausible Layer 3 pathway exists" has no sanctioned starting point outside the Layer 3 report. **[Run]** The Asset and Energy researchers' first fetches re-opened exactly the Layer 3 links (14 and 15 URLs respectively).

### 4.3 Layer 4 re-suppresses what Layer 3 suppressed

**[Repo]** Layer 4 rule 2 scans twenty condition classes "only when a plausible Layer 3 pathway exists"; the stop rule adds "Do not continue merely to find a geopolitical or macroeconomic explanation."

**[Run]** Layer 4 issued 105 queries: 1 on population, 0 on employment, 0 on investment, 2 on business or insolvency, 0 on the metropolitan region, 1 on the district, 1 on the EU. The Asset researcher spent 9 of 15 queries on one inspection ordinance and declared insurer response, utility redundancy, cyber and political conditions "context or evidence gaps" with zero queries on them. The Energy researcher closed the renewable/PV/grid factor with zero queries. The Occupier researcher opened two insurer statistics pages and wrote nothing about them. Six research stages ran 4–9 turns in 2–6 minutes.

**[Inf]** Early termination is driven by the scoping rule, not by budget: once the Layer 3 links are re-opened there are no sanctioned questions left.

### 4.4 No output slot for Tier 1 context

**[Repo]** Layer 3 domain section 5 mixes contradictions, context-only subjects, unextended anchors and pure gaps; Layer 3 synthesis section 7 likewise; Layer 4 research folds "context-only factors" into one list; Layer 4 synthesis places them "in the final section when material". No prompt has a section whose purpose is verified world context kept outside the register.

**[Run]** Layer 3 synthesis: 73 handed-over dependency items → 48 survive, 14 degraded (identifiers dropped), 11 lost; quantified external figures stripped while links kept (NAI apollo take-up and rents, Destatis indices, ECB rates, GEG percentages); one register rating overwritten (RP4 ratings replaced by GC3's); a factual error introduced ("six named domain responses" for eight). Layer 4 synthesis: 46 → 41 via four merges and one full drop (the Occupier finding on fragile commercial-real-estate financing, none of whose evidence survives); non-numbered material dropped (lead-pipe deadlines, court staffing count, state security-and-justice investment figure, the "insolvency-safe tenant" buffering fact, municipal heat-transition planning, terrorism cover); the only place fact is one bullet.

**[Inf]** "When material" + "write telegraphically" + a section list without a Tier 1 slot makes context the first casualty of compression. The classification vocabulary is adequate; the output organisation is not.

### 4.5 The evidence tool cannot open the primary place records

**[Run]** Place-model sources the proxy found were disproportionately PDFs: state population bulletin, regional labour forecast, municipal market report (82 pages), participation report (210 pages), parking and fee by-laws, building plans and justifications, state justice budget chapter (240 pages), chamber market report, transport planning decision (245 pages). All stored without text. **[Doc]** The source survey confirms municipal budgets, participation reports, chamber reports, valuation-committee reports, parliamentary papers and insurer statistics are PDF-only classes, while statistics offices, the employment agency, Eurostat, the Bundesbank and the regional planning association expose tables or APIs that `read_source` can already consume.

**[Inf]** Even with corrected prompts the world model stays thin until the PDF tier exists, because the model correctly refuses to cite what it cannot read.

### 4.6 Cost is concentrated in duplication, not in discovery

**[Run]** 98.3% of Layer 4 tokens sit in the research stage; 65% of that in two domains that re-researched Layer 3 material; the mapper and internal stages together cost 1.4%. There is room to fund a baseline stage and PDF reads by removing duplication.

---

## 5. Source-ingestion redesign

**[Rec]** Keep `read_source(url)` as the single reading tool and put a deterministic fallback hierarchy beneath it, ordered by cost and by observed need.

| Tier | Mechanism | Covers (evidence) | Status returned |
|---|---|---|---|
| 0 | Store lookup by normalised URL and by content hash; strip `utm_*` and similar tracking parameters before normalisation; record fetched URL and final URL | 66 files fetched twice across the pair; 651/1,069 hit URLs carry `utm_source` | `cached` |
| 1 | HTML / text / JSON extraction (existing) | 171 of 197 Layer 4 records | `text` |
| 2 | Born-digital PDF text layer via PyMuPDF in a child process with timeout; `[p.N]` page markers; page count, characters per page and empty-page count recorded in `index.jsonl` | 25/25 Layer 4 PDFs, 25/26 Layer 3 | `pdf_text`, pages, empty pages |
| 3 | Document map for long documents (bookmarks or first heading per page; capped) and `pages="a-b"` / `find="term"` retrieval so a 245-page decision is never pushed into context whole | Largest Layer 4 PDFs: 245, 240, 210, 196 pages | `pdf_map` |
| 4 | OCR only for pages tier 2 flags empty (RapidOCR via Docling or Tesseract via PyMuPDF), bounded by page count | 1 image-only file in two runs; 3 partially empty | `ocr` |
| 5 | Official-alternative hint in the limitation text: HTML version, table portal, CSV/API export, press release naming the same figure; the tool description tells the model to try these before declaring a gap | Population PDF has a GENESIS/Regionalstatistik table twin | `alternative_suggested` |
| 6 | JavaScript rendering as a run-frozen, default-off last resort for `text/html` records whose text is shorter than a threshold | Not needed for the observed failures | `rendered` |
| — | Every result header: `SOURCE <sha>`, `URL`, `FINAL_URL`, `STATUS`, `PAGES a-b of N`, limitations (tables flattened, empty pages, truncated) | | |

Design rules that follow from the repository constraints: raw bytes stay authoritative; extraction artifacts are keyed by source hash with extractor name and version; extraction never grades or rewrites model output and never blocks sibling outputs; page-level provenance (`sha p.12`) is required for citation traceability; the snippet is never promoted to evidence merely because the source is unreadable; the two-tool contract is kept (`pages` and `find` are optional arguments, which the pinned tests allow because they pin tool names and the phrases "canonical text" and "candidate sources" only).

**[Inf]** With tier 2 alone, the Layer 4 run would have had 196 of 196 distinct sources readable, including the municipal market report, transport decision, building plans, parking and fee by-laws, participation report and state budget chapter — exactly the primary records the place model needs. A `text/html` record should also be flagged `thin` when extracted text is under a small threshold, so the misleading `canonical_text_available: true` on a 26-character shell page is visible.

---

## 6. Search-strategy redesign

### 6.1 Assessment of the current proxy

**[Repo]** Every `search_web` call is a full frontier-model reasoning turn whose only instruction is to search "this exact research query". The tool description says only "Search the public web for candidate sources and discovery snippets." No strategy exists in code, tool description or prompt beyond the Layer 3 priority sentence (address → municipal records → recent events → legislation → market evidence).

**[Run]** Operator use is good (site: on 207/271 and 83/105 queries); scale and topic are narrow:

| Scale or topic | Layer 3 (271) | Layer 4 (105) |
|---|---|---|
| Municipality named | 89 | 31 |
| District | 2 | 1 |
| Metro region | 2 | 0 |
| State | 70 | 39 |
| Federal | 33 | 16 |
| EU | 18 | 1 |
| Population or demographics | 1 | 1 |
| Employment or labour market | 1 | 0 |
| Investment or business location | 5 | 0 |
| Business formation or insolvency | 5 | 2 |
| Office market indicators | 8 | 4 |
| Municipal finance | 16 | 2 |
| `filetype:` | 0 | 0 |
| Near-duplicate of an earlier query, same run | 17 | 4 |
| Near-duplicate of a Layer 3 query | — | 22 |

**[Inf]** The proxy is not too generic; the strategy is too narrow, and the pipeline pays twice for repeated discovery.

### 6.2 Where each behaviour belongs

| Behaviour | Prompt | Tool description | Deterministic code |
|---|---|---|---|
| Scale ladder site → catchment → municipality → district → metro region → state → country → EU → global; widen only when the narrower scale is exhausted or the question is inherently wider | Yes (one sentence in the baseline prompt and in Layer 4) | Mention that a query may carry `site:` and a scale term | — |
| Jurisdiction-native terminology (German terms of art: *Bebauungsplan*, *Bodenrichtwert*, *Beschäftigte am Arbeitsort*, *Hebesatz*, *Haushaltssatzung*) | Yes | One line | — |
| Exact address, parcel, occupier, installed-system searches first | Already in Layer 3 | — | — |
| Domain-restricted official and file-type searches (`site:`, `filetype:pdf` for gazettes, budgets, by-laws) | — | Yes | Optional `allowed_domains` pass, default off |
| Entity aliases and historical names (former operators, merged authorities, old street spellings) | Yes | — | — |
| Date bounds (last 24 months; announced through the hold period) | Already present | — | — |
| Diversify after a failed query (synonym, language switch, scale change, portal change) rather than re-issue | Yes | "a repeated or near-identical query returns the cached result" | Cache key casefolded, whitespace-collapsed, tracking parameters stripped; cache hit and zero-result status shown to the model |
| Alternative-source discovery when an authoritative record is unreadable | One sentence | In the `read_source` limitation text | Status + suggested alternative class |
| Record negative research once | Output contract | — | `queries.jsonl` already records `new_sources` |
| Discovery breadth vs evidence depth | Yes: Tier 1 / Tier 2 split | — | — |
| Cross-run reuse | — | — | Seed Layer 4 store and query cache from the Layer 3 run at `create_run` |

### 6.3 Provider changes limited to documented parameters

Verified in the installed `openai` 2.46.0 SDK type definitions and the current official guide (**[Doc]**):

| Parameter | Official behaviour | Current code | Change |
|---|---|---|---|
| `tools[].type` | `web_search` or `web_search_2025_08_26`; `web_search_preview` is legacy and lacks `filters` | `web_search` | Keep |
| `include=["web_search_call.action.sources"]` | Returns "the complete list of URLs the model consulted"; sources carry only `type` and `url` | Not passed; code reads `source.title`/`source.snippet`, which do not exist | Add `include`; treat sources as URL-only candidates, annotations as cited leads |
| `url_citation` annotations | `url`, `title`, `start_index`, `end_index` | Snippet = whole answer text for every hit | Slice per hit around `start_index:end_index`, or label the shared text `answer_text` |
| `action.open_page.url`, `action.find_in_page.url` | Pages opened during reasoning-model search | Ignored | Harvest as candidates |
| `tool_choice` | Documented forcing form is `"required"`; the SDK literal for hosted-tool choice lists `web_search_preview` but not `web_search` | `{"type": "web_search"}` | Use `"required"` or verify the object form against the current API reference |
| `user_location` | `{"type": "approximate", "country": "DE", "region": ...}` refines by geography | Not set | Set country/region per run from the property's jurisdiction; never a hardcoded town |
| `filters.allowed_domains` | Up to 100 domains, subdomains included, no scheme; `web_search` only | Not used | Optional provider option for official-registry passes |
| `search_context_size` | `low`/`medium`/`high`, default `medium`; search context capped at 128k | Run-frozen (`medium` here) | Keep run-frozen; `low` suffices for discovery because evidence comes from `read_source` |
| Pricing | $10 per 1k calls plus search content tokens at model rates; reasoning billed | Frontier model at effort `high` per query | Cost lever only (2026-08-31 plan); the largest controllable cost |
| `store=False` | Allowed | `store=False` | Keep |

Not adopted: `return_token_budget` (guide-only, absent from the installed SDK); passing PDFs as `input_file` with `file_url` (official, 50 MB, text plus page images — moves extraction into a paid call and loses local page provenance).

---

## 7. Domain-options comparison

| Criterion | A. Eight domains, stronger Location | B. Ninth domain "Regional Economy, Demographics, Investment & Place Dynamics" | C. One place/world baseline call reused by L3 and L4 | D. L4 cross-domain world-context researcher |
|---|---|---|---|---|
| Information coverage | Only Location gets place data; Occupier, Finance, External Dependencies, Asset receive none | Full but late: one input among nine at synthesis | Full and early: every L3 domain and L4 researcher starts from one dated, cited ledger | L4 only; L3 still forms questions blind |
| Overlap and duplication | Existing 22/105 duplicate queries persist | High with Location (market), Finance (macro), External Dependencies (labour) | Lowest: regional searches run once instead of up to sixteen times | Medium: duplicates L4 domain searches |
| Property linkage | Good, but Location is already the heaviest domain (27 turns both runs) and would dilute | Weak by construction; no property anchor | Done where it belongs: domains link the baseline to dependencies | Weak; must invent linkage or stay generic |
| Call and token cost | +0 stages; Location grows (already 4.1M tokens in L4) | +1 L3 researcher (0.4–3.4M observed range) +3 L4 calls +1 synthesis input + Layer 2 roster change | +1 researcher stage per property (est. 1–3M) +8–15k input tokens on 16 downstream prompts, mostly cached | +1 researcher stage (1–3M) +1 synthesis input |
| Checkpoint and synthesis complexity | None | Highest: L2 `AGENT_NAMES`, planner JSON, `DOMAIN_NAMES`, tests, schemas | One stage record, one input file, one section per synthesis prompt | One stage record; ninth report at synthesis |
| Risk of generic commentary | Medium | High | Contained: explicitly unrated context, never a finding source | High |
| Preserves not-yet-risk context | Only with output changes | Yes | Yes by design | L4 only |
| Fits "no Layer 2 change" | Yes | No | Yes | Yes |

**[Rec] Option C**, plus the Option A intent delivered by prompt: domains link place context to their dependencies instead of researching it eight times. B is rejected (Layer 2 change without a verified Layer 2 loss; a domain without an anchor). D is rejected (repairs Layer 4 only; adds a ninth report without removing duplication).

---

## 8. Recommended Layer 3 responsibility

**[Rec]**

1. **Place and world baseline (new stage, once per property, before the eight domains).** Same direct researcher, same two tools, same context policy. Input: the eight Layer 2 routed contexts (address, municipality, district, state, occupier, use, sector, hold period, named systems and counterparties are all present there). Output `research/place_baseline.md`: a scale-by-topic ledger of externally verified facts and dated announcements with links and page references; no likelihood or impact ratings; no property-effect claims; one "not found / not applicable / not searched" line per cell; German-language official sources preferred. This is Tier 1 by definition.
2. **Eight domain researchers (unchanged count).** Property facts, systems, dependencies, vulnerabilities, safeguards and directly property-linked risks. Each receives the baseline as supplied context, links rather than re-researches it, researches outward only to the first external node, and records incidental world signals absent from the baseline under a Tier 1 heading instead of dropping them.
3. **Dependency ledger as the explicit handoff.** The existing section "Dependencies requiring external research" is strengthened: exact dependency, applicability state, what is known, what is unresolved, and the scale at which the outside driver is likely to live. Contradictions and safeguards stay inside it because Layer 4 currently receives the whole report and the mapper decides what to carry.
4. **Synthesis.** Adds "World and place context" (baseline plus domain Tier 1 items once, unrated, outside the register) and a dedicated "Dependencies requiring external research" section so identifiers are not recoded as pure gaps (**[Run]** 25 of 73 items were lost or degraded).

Layer 3 owns initial discovery of property facts and of the world baseline; it does not own outward causal extension beyond the first external node.

---

## 9. Recommended Layer 4 responsibility

**[Rec]**

1. **Candidate mapper (keep, re-scope).** Input: Layer 3 report plus the baseline. Output: (a) dependency-linked external factors as today; (b) exploration directions per scale and topic where the baseline shows a signal without a pathway yet; (c) Layer 3 evidence gaps that external records could close. It stays navigation, not a boundary; the researcher must run one widening pass per uncovered scale regardless.
2. **External researcher (unchanged harness).** Owns causal extension outward from each dependency and inward from baseline signals where a pathway exists. Produces Tier 2 pathways (established or conditional) and a separate Tier 1 list of verified world signals whose property effect is not demonstrated, unrated. Does not re-open Layer 3 sources unless a claim depends on them (seeded cache makes re-reads free anyway).
3. **Internal segregation (keep as user-facing).** **[Run]** Four independent readers found it a pure reformatting of the Layer 3 report; it is consumed by nothing and costs 0.7% of the run. Keeping or dropping it is a product decision.
4. **Synthesis.** Owns cross-domain structure and the two-tier organisation: numbered register (Tier 2) and a "World and place context register" (Tier 1) merging baseline, domain and Layer 4 Tier 1 items once each, unrated, with scale and date.

Responsibility matrix:

| Task | L3 baseline | L3 domain | L3 synthesis | L4 mapper | L4 researcher | L4 synthesis |
|---|---|---|---|---|---|---|
| Property facts and applicability states | — | Owner | Consolidates | Reads | Reads | — |
| Place and world context discovery (Tier 1) | Owner | Adds incidental items | Carries once | Proposes directions | Extends, adds new signals | Carries once |
| Directly property-linked risks | — | Owner | Register | Reads | Does not restate | — |
| Dependency ledger (handoff) | — | Owner | Carries verbatim | Consumes | Consumes | — |
| Outward causal extension | — | First external node only | — | Hypothesises | Owner | — |
| Cross-domain relationships | — | — | Owner (L3) | — | Within domain only | Owner (L4) |
| Contradictions and evidence gaps | Records | Records | Carries | Lists closable gaps | Closes or records | Carries |

---

## 10. Layer 3 → Layer 4 input contract

**[Repo] Current.** Per domain: the verbatim Layer 3 domain report and the candidate brief. Not received: Layer 3 synthesis, other domains' reports, Layer 3 source index, Layer 3 query log, Layer 2 routed context.

**[Rec] Proposed.**

| Input to Layer 4 | Form | Why |
|---|---|---|
| Layer 3 domain report | Verbatim, unchanged | Keeps facts, classifications, contradictions, links; 13–23 KB is adequate |
| Place and world baseline | Verbatim `research/place_baseline.md` | One Tier 1 ledger for every researcher; removes eight-fold regional research |
| Candidate brief | Verbatim, re-scoped | Prioritisation plus exploration directions |
| Layer 3 source store and query cache | Copied into the Layer 4 run at `create_run` (provenance kept in `index.jsonl`) | 66 refetches and 22 repeated queries; the model sees "cached" |
| Layer 3 synthesis | Not to domain researchers; optionally read-only context for the Layer 4 synthesis | Avoids replaying 75 KB into eight loops; helps cross-domain matching |
| internal.md | Not passed (unchanged) | No research value |

Not recommended: a Python-authored ledger file. The ledger stays model-authored inside the verbatim report; Python must not select or grade content.

---

## 11. Prompt-by-prompt change map

Conventions: quoted text is the current wording; `−` marks deletion, `+` insertion. Each behaviour is stated once at the level that owns it: tool descriptions own tool mechanics; SKILL files own research behaviour; synthesis prompts own reconciliation. No property or town is named. No model, search or token limits are restated.

### 11.1 Layer 3 `SKILL.md` (direct domain researcher)

**Objective.** Discover current or emerging risks within one domain that reach the property; keep dependencies and safeguards visible; five fixed sections.

**Does well.** Evidence discipline ("discovery leads, never evidence"; "canonical content successfully returned"); the dependency ledger with applicability states; the two causal chains; "Missing input is not a finding"; the self-review inside the loop; "Source silence is a knowledge gap".

**Suppressing wording (with run effect).**
- "Do not force generic national law, statistics, market data, history or world news into the report. They matter only when applicability and transmission to this property are demonstrated." → **[Run]** one place query in 40 for Location; six official hits dropped.
- "Use national statistics only where a property transmission pathway is shown." → same effect; also blocks recording of district and state statistics.
- Stop rule "…or no property linkage is established." → ends a question at exactly the point where Tier 1 recording should happen.
- Section 5 mixes context with gaps → context compresses away at synthesis.

**Contradictions or duplication.** "Search broadly enough to discover the relevant records" versus the two sentences above. The external-frontier step 6 and the "External and geopolitical dependency" checklist item say the same thing twice. Section 4 "Preserve exact anchors without inventing a factor, question or search string" conflicts with Layer 4's need for scale hints.

**Stop rules.** Not the primary cause of early stopping in Layer 3 (7–35 turns); but the linkage clause is.

**Scoping of "generic statistics".** Wrongly scoped: it gates research and recording, not only rating.

**Exact changes.**

Conditional perspective checklist, closing paragraph:
> − Do not force generic national law, statistics, market data, history or world news into the report. They matter only when applicability and transmission to this property are demonstrated.
> + Rate a subject as a risk only when applicability and transmission to this property are demonstrated. A verified place or world fact without that pathway is still recorded once, unrated, under `## World and place context` when it is absent from the supplied place baseline.

Research procedure step 4, last sentence:
> − Use national statistics only where a property transmission pathway is shown.
> + Statistics at any scale become a numbered risk only where a property transmission pathway is shown; otherwise they remain Tier 1 context.

Research procedure, new step 2a (one sentence):
> + Read the supplied place baseline first; link its facts to the domain's dependencies instead of re-searching them, and search outward only for what the baseline does not cover.

Stop rules:
> − Stop a question when evidence supports an answer, evidence conflicts, the necessary record is unavailable, or no property linkage is established.
> + Stop a question when evidence supports an answer, evidence conflicts, or the necessary record is unavailable. A subject without property linkage is recorded as context and closed, not dropped.

Section 4 of the final report:
> + Give each item its likely driver scale (site, catchment, municipality, district, region, state, country, EU, global) and the record class that would resolve it. Do not invent a factor, question or search string.

Final report sections: split section 5 into
> 5. `## World and place context` — verified external facts and dated announcements relevant to this domain, absent from the supplied place baseline, unrated, each with scale, date and link.
> 6. `## Contradictions and evidence gaps` — competing readings, supplied anchors external evidence could not extend and pure gaps. Keep pure gaps unrated.

Delete the duplicate: keep step 6 (external frontier), and shorten the checklist's "External and geopolitical dependency" bullet to "see step 6".

**Pinned test phrases affected** (`tests/test_layer3_prompts.py`): "Use national statistics only where a property transmission pathway is shown"; the exact five-section list; "## Contradictions, context and evidence gaps".

### 11.2 Layer 3 `prompts/synthesis.md`

**Objective.** Reconcile eight domain reports into one landscape without new facts.

**Does well.** Merge discipline ("identical cause and transmission pathway"); "Never promote context…"; retention rule for specifics; the same-model caveat.

**Losing wording.** No section receives "Dependencies requiring external research", so items are recoded as "pure gaps" (**[Run]** 11 lost, 14 degraded). "Compress narration and exact duplication, never specifics" is correct but was not followed (**[Run]** most quantified figures stripped); the prompt cannot fix model non-compliance, but it can make the loss visible by requiring the counts.

**Exact changes.**
Output list:
> + 4a. `## World and place context` — the supplied place baseline and every domain Tier 1 item, once each, unrated, with scale and date; never merged into the register.
> + 4b. `## Dependencies requiring external research` — every domain item carried verbatim, deduplicated only on identical text, with its driver scale.

Reconciliation rules, one sentence:
> + State the number of domain responses supplied and the number of items carried into sections 4a and 4b as read from the input, not from memory.

**Pinned phrases affected:** the seven-section list in `test_synthesis_receives_domain_responses_directly`.

### 11.3 Layer 4 `SKILL.md` (external researcher)

**Objective.** Research outside forces transmitting into Layer 3 dependencies.

**Does well.** Seven-node pathway; "neither evidence nor a discovery boundary"; the class "Property dependency without proven adverse external event"; scale testing in rule 5; "Do not manufacture complexity".

**Suppressing wording (with run effect).**
- Rule 2 "…only when a plausible Layer 3 pathway exists." → **[Run]** 0 employment/investment queries in 105; factors closed with zero queries.
- Stop rule "Do not continue merely to find a geopolitical or macroeconomic explanation." → 4–9 turn stages.
- "Treat Layer 3 as authoritative asset context… do not re-audit it." plus "exact Layer 3 dependency" in the final response → first fetches re-open all Layer 3 links; 83% restatement.
- "Communicate only what is material" plus one mixed list for "context-only factors, evidence gaps and uncertainty" → Tier 1 compressed to one line.

**Contradiction.** "reject, combine, extend or independently discover factors" versus rule 2's pathway gate and the stop rule.

**Exact changes.**

Inputs and authority, add after the Layer 3 bullet:
> + The supplied place baseline is verified Tier 1 context. Do not re-research it; extend it where a dependency or a scale is uncovered, and record new world signals in the same form.
> + Do not re-open Layer 3 sources unless a new claim depends on their exact wording; they are served from the run store.

Research rules 2:
> − Conditionally scan demographic, labour, … security conditions only when a plausible Layer 3 pathway exists.
> + Scan demographic, labour, sector, occupier, financial, regulatory, public-budget, utility, infrastructure, technology, cyber, insurance, climate, trade, supply-chain, political, geopolitical, social, public-health and security conditions at every scale from site to global that the dependencies or the baseline make relevant. Record a verified condition without a pathway as Tier 1 context; build a numbered pathway only where each transmission step is supported.

Research rules 3:
> − Follow evidence to upstream causes only while a supported property pathway remains intact.
> + Follow evidence upstream while a pathway remains intact; where it breaks, keep the verified upstream fact as context and name the missing step.

New rule (one sentence):
> + Before finalizing, run one discovery pass for each scale the brief and baseline leave uncovered, using jurisdiction-native terminology and official portals, and record its outcome once even when nothing property-relevant is found.

Stop rules:
> − Do not continue merely to find a geopolitical or macroeconomic explanation.
> + Do not continue to force a pathway; do continue until every relevant scale has been scanned once.

Final response, add one bullet before "material contradictions":
> + a `## World and place context` list of verified external facts without a demonstrated property effect, unrated, with scale, date and link;
and narrow the mixed bullet to "material contradictions, evidence gaps and uncertainty".

**Pinned phrases affected** (`tests/test_layer4.py`): none of the asserted substrings is deleted ("neither evidence nor a discovery", "reject, combine, extend or independently discover", "geographic or sector manifestation", "reinforcing", "balancing feedback effects", "consecutively numbered list, starting at 1" remain); the rewritten rule 2 removes no pinned string.

### 11.4 Layer 4 `prompts/external_candidates.md`

**Objective.** Map the Layer 3 report into a prioritised brief of outside factors.

**Does well.** Anchors every factor to an exact dependency; forbids ratings; "Do not force a category".

**Suppressing wording.** "Account for every material Layer 3 dependency once." makes the brief a dependency mirror. "Include a factor only when it connects to an exact dependency or fact in Layer 3" excludes exploration directions. "Do not generate research questions, search strings or searchable anchors." leaves the researcher with Layer 3's URL inventory as its only anchors (**[Run]** Asset: first 14 fetches were Layer 3 links).

**Exact changes.**
> + Inputs: `<external_candidate_input>` also contains the supplied place baseline.
> − Include a factor only when it connects to an exact dependency or fact in Layer 3 through a plausible transmission mechanism.
> + Part A: for every material Layer 3 dependency, one or more plausible external factors with the exact dependency and mechanism, or `No grounded external factor`. Part B: for every scale and topic where the baseline records a verified signal or a gap without a Layer 3 pathway, an exploration direction naming the institution or record class and the scale, without asserting a pathway.
> − Do not generate research questions, search strings or searchable anchors.
> + Name the record class and jurisdiction level to consult (for example a state statistics series, a municipal budget, a regulator's register); do not write search strings.

Output: rename `## Research brief` content to hold Part B directions with scale and horizon.

**Pinned phrases affected:** "Account for every material Layer 3 dependency once" stays; "without a plausible Layer 3" may need to remain in Part A's sentence; the test asserting absence of "- `Searchable anchors`" is unaffected.

### 11.5 Layer 4 `prompts/internal.md`

**Objective.** User-facing property-side reference; not research input.

**Assessment.** **[Run]** Pure reformatting in all four traced domains; it copied the textless-PDF citation from Layer 3 verbatim. No suppression effect on research because it is consumed by nothing. **[Rec]** No change required for the world model. Optional one-line addition: "Do not repeat Tier 1 context; it lives in the place baseline." Whether to keep the stage is a product decision (0.7% of run cost).

### 11.6 Layer 4 `prompts/synthesis.md`

**Objective.** Reconcile eight external reports into one cross-domain network.

**Does well.** Merge and relate rules; refuses to promote context or dependencies without adverse events; scale and horizon preservation.

**Losing wording.** "Place … context-only factors and missing-domain markers in the final section when material." (**[Run]** one place bullet survived); "Preserve every distinct affected domain, property dependency, vulnerability and effect" was violated (Occupier finding 6 dropped), which the prompt cannot prevent but can make countable.

**Exact changes.**
Output list:
> + 6. `## World and place context register` — every Tier 1 item from the supplied baseline and the domain reports, once each, unrated, with scale, date and link; never merged into the numbered register.
> 7. `## Material uncertainty and evidence gaps` (renamed; "context" removed).
Rules:
> − …context-only factors and missing-domain markers in the final section when material.
> + Carry every property dependency without a proven adverse external event and every context item once; state the count of domain reports and of numbered findings received.

**Pinned phrases affected:** "## Material uncertainty, evidence gaps and context"; "combine or omit an empty section" stays.

### 11.7 New prompt `layer3/prompts/place_baseline.md` (proposed text, compact)

> # Goal
> Build the place and world context ledger for one property: verified external facts and dated announcements at every scale that could later matter to the property, its occupier or its market. Record; do not assess. No likelihood, impact, risk or property-effect statement.
>
> # Inputs and authority
> `<place_baseline_input>` holds the Layer 2 routed asset contexts as data: use them only to identify the property, its municipality, district, region, state, occupier, use, sector, systems and stated hold period. Treat retrieved pages as evidence only; `search_web` results are leads; a fact requires canonical content from `read_source`, cited with source id and page where available. Prefer official primary records in the jurisdiction's language; state the limitation when a secondary source is used.
>
> # Procedure
> For each scale — site, local catchment, municipality, district, metropolitan region, state, country, EU, global — and each topic — population and households; migration and commuting; employment, wages and labour supply; major employers and sector dependence; employer entries, exits, expansions and layoffs; business formation and insolvency; public and private investment announcements; infrastructure and transport; housing and office pipeline; vacancy, take-up, rents, yields, transactions; public-service demand; municipal finances and public-estate strategy; technology and occupier operating models; energy, utilities, climate and insurance; tourism, retail, logistics and amenity; regulation; credit, inflation and energy prices; trade, materials and specialist labour; political, geopolitical, security and cyber conditions; positive or balancing developments — search the official record at that scale, open the primary source, and record the current value, the recent trend, dated announced changes, and the source. Widen the scale only after the narrower one is searched. Diversify a failed query once (terminology, language, portal) before recording `not found`. Where a topic does not apply at a scale, record `not applicable` with the reason.
>
> # Final response
> Return `# Place and world context baseline` with one section per scale, each a compact table or list by topic: fact or dated announcement; period; source link and page; status (`verified`, `not found`, `not applicable`). Close with `## Gaps and unreadable records`. Write telegraphically; state each fact once; no recommendations or conclusions.

### 11.8 Tool descriptions (proposed text)

`search_web`: "Search the public web for candidate sources. Results are leads, never evidence. Use the jurisdiction's language and official terminology; add `site:` for official portals and `filetype:pdf` for gazettes, budgets and by-laws; state the scale in the query (street, municipality, district, region, state, country). A repeated or near-identical query returns the cached result, so change terminology, language, scale or portal instead of repeating."

`read_source`: "Open one public URL and return retained canonical text with its source id and, for documents, page markers. Long documents return a map first; request `pages=\"a-b\"` or `find=\"term\"` to read parts. An unreadable source returns an explicit status and the alternative record classes to try (HTML version, table portal, CSV or API export, official release). Use this result, not a search snippet, as evidence."

`tool_description_overrides` on the existing `HarnessProfile` can apply these without editing `research_tools.py` (**[Doc]**, verified in the installed 0.7.7 source), but the run-frozen prompt copy mechanism does not cover tool descriptions; editing the docstrings keeps them in one place.

---

## 12. Minimal Deep Agents architecture

**[Repo]** Deep Agents 0.7.7 exposes `create_deep_agent(model, tools, *, system_prompt, middleware, subagents, skills, memory, permissions, backend, interrupt_on, response_format, state_schema, context_schema, checkpointer, store, debug, name, cache)`; `HarnessProfile` supports `tool_description_overrides`, `excluded_tools`, `excluded_middleware`, `extra_middleware`, `general_purpose_subagent`; the repository's profile disables the general-purpose subagent, excludes `SummarizationMiddleware` and `PatchToolCallsMiddleware`, and substitutes a no-op for `FilesystemMiddleware`, which also disables the framework's 20k-token tool-result offloading. **[Doc]** 0.7.7 was released 2026-08-18; no 0.7.x release changes tool-result truncation, summarisation defaults or `response_format`.

**[Rec]** Every element fits the existing shape:

| Requirement | Kept? | How |
|---|---|---|
| One direct researcher per stage | Yes | Baseline stage = one more `create_direct_research_harness` call with a new prompt file |
| Only `search_web` and `read_source` | Yes | Optional `pages`/`find` arguments; no new tool |
| StateBackend | Yes | The model writes no files; baseline is saved by Python like every verbatim output |
| SQLite checkpoints | Yes | One more stage record and thread id; schema bumps (L3 → 9, L4 → 3) |
| Source and query caching | Extended | Tracking-parameter stripping; extraction artifacts keyed by hash; Layer 4 seeded from Layer 3 |
| Context eviction and summarisation | Yes | Unchanged policy; page-bounded `read_source` results reduce pressure (the framework's 20k offloading is disabled, so the tool must bound its own output) |
| Verbatim Markdown | Yes | All outputs saved unchanged |
| Tool-free synthesis | Yes | Two prompts gain one section each |
| No subagents | Yes | Sequential stages already isolate context |

Considered and not adopted: subagents (isolation already provided by stages and threads); `skills`/`memory` (prompts are already run-frozen files; cross-property memory is forbidden by AGENTS.md); `RubricMiddleware` (grader sub-agent plus repair loop, which the repository forbids); `SummarizationToolMiddleware` (adds a tool); JavaScript rendering by default (not needed by observed failures); MCP or a document service (a child-process extractor covers 25 of 26 documents); `include=["reasoning.encrypted_content"]` on the model (documented for `store=False`; cost effect unmeasured — an A/B, not a default).

---

## 13. Evaluation and rollout sequence

**[Rec]** Four experiments, one change each, against the frozen pair as baseline. Cheap, offline or Layer-4-only steps first.

| Step | Change | Cheapest valid test | Primary metrics |
|---|---|---|---|
| E1 Ingestion | PDF tier, page markers, document map, tracking-parameter stripping, status field, `thin` flag | Offline replay over the 51 stored PDFs (no paid call); then one Layer 4 domain re-run (Rights or Location) against the frozen Layer 3 | PDF extraction success; opened and readable sources; citation traceability incl. page; unsupported findings |
| E2 Search strategy | Tool descriptions, `include`, `user_location`, normalised hit keys, cache-key normalisation, Layer 4 seeding | One full Layer 4 re-run against the frozen Layer 3 | Duplicate searches; web-search calls; distinct hosts; primary-source share; query scale distribution |
| E3 Prompts and world model | Section 11 wording for the three Layer 4 prompts only | One full Layer 4 re-run against the frozen Layer 3 | External-factor recall; population/employment/investment coverage; distinct root drivers; property-linked vs context-only; generic findings |
| E4 Domain architecture | Baseline stage plus Layer 3 SKILL and synthesis changes | One full Layer 3 + Layer 4 run on the same fact sheet | Layer 3 dependency retention; Tier 1 coverage per scale and topic; tokens, calls, runtime, cost |

Metric definitions:

| Metric | Source | Method |
|---|---|---|
| Layer 3 dependency retention | Domain "Dependencies requiring external research" vs candidate brief and external report | Manual per-item trace (present / partial / lost) as in this audit |
| Layer 4 external-factor recall | Reference list of expected external factors for the asset class, frozen before the run by two reviewers | Fraction found |
| Population, employment, investment coverage | Scale-by-topic grid | Manual covered / partial / absent per cell |
| Distinct external root drivers | Register | Manual grouping (baseline: 34 behind 41 entries) |
| Property-linked vs context-only | Register and Tier 1 sections | Counts as written by the model (baseline: 27 vs 14 "context in disguise") |
| Unsupported or generic findings | Fixed sample (15 entries) | Two reviewers, disagreements recorded |
| Opened and readable sources; PDF extraction success | `sources/index.jsonl` | `canonical_text_available` by content type; extraction status |
| Exact citation traceability | Cited URLs vs `index.jsonl` (page ids after E1) | Script over artifacts, observational only |
| Primary-source proportion | `index.jsonl` hosts classified once | Script |
| Duplicate searches | `queries.jsonl` | Casefolded token-set similarity within run and across the pair |
| Model calls, web-search calls, cached/uncached tokens, runtime, cost | `run.json` | Direct |
| Stakeholder usefulness | Two readers rate Tier 1 and Tier 2 sections for decision relevance without deciding | Questionnaire |
| Manual evidence review | 10 claims per run re-read against stored text | Two reviewers |

Representative set: the current asset (public-sector single-tenant court building) as baseline plus one contrasting public-input-confirmed fact sheet if available. Two assets separate asset-specific from systematic effects. Rollout E1 → E2 → E3 → E4; a full-pair regression only at E4; never combine E3 and E4 in one paid run.

---

## 14. Expected trade-offs

| Dimension | Direction | Basis |
|---|---|---|
| Source coverage | Up: 25 of 26 unreadable Layer 4 files become readable with tier 2 | [Run] text layers present |
| World-model coverage | Up: a baseline ledger covers all scales and topics once; Tier 1 items stop being dropped | [Inf] from the dropped population/employment hits |
| Duplication | Down: seeding removes 66 refetches and up to 22 repeated queries; "do not re-open Layer 3 sources" | [Run] |
| Tokens, Layer 3 | Up by one stage (est. +1–3M) and baseline replay (+8–15k per turn on eight domains, mostly cached) | Observed per-domain range 0.4–3.4M |
| Tokens, Layer 4 | Roughly flat to down: fewer duplicate searches and free re-reads offset baseline input; page-bounded reads keep long documents out of context | [Inf] |
| Cost | Search proxy stays the largest controllable cost (29–39% of tokens); unchanged unless the proxy model changes | [Run] |
| Complexity | One stage record, one prompt file, one extraction module, two schema bumps, seeding at `create_run`, test updates | Repository structure |
| Risk | Baseline drifts generic if its prompt allows commentary; mitigated by "record; do not assess" | Design |

---

## 15. Open questions and assumptions

- **Assumption:** the baseline stage receives all eight routed contexts (about 124 KB, roughly 30k tokens) rather than a Python-selected subset. Fallback if replay cost is high: pass only the Location and Occupier routed contexts (a file selection, not content grading).
- **Open:** `reasoning_effort=high` on the search proxy is run-frozen; the settings default is `low`. Cost, not coverage.
- **Open:** OCR provisioning (RapidOCR via Docling or Tesseract via PyMuPDF) for the one image-only document class; tier 4 ships after tier 2 is measured.
- **Open:** whether statistics APIs (GENESIS/Regionalstatistik REST, Eurostat JSON-stat, Bundesbank SDMX) should be reached through `read_source` on their URL endpoints (already works for CSV/JSON) or left to web search; the source survey found several web UIs are JavaScript shells while the APIs answer.
- **Assumption:** pinned test phrases are updated with the prompts in the same change (listed per prompt in section 11).
- **Open:** hold-period source of truth for the baseline's time bounds; take it from the routed context when present.
- **Audit coverage note:** four domain traces were produced by independent readers; their strongest "lost" claims were re-verified by direct pattern search (all confirmed for Asset, Energy, Location and Occupier: fire-door chronology, "ja, alle ok", grease separator, GEG inspection thresholds, parking counts, solar-readiness, March 2025 road works, Gewerbegebiet Mitte vacancy, area-basis conflict, Einzelplan 05 limitation). The other four domains were traced directly by the author.

---

## 16. Reconciliation with the target architecture

**[Rec]** Where the proposed target architecture already answers a finding of this audit, implement it there rather than twice.

| Finding of this audit | Covered by the target architecture? | Consequence |
|---|---|---|
| PDFs unreadable (section 3) | Yes — a shared document-ingestion service with page references is a named phase | Implement once, in the ingestion design; this audit supplies the measured urgency and the affected record classes |
| Layer 4 re-opens Layer 3 sources; duplicate discovery (section 4.2) | Partly — Layer 4 receives reports and definitions, not the factsheet, and reuses one ingestion service | Still needs the store and query-cache seeding of section 10 and the prompt change of section 11.3 |
| No cross-domain structure in Layer 4 beyond one synthesis (section 9) | Yes — a separate dependency graph is a named deliverable | Adopt the graph; the two-tier split of section 6 then applies to the graph and the synthesis |
| Layer 3 synthesis loses dependency identifiers (section 4.4) | Yes, indirectly — the target design removes the Layer 3 cross-domain synthesis and hands individual reports to Layer 4 | The retention rule of section 11.2 still matters while the current synthesis exists |
| Place and world context never gathered or recorded (sections 4.1, 4.3) | **No** | The baseline stage (section 8) and the Tier 1 output slots (section 11) are additional work under either domain model |
| Search strategy: scale ladder, jurisdiction-native terms, provider options (section 6) | **No** | Applies to the source scout and selector as much as to today's researcher |
| Fixed eight domains versus a reviewed catalogue | Yes — the target design makes the catalogue dynamic | Option C's baseline stage is compatible: it runs once per subject, before the domains, whatever the catalogue contains |

**[Inf]** The baseline stage recommended here becomes easier under the target architecture, not harder: with a subject profile and a reviewed catalogue already in place, the place-and-world ledger has a natural owner and a natural input.

---

## Prioritized implementation plan

| Priority | Change | Files | Python? | Prompt? | Tests |
|---|---|---|---|---|---|
| P0 | PDF text tier (PyMuPDF child process), page markers, document map, `pages`/`find` args, extraction status, `thin` flag, tracking-parameter stripping in `normalize_url` and hit keys | `text_extraction.py`, `sources.py`, `research_tools.py`, `retrieval.py`, `settings.py` | Yes | Tool descriptions only | Add extraction and normalisation tests; existing tool-name pins unchanged |
| P1 | Provider: `include=["web_search_call.action.sources"]`, per-hit snippet slicing or `answer_text` label, `open_page` URL harvest, `user_location` from run config, `tool_choice="required"` after verification | `providers/openai_search.py`, `create_run.py` (freeze location) | Yes | No | Provider parsing tests |
| P2 | Seed Layer 4 `sources/` and `query_cache/` from the Layer 3 run at `create_run`; show "cached" and "0 results" status to the model | `layer4/create_run.py`, `research_tools.py` | Yes | No | Resume and provenance tests |
| P3 | Layer 4 prompt changes (SKILL rule 2/3, stop rules, Tier 1 output; candidates Part A/B; synthesis Tier 1 register) | `layer4/SKILL.md`, `prompts/external_candidates.md`, `prompts/synthesis.md` | No | Yes | Update pinned phrases in `test_layer4.py` |
| P4 | Baseline stage: new prompt, message builder over the routed contexts, stage record before the domains, verbatim save, injection into domain and Layer 4 messages, schema bumps | `layer3/prompts/place_baseline.md`, `prompts.py`, `runner.py`, `create_run.py`, `settings.py`, `layer4/prompts.py`, `layer4/create_run.py` | Yes | Yes | Stage, resume and message tests |
| P5 | Layer 3 prompt changes (rating vs recording split, stop rule, Tier 1 section, dependency scale hints; synthesis Tier 1 and dependency sections) | `layer3/SKILL.md`, `prompts/synthesis.md` | No | Yes | Update pinned phrases in `test_layer3_prompts.py` |
| P6 | Evaluation harness as observational scripts over run artifacts (traceability, duplicates, primary share); no gating | new `docs/` or `tools/` scripts | Yes | No | Script tests |
| Later | OCR tier for image-only pages; optional `allowed_domains` pass; JavaScript rendering flag (default off); cheaper search-proxy model as a separate cost experiment | | | | |

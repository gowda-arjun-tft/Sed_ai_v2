# Document extraction — second opinion and implementation brief

Date: 2026-08-25 · Responds to `260825_Document_Extraction_Architecture_Second_Opinion_ENG.md` ·
Audience: Codex (implementer) · Evidence: repository code, measurements on run
`backup_L3_20260821_182919_b675`, and primary sources listed in §12.

---

## 1. Direct recommendation

**Direct Python integration, but not Docling-first.** A tiered extractor behind one application-owned
interface, beneath the existing `read_source` tool:

| Tier | Engine | Covers | When |
|---|---|---|---|
| 1 | **PyMuPDF text layer** (already installed, v1.28.0) in a child process | **149 / 154 = 96.8%** of the withheld PDFs | Ship first |
| 2 | OCR on flagged pages only (RapidOCR via `docling[rapidocr]`, or Tesseract via PyMuPDF) | 3 scanned + 2 mixed docs; 10 glyph-broken pages | After tier 1 is measured |
| 3 | Docling TableFormer / full Docling on **requested pages only** | Table-dense pages where tier 1 markdown is inadequate | Only if evidence demands |
| — | Docling MCP | — | **Not recommended** for this repository |
| — | docling-serve sidecar (async REST) | — | The correct form of "option C" **if** scale ever demands a service; do not build a custom worker |

Plus one contract that is mandatory regardless of engine: **ingest once, return a document map, let
the agent request pages or search** — see §4.

## 2. Why, for this repository specifically

### 2.1 Measured: the documents do not need ML

All 154 distinct PDFs (173 index records; 19 were the same file under different URLs) opened with
PyMuPDF in memory, read-only, on this machine:

| Metric | Value |
|---|---|
| Parsed / failed / password-protected | 154 / 0 / 0 (14 carry `/Encrypt` with an empty user password — open fine) |
| Wall time, all 154 | **20.5 s → 482 pages/s**; slowest doc 1.11 s (601 pages) |
| Pages | median 32 · p90 187 · max 601 · total 9,888 |
| Est. tokens/doc (chars ÷ 4) | median **15.2k** · p90 103k · max **343k** · total 5.57M |
| Docs > 100 / 300 / 500 pages | 24 / 6 / 3 |
| Docs > 50k / 100k / 200k tokens | 31 / 17 / 4 |
| Text layer present (≤ 20% empty pages) | **149** |
| Mixed (20–80% empty) / scanned (> 80% empty) | 2 / **3** (starweb.hessen.de gazettes 1974, 1985, 1990) |
| Glyph-mapping failures (U+FFFD > 0.2% of chars) | 2 docs, 10 pages (Rechnungshof reports); sporadic `Ausf�hrung`, `� 90 Abs. 2 HBO` elsewhere |
| `find_tables()` sample (40 docs, ≤ 60 pp each) | 412 tables in 26 docs; **11 pages/s with detection** (44× slower than text) |
| Size | median 780 KB · p90 5.8 MB · p99 9.2 MB · max 10.2 MB; 18 docs > 5 MiB; cap-rejection messages present in checkpoints |

Docling's own technical report gives **3.1 s/page on x86 CPU** (1.27 s/page M3 Max, 0.49 s/page on an
L4 GPU). For this corpus that is ~8.5 hours of CPU per run versus 20 seconds, to gain nothing on the
97% that already carry text. Reported footprint: ~1.3 GB venv with torch ≈ 536 MiB, ~506 MiB of
layout+TableFormer models fetched on first run, 3–4 GB RAM spikes (secondary sources — verify locally).

### 2.2 Why not Docling MCP

- Its tool surface (`convert_document_into_docling_document`, `export_docling_document_to_markdown`,
  `is_document_in_local_cache`, `save_docling_document`, authoring/RAG tools) is **agent-facing
  whole-document conversion**. No page selection is documented. That is the exact anti-pattern for a
  343k-token file.
- It answers "how does a model call a converter"; the brief's question is "how does Python prepare
  evidence beneath `read_source`". Wrong layer.
- Remote mode requires docling-serve plus an API key; local mode adds transport, lifecycle and a
  failure surface for a 3-metre hop inside one process.
- The two-tool contract (`search_web`, `read_source`) is pinned by tests and by the design; letting
  the model call MCP tools directly breaks both.

### 2.3 Why not a hand-built worker/service (brief's option C)

docling-serve already **is** that worker: async `POST /v1/convert/{source,file}/async`, poll/websocket/
result endpoints, and options `page_range`, `document_timeout`, `abort_on_error`, `do_ocr`,
`force_ocr`, `ocr_lang`, `table_mode`, `pdf_backend`, `to_formats` (md/json/html/text/doctags/chunks).
If a service is ever justified, adopt it; don't build one.

### 2.4 When MCP/service would become preferable

Any of: (a) more than one worker host or another application needs extraction; (b) OCR volume makes
CPU contention with the research worker measurable; (c) a GPU box exists that the research host is
not. Today: one host, sequential domains, ~150 PDFs/run, 3% OCR — none applies.

## 3. Minimal component and call flow

```
lens / verifier
   │  read_source(url, pages=None, find=None)          ← same two tools, two optional args
   ▼
research_tools._read
   │  SourceStore.record_for_url(url) ──► hit ──────────────────┐
   │  miss: retriever.fetch(url) → SourceStore.store(document)  │
   ▼                                                            │
SourceStore.store                                               │
   │  raw bytes → sources/raw/<aa>/<sha>.bin   (unchanged)      │
   │  application/pdf → extract_pdf(raw_path, out_dir)          │
   │        child process: python -m …pdf_extract_worker        │
   │        timeout, no shared memory with the research worker  │
   │        writes documents/<sha>/manifest.json + pages.jsonl  │
   │  writes sources/text/<sha>.txt (page-marked full text)     │
   │  index.jsonl record += extraction summary                  │
   ▼                                                            ▼
_source_result(store, record, pages, find)  ◄───────────────────┘
   │  small doc → full page-marked text
   │  large doc, no args → DOCUMENT MAP
   │  pages="12-15,40" → bounded page text
   │  find="Brandschutz" → page hits + snippets
   ▼
tool result → lens context  (eviction-safe: bounded by READ_RESPONSE_TOKENS)
```

No new agent, no Layer 2 change, no synthesis change. The coordinator and synthesizer are untouched.

## 4. Large-PDF ingestion and selective-reading contract

### 4.1 Tool signature (backwards compatible)

```python
@tool("read_source", parse_docstring=True)
async def read_source(url: str, pages: str | None = None, find: str | None = None, runtime=...) -> str:
    """Fetch, retain, and read one public source as canonical text.

    Args:
        url: The HTTP or HTTPS source address.
        pages: Optional page selection for long documents, e.g. "3" or "12-15,40".
        find: Optional case-insensitive search term; returns matching pages with snippets.
    """
```

Keep the phrase **"canonical text"** in the description — `tests/test_layer3_harness_core.py:98`
pins it. Tool *names* are pinned in three test files; names do not change.

### 4.2 Response forms

**A. Whole document** — when `est_tokens ≤ READ_RESPONSE_TOKENS` (default 16,000 ≈ median doc ×1):

```
SOURCE <sha>
URL <url>
PAGES 1-34 (complete) · TEXT LAYER 34 · SCANNED 0

[p.1]
…
[p.2]
…
```

**B. Document map** — large document, no `pages`/`find`:

```
SOURCE <sha>
URL <url>
TITLE Hessische Verwaltungsvorschriften Technische Baubestimmungen 2024
PAGES 601 · TEXT LAYER 598 · SCANNED 3 (p.4, p.5, p.9) · EST TOKENS 343,000
TOO LARGE FOR ONE RESPONSE — request pages or search.

OUTLINE
  p.1    Vorwort
  p.3    Inhaltsverzeichnis
  p.13   A 1.2.2 Anforderungen an Planung, Bemessung und Ausführung
  …                                   (PDF bookmarks if present, else first heading-like line per page;
                                       capped at OUTLINE_MAX_LINES=150, grouped into page ranges beyond)
TABLES  p.13, p.14, p.27 … (count only; detection is lazy — see §5.3)

Next: read_source(url, pages="12-15")   or   read_source(url, find="Brandschutz")
```

**C. Page selection** — `pages="12-15,40"`: page-marked text for the requested pages, bounded by
`READ_MAX_PAGES_PER_CALL` (30) **and** `READ_RESPONSE_TOKENS`. If the budget is hit, return what fits
and end with `CONTINUE: read_source(url, pages="16-40")`.

**D. Search** — `find="term"`: case- and diacritic-insensitive substring over `pages.jsonl`; up to
`FIND_MAX_HITS` (40) lines `p.N: …±200 chars…`, plus total hit count. Deterministic — the verifier
reproduces it exactly.

Citations become `SOURCE <sha> p.N`. Because every form is derived from the same persisted
`pages.jsonl`, the citation verifier re-reads the identical text.

### 4.3 Why the budget is mandatory even with compaction

The new context-eviction layer (`layer3/memory.py`) evicts *older* tool results and keeps the most
recent 6 intact. A single 343k-token `read_source` result inside that keep window is **un-evictable**
and alone exceeds the 150k eviction trigger. The response budget is therefore not a guardrail on the
model — the model still chooses freely which pages to read — it is what makes any page readable at all.

### 4.4 Continuing without losing research context

The agent's prior context is untouched: each page request is one more bounded tool result; the map
stays in history (small); evicted page bodies are re-readable from disk at zero cost (§3 hit path).

## 5. Minimum persistent artifact schema

```
sources/
├── raw/<aa>/<sha>.bin                     unchanged — authoritative bytes
├── text/<sha>.txt                         page-marked full text ("[p.N]\n…") — keeps
│                                          canonical_text_available=True and text_sha256 for the verifier
├── documents/<sha>/
│   ├── manifest.json
│   └── pages.jsonl                        one line per page
└── index.jsonl                            record += "extraction": {…summary of manifest…}
```

`manifest.json` (schema 1):

```json
{
  "source_sha256": "…", "schema": 1,
  "extractor": "pymupdf", "extractor_version": "1.28.0",
  "status": "success | partial | failed | needs_password | unsupported",
  "pages": 601, "text_layer_pages": 598, "scanned_pages": [4, 5, 9],
  "replacement_char_pages": [212, 213],
  "est_tokens": 343000,
  "title": "…", "outline": [[1, "Vorwort", 1], [1, "Inhaltsverzeichnis", 3]],
  "errors": [{"page": 77, "error": "…"}],
  "limits_applied": {"max_pages": 2000, "timeout_seconds": 60},
  "extracted_at": "2026-08-25T…Z"
}
```

`pages.jsonl` line: `{"page": 13, "chars": 2140, "source": "text_layer | ocr | none",
"replacement_ratio": 0.0, "text": "…"}`.

**Why this and not Docling JSON:** provenance needed for citation is *page + text*; the verifier
quotes words, not bounding boxes. Docling JSON (bbox, charspan) is only justified if tier 3 is added,
and then it is stored **alongside** for the requested pages, never as the canonical form.

**Cache key = `sha256 + extractor + extractor_version`.** On a version change, re-extract lazily on
next read; never rewrite artifacts in completed runs (stores are per run).

### 5.1 Limits — separated, as the brief asks

| Limit | Setting | Proposed | Rationale |
|---|---|---|---|
| Download bytes, PDF | `PDF_MAX_BYTES` | **50 MiB** | p99 stored = 9.2 MB; rejections observed at 10 MiB; stream to disk, not memory |
| Download bytes, other | `MAX_SOURCE_BYTES` | 10 MiB (unchanged) | HTML never approaches it |
| Pages extracted | `PDF_MAX_PAGES` | 2,000 | beyond → `partial`, first 2,000 kept |
| Extraction wall time | `PDF_EXTRACT_TIMEOUT_SECONDS` | 60 (tier 1) | 601 pp took 1.1 s; budget is for hostile files |
| OCR pages per doc (tier 2) | `OCR_MAX_PAGES` | 60 | only flagged pages |
| One response | `READ_RESPONSE_TOKENS` | 16,000 | ≈ median doc; ~10% of eviction trigger |
| Pages per call | `READ_MAX_PAGES_PER_CALL` | 30 | |
| Find hits | `FIND_MAX_HITS` | 40 | |
| Stored artifacts | none | — | disk is cheap; provenance is not |

Record all of them in `run.json` (a `document_extraction` block, sibling of `limits`, mirroring the
`context_management` precedent).

### 5.2 Store integration (concrete)

- `text_extraction.canonical_text()` keeps its signature; `SourceStore.store()` gains a branch:
  `if media_type == "application/pdf": manifest = extract_pdf(raw_path, documents_dir)`; the
  page-marked text is written to `text/<sha>.txt` so **every existing downstream path works unchanged**.
- `_source_result(store, record, pages, find)` implements forms A–D from `pages.jsonl`.
- `record_for_url` hit path already exists — reuse is free.

### 5.3 Tables

Tier 1 text extraction already renders table cells in reading order; `find_tables()` is **44×
slower** and must not run at ingest. Run it lazily inside form C for the requested pages, cache the
Markdown per page in `pages.jsonl` (`"tables_md": […]`), and only escalate to Docling on evidence.

## 6. Failure handling

| Case | Behaviour | Visible as |
|---|---|---|
| Parser crash / hang | Child process; `subprocess.run(timeout=…)`; kill on expiry | manifest `status: failed`, `errors[]`; tool returns the reason, never raises (as today) |
| Page-level exception | Continue; record `{"page": n, "error": …}` | `status: partial`; page line `"source": "none"` |
| Scanned page (no text) | Flag; tier 2 target | `scanned_pages`, map line `SCANNED 3 (p.…)` |
| Glyph-map failure (U+FFFD) | Flag by ratio > 0.5% per page; tier 2 `force_ocr` target | `replacement_char_pages` |
| Password-protected (`needs_pass`) | Do not attempt cracking | `status: needs_password`; message names it |
| > `PDF_MAX_PAGES` | Extract first N | `status: partial`, `limits_applied` |
| > `PDF_MAX_BYTES` | Refuse before download completes (Content-Length, then streamed count) | today's message, with the new cap |
| Docling/OCR unavailable (tier 2 not installed) | Tier 1 result stands | `source: none` on those pages — never silent |
| Extractor version bump | Lazy re-extract on next read | manifest `extractor_version` |

Nothing here grades, rewrites or repairs model output; all of it describes the *evidence*.

## 7. Security and deployment

- **Untrusted input.** MuPDF/pdfium have historical parser CVEs; pypdf has 2026 DoS CVEs (unbounded
  FlateDecode/XMP allocation) — do **not** use pypdf for untrusted parsing. PyMuPDF **CVE-2026-3029**
  affects only the CLI `embed-extract` path (1.26.5, fixed 1.26.6) — not opening/parsing; installed
  1.28.0 is clear.
- **Isolation.** One child process per document, timeout, no network, no filesystem access beyond
  `raw/<sha>.bin` in and `documents/<sha>/` out. Windows has no RLIMIT/seccomp: rely on timeout +
  page cap; a Job Object memory cap is a later hardening step.
- **Privacy.** Everything local; no external conversion services (LlamaParse, cloud OCR) — raw
  documents never leave the host. If docling-serve is ever adopted, run it on the same host or LAN
  with the API key, and pass a **local path** (shared volume), never re-upload bytes.
- **Dependencies.** `pymupdf` is installed but **not pinned** in `requirements.txt` (which lists only
  4 packages) — pin it. Licence: **AGPL-3.0 / commercial (Artifex)**; Docling is MIT; `pypdfium2`
  (Apache/BSD, shipped with Docling) is the drop-in if AGPL is unacceptable — same page-map design,
  weaker tables. **Decision required from the owner.**
- **Tier 2 facts to encode, not guess.** `docling` 2.121.0 is a metapackage over
  `docling-slim[standard]`; `standard` already includes torch, torchvision, docling-parse,
  docling-ibm-models, pypdfium2 **and rapidocr** (EasyOCR/Tesseract are extras). Default
  `ocr_options = OcrAutoOptions()`; **RapidOcrOptions default `lang = ["chinese"]`** — set
  `["de", "en", "fr"]` explicitly (EasyOCR default `["fr","de","es","en"]`, Tesseract
  `["fra","deu","spa","eng"]`). `document_timeout` → `PARTIAL_SUCCESS` with partial results.
  `page_range` is 1-indexed inclusive, validated `start ≥ 1, end ≥ start`; the last-page bug
  (#1469) closed 2025-08-25. `export_to_markdown(page_no=…)` exists; tables filter by
  `prov[0].page_no`; multi-page tables are a known caveat. Threads: `DOCLING_NUM_THREADS` >
  `OMP_NUM_THREADS`, default 4; device `auto`. Models cache `~/.cache/docling`, override
  `DOCLING_ARTIFACTS_PATH`; prefetch for offline hosts. Table mode default `ACCURATE` (slower).
  Tesseract is **not** on this machine's PATH.

## 8. Staged plan (smallest safe first)

**Stage 1 — text layer, map, pages, find (ship first).** New `layer3/pdf_extraction.py` (pure:
`raw_path, out_dir → manifest`) + `layer3/pdf_extract_worker.py` (child entry point). `SourceStore`
PDF branch; `text/<sha>.txt` page-marked; `read_source(url, pages, find)`; forms A–D; settings +
`run.json` block; pin `pymupdf`. Tests: generate 3 tiny PDFs with PyMuPDF in the test (text, empty
page, 40-page doc) — no fixtures on disk; assert map/pages/find forms, idempotent reuse, timeout →
`failed`, existing tests untouched (tool names, "canonical text" phrase, `MAX_SOURCE_BYTES` patch
point in `test_layer3_global.py:111`).

**Stage 2 — OCR on flagged pages only.** Choose engine (RapidOCR via `docling[rapidocr]`, or
Tesseract via PyMuPDF once installed); explicit `de/en/fr`; `OCR_MAX_PAGES`; page `source: "ocr"`.
Trigger: `scanned_pages ∪ replacement_char_pages`. Measure on the 5 known docs first.

**Stage 3 — tables on demand.** Lazy `find_tables()` per requested page → cached Markdown; evaluate
`pymupdf_layout`/`pymupdf4llm` (same licence family) or Docling TableFormer *for those pages*.

**Stage 4 — formats.** DOCX/PPTX behind the same `extract_document()` interface (python-docx /
python-pptx or Docling); **XLSX separate** (openpyxl; Docling's multi-sheet Markdown export is
lossy). Explicitly unsupported: images (until stage 2), archives, legacy `.doc`, password-protected.

**Stage 5 — only on evidence.** docling-serve sidecar if §2.4 conditions appear.

## 9. Answers to the 24 questions

| # | Answer |
|---|---|
| 1 | Child **process** in the same deployment unit (§3); not MCP; Docling only as a tier |
| 2 | No. docling-mcp has no documented page selection/artifact contract; docling-**serve** does (page_range, timeout, PARTIAL_SUCCESS) |
| 3 | Internal only. Model-visible MCP breaks the two-tool contract and pushes whole documents into context |
| 4 | None today; it would cost transport, auth, lifecycle for a same-host hop |
| 5 | §2.4: multiple hosts/apps, measurable CPU contention, or a remote GPU |
| 6 | §4: map → pages/find → bounded page text; citations `SOURCE p.N` |
| 7 | Document map (title, counts, outline, scanned flags) **plus** the ability to search; not text-search results first — the agent chooses |
| 8 | Each request is one bounded tool result; map stays; evicted bodies re-readable from disk |
| 9 | Per-page `pages.jsonl` + manifest `status: partial`; resume = re-run only pages with `source: none` |
| 10 | Raise PDF cap to 50 MiB; stream to disk; Content-Length pre-check; byte-count during stream |
| 11 | §5.1 table — six separated limits, all recorded in `run.json` |
| 12 | Page-level provenance is sufficient for quotation; Docling `prov[].page_no`/bbox only if tier 3 |
| 13 | Per-page text (jsonl) + page-marked full text; Docling JSON only alongside, on demand |
| 14 | `source: text_layer | ocr | none` per page + `replacement_ratio` |
| 15 | Manifest statuses `partial / failed / needs_password / unsupported` + tool message; never dropped |
| 16 | Cache key includes `extractor_version`; lazy re-extract; completed runs untouched |
| 17 | PDF only in stage 1 — 173/173 withheld sources were PDFs |
| 18 | Yes, XLSX separate (openpyxl) |
| 19 | Images until OCR, archives, legacy `.doc`, encrypted-with-user-password |
| 20 | Child process + timeout + page cap; no network; path-restricted I/O |
| 21 | Same, plus byte caps before parse; avoid pypdf for untrusted input |
| 22 | If serve is adopted: same-host/LAN, API key, `document_timeout`, async poll, shared volume paths |
| 23 | **Local path** to `raw/<sha>.bin` (never re-upload bytes) |
| 24 | No external services; local-only engines; assert no outbound network in the worker |

## 10. Incorrect assumptions and missing concerns in the brief

1. **False dichotomy.** The brief frames "Docling in-process vs Docling MCP". The measured corpus is
   97% text-layer; the missing option — a no-ML text extractor already installed — is the right first
   tier. Docling is a tier, not the foundation.
2. **"500-page planning file, hundreds of thousands of tokens"** is real but rare: 3 of 154 docs
   (2%); median 32 pages / 15k tokens returns whole. Design the map for the tail; don't tax the median.
3. **The 10 MiB cap.** Correct that it rejects useful files (rejections observed), but 0 stored docs
   exceed it by construction and p99 is 9.2 MB — 50 MiB covers everything seen with margin.
4. **Glyph-mapping failures are a third failure mode** (neither scanned nor clean): fonts without a
   ToUnicode map yield U+FFFD (`Ausf�hrung`). Needs per-page ratio flags and `force_ocr` on those
   pages. The brief's "scanned vs embedded text" taxonomy misses it.
5. **Licence is absent from the brief.** PyMuPDF AGPL/commercial vs Docling MIT vs pypdfium2
   Apache/BSD is a product decision that determines the tier-1 engine.
6. **Interaction with context eviction** (new since the brief): one oversized tool result inside the
   keep window is un-evictable → the response budget is structural, not optional (§4.3).
7. **OCR is not "configure a language"** — Docling's default is `OcrAutoOptions` and RapidOCR's
   default language is Chinese; the extra must be installed and languages set explicitly.
8. **Windows host.** No RLIMIT/seccomp; Docling's CPU-only torch instructions are Linux-oriented;
   Tesseract absent. Isolation = process + timeout here.
9. **Dedup is by hash, not URL** — 19 of 173 records were duplicates; the store already keys by sha,
   so extraction must too (it does under §5).
10. **Table detection cost** (44× text) is not mentioned; it must be lazy and page-scoped.
11. **Option C already exists** as docling-serve; the brief proposes building it.

## 11. Verification for Codex

- Unit: generated PDFs (text / empty / 40-page / oversized-pages) → manifest statuses, forms A–D,
  idempotent reuse, timeout → `failed`, `find` diacritic folding (`Brandschutz` ↔ `BRANDSCHUTZ`,
  `Straße` ↔ `strasse`).
- Existing suite unchanged: tool names, `"canonical text"` phrase, `MAX_SOURCE_BYTES` patch point.
- Offline replay: run `extract_pdf` over `backup_L3_20260821_182919_b675/sources/raw/*.bin` (154
  files) and assert 149 `success`, 3 flagged scanned, 2 mixed, 0 `failed`, total < 60 s.
- Live acceptance (costs money — owner's call): one domain; count `read_source` responses of each form;
  confirm page-cited findings appear and "record unavailable" language falls.

## 12. Sources

Repository measurements: `research_tools.py`, `sources.py`, `text_extraction.py`, `settings.py`,
`requirements.txt`; run store `backup_L3_20260821_182919_b675/sources/` (154 PDFs, PyMuPDF 1.28.0).

- Docling `DocumentConverter.convert` reference — https://docling-project.github.io/docling/reference/document_converter/
- Docling pipeline options (source: `OcrAutoOptions` default, `document_timeout` → PARTIAL_SUCCESS, OCR `lang` defaults) — https://raw.githubusercontent.com/docling-project/docling/main/docling/datamodel/pipeline_options.py
- Docling settings (`PageRange` validator, `DocumentLimits`) — https://raw.githubusercontent.com/docling-project/docling/main/docling/datamodel/settings.py
- Docling accelerator options — https://raw.githubusercontent.com/docling-project/docling/main/docling/datamodel/accelerator_options.py
- Docling OCR engines — https://docling-project.github.io/docling/concepts/OCR/
- Docling installation / extras — https://docling-project.github.io/docling/getting_started/installation/
- Docling advanced options (threads, limits, artifacts path, table mode) — https://docling-project.github.io/docling/usage/advanced_options/
- Docling page-specific export (discussion #2744) — https://github.com/docling-project/docling/discussions/2744
- Docling `page_range` last-page bug #1469 (closed 2025-08-25) — https://github.com/docling-project/docling/issues/1469
- Docling technical report (3.1 s/page CPU, 0.49 s/page L4) — https://arxiv.org/html/2408.09869v4
- Docling resource discussions (RAM spikes, threads) — https://github.com/docling-project/docling/issues/2877 · https://github.com/docling-project/docling/discussions/306
- Docling footprint (torch 536 MiB, ~1.3 GB venv; secondary) — https://shekhargulati.com/2025/02/05/reducing-size-of-docling-pytorch-docker-image/
- docling / docling-slim on PyPI (2.121.0, MIT, `standard` includes rapidocr) — https://pypi.org/pypi/docling/json · https://pypi.org/pypi/docling-slim/json
- docling-mcp (tools, transports, env flags, remote mode) — https://github.com/docling-project/docling-mcp
- docling-serve REST API (async endpoints, options) — https://docling-project.github.io/docling/usage/api_server/rest_api/ · https://raw.githubusercontent.com/docling-project/docling-serve/main/docs/usage.md
- PyMuPDF on PyPI (1.28.2, AGPL/commercial) — https://pypi.org/pypi/pymupdf/json
- PyMuPDF4LLM API (`pages`, `page_chunks`, OCR params) — https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/api.html
- CVE-2026-3029 (PyMuPDF `embed-extract` only) — https://www.sentinelone.com/vulnerability-database/cve-2026-3029/
- pypdf 2026 DoS CVEs — https://www.sentinelone.com/vulnerability-database/cve-2026-33123/ · https://www.sentinelone.com/vulnerability-database/cve-2026-41314/

# Document Ingestion Design

Status: **recommended, not implemented** on the main branch · Consolidated 08 September 2026 from the document-extraction brief, its second-opinion response and the plain-language companion of 25 August 2026, with measurements re-confirmed against the runs of 02 September 2026.

How Python turns a downloaded document into quotable evidence beneath the existing `read_source` tool. This is deterministic evidence preparation, not a research agent and not a model-visible service.

---

## 1 · The problem

The research agents work like a library. Every document found on the web is downloaded, hashed and stored in the vault (`sources/raw/`). A readable copy is then placed on the reading-room shelf (`sources/text/`), because agents may only read the copy, never the original bytes.

For web pages the copier works. **For PDFs it does not exist.** The document enters the vault and the shelf receives a note instead:

```text
Stored <sha> (application/pdf, 2481920 bytes). No canonical text is available
for verification; use a readable source or disclose this limitation.
```

The exact code path:

```text
search_web finds an official PDF
  → read_source downloads it
  → bytes stored at sources/raw/<aa>/<sha>.bin
  → canonical_text() receives content type application/pdf
  → canonical_text() returns None
  → no sources/text/<sha>.txt is written
  → the agent cannot read, quote or verify the document
```

German official records — development plans, budgets, gazettes, parliamentary papers, market reports — are almost all PDFs. So the agents write "record unavailable" for precisely the documents that hold the answers. No prompt can fix a document the agent never saw.

The missing component belongs inside the `read_source` evidence-preparation path. It is not a new research agent, a Layer 2 stage, a risk-classification stage or a synthesis stage.

---

## 2 · Measured evidence

**August 2026 corpus (154 distinct PDFs from one Layer 3 run), opened read-only with PyMuPDF:**

| Metric | Value |
| --- | --- |
| Parsed / failed / password-protected | 154 / 0 / 0 (14 carry `/Encrypt` with an empty user password and open fine) |
| Wall time, all 154 | 20.5 s → **482 pages/s**; slowest document 1.11 s for 601 pages |
| Pages | median 32 · p90 187 · max 601 · total 9,888 |
| Estimated tokens per document | median **15.2k** · p90 103k · max **343k** · total 5.57M |
| Documents over 100 / 300 / 500 pages | 24 / 6 / 3 |
| Documents over 50k / 100k / 200k tokens | 31 / 17 / 4 |
| Text layer present (≤ 20% empty pages) | **149 of 154 (96.8%)** |
| Mixed (20–80% empty) / scanned (> 80% empty) | 2 / **3** (state gazettes from 1974, 1985, 1990) |
| Glyph-mapping failures (U+FFFD > 0.2% of characters) | 2 documents, 10 pages; sporadic elsewhere |
| Tables (`find_tables()` on 40 documents) | 412 tables in 26 documents; **11 pages/s with detection — 44× slower than text** |
| Size | median 780 KB · p90 5.8 MB · p99 9.2 MB · max 10.2 MB; 18 documents over 5 MiB; cap rejections observed |

**September 2026 re-confirmation.** In the run pair `L3_20260902_120424_e0de` / `L4_20260902_132142_bb9f`, every source stored without canonical text was an `application/pdf` record: 26 distinct files in Layer 3 and 25 in Layer 4. All begin with `%PDF-`, none is encrypted, and all but one carry an extractable text layer (1,414 to 654,568 characters). The single exception is one image-only 1985 gazette scan. The affected documents include the municipal property-market report, the transport planning decision, development plans and their justifications, parking and fee by-laws, the municipal participation report, the state justice budget chapter and the chamber-of-commerce market report — that is, the primary local records the research most needs.

Two conclusions follow directly:

1. **About 97% of the problem needs no machine learning.** A plain text reader solves it, and one is already installed. For comparison, Docling's own technical report gives 3.1 s/page on x86 CPU (1.27 s/page on an M3 Max, 0.49 s/page on an L4 GPU). For this corpus that is roughly 8.5 CPU-hours per run versus 20 seconds, to gain nothing on the documents that already carry text.
2. **The large-PDF fear is real but rare** — 2% of documents. It needs a rule ("never hand over the whole book; give a map and let the agent ask for pages"), not a heavier engine.

---

## 3 · Recommendation: a tiered extractor behind one interface

Direct Python integration, but not Docling-first. One application-owned interface beneath `read_source`:

| Tier | Engine | Covers | When |
| --- | --- | --- | --- |
| 1 | **PyMuPDF text layer** (installed, 1.28.0) in a child process | 149 / 154 = **96.8%** of withheld PDFs | Ship first |
| 2 | OCR on flagged pages only (RapidOCR via `docling[rapidocr]`, or Tesseract via PyMuPDF) | 3 scanned + 2 mixed documents; 10 glyph-broken pages | After tier 1 is measured |
| 3 | Docling TableFormer or full Docling on **requested pages only** | Table-dense pages where tier-1 Markdown is inadequate | Only if evidence demands |
| — | Docling MCP | — | **Not recommended** here |
| — | docling-serve sidecar (async REST) | — | The correct form of a service **if** scale ever demands one; do not build a custom worker |

One contract is mandatory regardless of engine: **ingest once, return a document map, let the agent request pages or search.**

### Why not the alternatives

- **Docling as the first engine.** Excellent but heavy: roughly 1.3 GB of install (PyTorch alone ~536 MB), ~500 MB of models fetched on first use, 3–4 GB RAM spikes, and about 3 s/page on CPU. The 601-page document takes ~1 second with the plain reader versus ~30 minutes with Docling. Paying that for the 97% that need no OCR is the wrong trade. Docling earns its place later, for the scanned remainder and for difficult tables, as a tier behind the same door rather than the door itself.
- **Docling MCP.** Its tool surface is agent-facing whole-document conversion with no documented page selection — the exact anti-pattern for a 343k-token file. It answers "how does a model call a converter", while the question here is "how does Python prepare evidence beneath `read_source`". Making it model-visible would also break the two-tool contract that the tests and the design pin.
- **A hand-built worker or service.** docling-serve already is that worker, with async convert endpoints and `page_range`, `document_timeout`, `abort_on_error`, `do_ocr`, `force_ocr`, `ocr_lang`, `table_mode`, `pdf_backend` and multiple output formats. If a service is ever justified, adopt it; do not build one.
- **When a service would become preferable.** Any of: more than one worker host or another application needs extraction; OCR volume makes CPU contention with the research worker measurable; a GPU host exists that the research host is not. None applies to one host, sequential domains, ~150 PDFs per run and 3% OCR.

---

## 4 · The `read_source` contract

The tool keeps its name and its evidence role, and gains two optional arguments:

```python
@tool("read_source", parse_docstring=True)
async def read_source(url: str, pages: str | None = None,
                      find: str | None = None, runtime=...) -> str:
    """Open one public URL and return retained canonical text with its source ID.

    Args:
        url: The HTTP or HTTPS source address.
        pages: Optional page selection for long documents, e.g. "3" or "12-15,40".
        find: Optional case-insensitive search term; returns matching pages with snippets.
    """
```

The phrase "canonical text" stays in the description because a harness test pins it. Tool names are pinned in three test files and do not change.

**Response forms**

- **A · Whole document** when estimated tokens ≤ the response budget: header (`SOURCE`, `URL`, page counts, text-layer and scanned counts) followed by `[p.N]`-marked page text.
- **B · Document map** for a large document with no `pages`/`find`: title, page count, text-layer and scanned page numbers, estimated tokens, an outline (PDF bookmarks where present, otherwise the first heading-like line per page, capped and grouped into ranges beyond the cap), the pages where tables were detected, and a closing line naming the next call.
- **C · Requested pages**: bounded page text for `pages="12-15,40"`, with the same page markers.
- **D · Find**: matching pages with snippets, capped at a hit limit, with diacritic-folded matching.

Findings then cite `SOURCE <id> p.12`, and a reviewer can re-read the same page to check the quote.

---

## 5 · Persistent artifacts

```text
sources/
├── raw/<aa>/<sha>.bin            unchanged — authoritative bytes
├── text/<sha>.txt                page-marked full text ("[p.N]\n…"), so
│                                 canonical_text_available and text_sha256 stay meaningful
├── documents/<sha>/
│   ├── manifest.json
│   └── pages.jsonl               one line per page
└── index.jsonl                   record += "extraction": { …manifest summary… }
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

A `pages.jsonl` line: `{"page": 13, "chars": 2140, "source": "text_layer | ocr | none", "replacement_ratio": 0.0, "text": "…"}`.

**Why this and not Docling JSON.** The provenance needed for citation is page plus text; a reviewer quotes words, not bounding boxes. Docling JSON (bbox, charspan) is justified only if tier 3 is added, and then it is stored alongside for the requested pages, never as the canonical form.

**Cache key = `sha256 + extractor + extractor_version`.** On a version change, re-extract lazily on the next read; never rewrite artifacts in completed runs, since stores are per run. Deduplication is by hash, not URL: 19 of 173 records in the measured run were the same file under different URLs, and the store already keys by hash.

### Store integration

- `canonical_text()` keeps its signature. `SourceStore.store()` gains one branch: for `application/pdf`, call the extractor and write the page-marked text to `text/<sha>.txt`, so every existing downstream path keeps working unchanged.
- `_source_result(store, record, pages, find)` implements forms A–D from `pages.jsonl`.
- The `record_for_url` hit path already exists; reuse is free.

### Tables

Tier-1 text extraction already renders table cells in reading order. `find_tables()` is 44× slower and must not run at ingest. Run it lazily inside form C for the requested pages, cache the Markdown per page in `pages.jsonl`, and escalate to Docling only on evidence.

---

## 6 · Limits, separated

| Limit | Setting | Proposed | Rationale |
| --- | --- | --- | --- |
| Download bytes, PDF | `PDF_MAX_BYTES` | **50 MiB** | p99 stored = 9.2 MB; rejections observed at 10 MiB; stream to disk, not memory |
| Download bytes, other | `MAX_SOURCE_BYTES` | 10 MiB (unchanged) | HTML never approaches it |
| Pages extracted | `PDF_MAX_PAGES` | 2,000 | beyond → `partial`, first 2,000 kept |
| Extraction wall time | `PDF_EXTRACT_TIMEOUT_SECONDS` | 60 (tier 1) | 601 pages took 1.1 s; the budget is for hostile files |
| OCR pages per document (tier 2) | `OCR_MAX_PAGES` | 60 | flagged pages only |
| One response | `READ_RESPONSE_TOKENS` | 16,000 | ≈ the median document; ~10% of the eviction trigger |
| Pages per call | `READ_MAX_PAGES_PER_CALL` | 30 | |
| Find hits | `FIND_MAX_HITS` | 40 | |
| Stored artifacts | none | — | disk is cheap; provenance is not |

Record all of them in `run.json` as a `document_extraction` block, a sibling of `limits`, mirroring the `context_management` precedent.

**Why the response budget is structural, not optional.** Layer 3 replaces the framework filesystem middleware, so Deep Agents' own 20k-token tool-result offloading is inactive. One oversized tool result inside the eviction keep-window cannot be evicted. The tool must therefore bound its own output.

---

## 7 · Failure handling

| Case | Behaviour | Visible as |
| --- | --- | --- |
| Parser crash or hang | Child process with a timeout; kill on expiry | manifest `status: failed`, `errors[]`; the tool returns the reason and never raises |
| Page-level exception | Continue; record `{"page": n, "error": …}` | `status: partial`; page line `"source": "none"` |
| Scanned page (no text) | Flag as a tier-2 target | `scanned_pages`; map line names the pages |
| Glyph-map failure (U+FFFD) | Flag by ratio per page; `force_ocr` target | `replacement_char_pages` |
| Password-protected | Do not attempt to bypass | `status: needs_password`; the message names it |
| Over `PDF_MAX_PAGES` | Extract the first N | `status: partial`, `limits_applied` |
| Over `PDF_MAX_BYTES` | Refuse before the download completes (`Content-Length`, then streamed count) | today's message with the new cap |
| OCR tier not installed | Tier-1 result stands | `source: none` on those pages — never silent |
| Extractor version bump | Lazy re-extract on next read | manifest `extractor_version` |

Nothing here grades, rewrites or repairs model output; all of it describes the evidence.

---

## 8 · Security, privacy and dependencies

- **Untrusted input.** MuPDF and pdfium have historical parser CVEs; pypdf has 2026 denial-of-service CVEs (unbounded FlateDecode/XMP allocation) — do not use pypdf for untrusted parsing. PyMuPDF CVE-2026-3029 affects only the CLI `embed-extract` path (1.26.5, fixed 1.26.6), not opening or parsing; the installed 1.28.0 is clear.
- **Isolation.** One child process per document, with a timeout, no network, and no filesystem access beyond `raw/<sha>.bin` in and `documents/<sha>/` out. Windows has no RLIMIT or seccomp: rely on the timeout plus the page cap; a Job Object memory cap is a later hardening step.
- **Privacy.** Everything local. No external conversion services, so raw documents never leave the host. If docling-serve is ever adopted, run it on the same host or LAN with an API key and pass a local path over a shared volume — never re-upload bytes.
- **Dependencies.** `pymupdf` is installed but not pinned in `requirements.txt`; pin it.
- **Tier-2 facts to encode rather than guess.** `docling` 2.121.0 is a metapackage over `docling-slim[standard]`, and `standard` already includes torch, torchvision, docling-parse, docling-ibm-models, pypdfium2 and rapidocr (EasyOCR and Tesseract are extras). The default `ocr_options` is `OcrAutoOptions()`, and **RapidOCR's default language is Chinese** — set the expected languages explicitly. `document_timeout` yields `PARTIAL_SUCCESS` with partial results. `page_range` is 1-indexed inclusive. Threads come from `DOCLING_NUM_THREADS` before `OMP_NUM_THREADS`, default 4; models cache under `~/.cache/docling`, overridable, and should be prefetched for offline hosts. Table mode defaults to the slower accurate model. Tesseract is not on this machine's PATH.

---

## 9 · Staged plan

1. **Text layer, map, pages, find — ship first.** A pure extraction module (`raw_path, out_dir → manifest`) plus a child-process entry point; the `SourceStore` PDF branch; page-marked `text/<sha>.txt`; `read_source(url, pages, find)` with forms A–D; settings and the `run.json` block; pin `pymupdf`. Tests generate small PDFs in-process (text, empty page, multi-page) rather than committing fixtures, and assert the map, pages and find forms, idempotent reuse, and timeout → `failed`, while existing tests stay untouched.
2. **OCR on flagged pages only.** Choose the engine, set languages explicitly, cap OCR pages, and mark page `source: "ocr"`. Trigger on scanned pages plus glyph-failure pages. Measure on the five known documents first.
3. **Tables on demand.** Lazy per-page table detection cached as Markdown; evaluate a layout-aware PyMuPDF variant or Docling TableFormer for those pages only.
4. **More formats.** DOCX and PPTX behind the same interface; spreadsheets handled separately, since multi-sheet Markdown export is lossy. Explicitly unsupported for now: images (until tier 2), archives, legacy `.doc`, and password-protected files.
5. **A service, only on evidence.** docling-serve if the conditions in section 3 appear.

---

## 10 · Decisions required from the owner

1. **Licence.** PyMuPDF is dual-licensed AGPL-3.0 or commercial (Artifex). For an internal tool this is usually acceptable; for a product sold or offered as a service it is a legal decision. Docling is MIT. If AGPL is unacceptable, tier 1 uses `pypdfium2` (Apache/BSD, ships with Docling) instead — slightly weaker on tables, same page-map design.
2. **PDF download cap.** 50 MiB is proposed; the largest stored file measured 10.2 MB and p99 was 9.2 MB.
3. **When to add OCR.** 3% of documents need it today. Recommended: ship tier 1, measure, then decide.

---

## 11 · Verification

- **Unit.** Generated PDFs (text, empty, multi-page, over-page-cap) → manifest statuses, response forms A–D, idempotent reuse, timeout → `failed`, and diacritic-folded `find` matching.
- **Existing suite unchanged.** Tool names, the "canonical text" phrase, and the source-byte-cap patch point.
- **Offline replay.** Run the extractor over the stored `sources/raw/*.bin` of an archived run and assert the expected success, scanned and mixed counts with zero failures, within the time budget. This costs nothing and is the correct first gate.
- **Live acceptance** (costs money, owner's call). One domain; count `read_source` responses of each form; confirm page-cited findings appear and that "record unavailable" language falls.

---

## 12 · What changes, and what does not

**Changes**

- PDFs become readable. Expect fewer "record unavailable" findings and more page-cited facts from official documents — on the evidence above, the single largest remaining quality lever, larger than any prompt change.
- Findings cite source id plus page number.
- The download cap rises for PDFs, since useful files were rejected by the 10 MiB limit.

**Unchanged**

- The agents still have only `search_web` and `read_source`. The map, pages and find behaviour lives inside `read_source` as optional arguments.
- Original bytes remain the authoritative artifact.
- Nothing grades, rewrites or repairs what the model writes.
- Completed run folders are untouched.

> Store every page once, hand the agent a map, let it ask for pages. Everything else is a tier.

---

## 13 · Sources

Repository measurements: `research_tools.py`, `sources.py`, `text_extraction.py`, `settings.py`, `requirements.txt`; the archived run store of 21 August 2026 (154 PDFs, PyMuPDF 1.28.0); the run pair of 02 September 2026 (51 distinct unreadable PDFs, re-measured 03 September 2026).

- Docling `DocumentConverter.convert` reference — https://docling-project.github.io/docling/reference/document_converter/
- Docling pipeline options (`OcrAutoOptions` default, `document_timeout`, OCR language defaults) — https://raw.githubusercontent.com/docling-project/docling/main/docling/datamodel/pipeline_options.py
- Docling settings (`PageRange` validator, `DocumentLimits`) — https://raw.githubusercontent.com/docling-project/docling/main/docling/datamodel/settings.py
- Docling accelerator options — https://raw.githubusercontent.com/docling-project/docling/main/docling/datamodel/accelerator_options.py
- Docling OCR engines — https://docling-project.github.io/docling/concepts/OCR/
- Docling installation and extras — https://docling-project.github.io/docling/getting_started/installation/
- Docling advanced options (threads, limits, artifacts path, table mode) — https://docling-project.github.io/docling/usage/advanced_options/
- Docling page-specific export — https://github.com/docling-project/docling/discussions/2744
- Docling `page_range` last-page issue (closed 2025-08-25) — https://github.com/docling-project/docling/issues/1469
- Docling technical report (3.1 s/page CPU, 0.49 s/page L4) — https://arxiv.org/html/2408.09869v4
- Docling resource discussions (RAM spikes, threads) — https://github.com/docling-project/docling/issues/2877 · https://github.com/docling-project/docling/discussions/306
- docling and docling-slim on PyPI (2.121.0, MIT, `standard` includes rapidocr) — https://pypi.org/pypi/docling/json · https://pypi.org/pypi/docling-slim/json
- docling-mcp (tools, transports, remote mode) — https://github.com/docling-project/docling-mcp
- docling-serve REST API — https://docling-project.github.io/docling/usage/api_server/rest_api/
- PyMuPDF on PyPI (AGPL/commercial) — https://pypi.org/pypi/pymupdf/json
- PyMuPDF4LLM API (`pages`, `page_chunks`, OCR parameters) — https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/api.html
- CVE-2026-3029 (PyMuPDF `embed-extract` only) — https://www.sentinelone.com/vulnerability-database/cve-2026-3029/
- pypdf 2026 denial-of-service CVEs — https://www.sentinelone.com/vulnerability-database/cve-2026-33123/ · https://www.sentinelone.com/vulnerability-database/cve-2026-41314/

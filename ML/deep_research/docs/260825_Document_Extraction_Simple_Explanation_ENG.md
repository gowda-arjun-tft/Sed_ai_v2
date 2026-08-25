# Document extraction — the simple explanation

Date: 2026-08-25 · Companion to `260825_Document_Extraction_Second_Opinion_Response_ENG.md` (the
technical brief for Codex). This file is for you; the other one is for the implementer.

---

## 1. The problem in one picture

Imagine the research agents work in a **library**. Every document they find on the web is bought,
stamped with a serial number and put in the vault (`sources/raw/`). Then a **photocopy** is made and
put on the reading-room shelf (`sources/text/`), because the agents may only read photocopies, never
the originals.

For web pages, the photocopier works. For **PDFs it does not exist**. The book goes into the vault,
and the reading-room shelf gets a note: *"Stored 2,481,920 bytes. No readable copy available;
disclose this limitation."*

That is exactly what happened in your last big run: **173 PDFs were fetched, paid for, stored — and
none was ever read.** German official documents (Bebauungspläne, Haushaltspläne, Landtag papers,
Amtsblätter) are almost all PDFs. So the agents wrote "no data" for the very documents that hold the
answers. No prompt can fix a document the agent never saw.

## 2. What the brief asked

Your brief (`260825_Document_Extraction_Architecture_Second_Opinion_ENG.md`) asks: should the
photocopier be

- **A** — a machine we install inside our own building (Docling library, in-process),
- **B** — a courier service we phone (Docling MCP server), or
- **C** — a separate copy shop with a counter (worker/service)?

## 3. What I found by actually measuring your PDFs

Before choosing a machine, I checked what the books look like. I ran a reader that is **already
installed on your machine** (PyMuPDF 1.28) over all 154 distinct PDFs from the run. Read-only, no
model calls, 20 seconds total.

| Question | Answer |
|---|---|
| Can they be opened? | **154 of 154.** Zero failures, zero password-protected |
| Do they already contain real text (no OCR needed)? | **149 of 154 — 97%** |
| Scanned images only (OCR needed)? | **3** (old Hessian gazettes from 1974–1990) plus 2 partly scanned |
| How big are they? | median **32 pages / ~15k tokens** — fits in one response |
| The scary tail | **3 documents over 500 pages**, largest 601 pages ≈ **343k tokens** |
| Speed of the plain reader | **482 pages per second** — the 601-page monster took 1.1 s |
| Tables? | The plain reader found **412 tables in 26 of 40** sampled docs, readable as Markdown |
| Hidden defect | 2 docs (10 pages) have broken letters (`Ausf�hrung`) — the PDF's font map is bad, not our reader |

Two conclusions fall straight out of this:

1. **97% of the problem needs no artificial intelligence at all.** A plain text reader solves it,
   and it is already installed. Docling is a forklift; most of these are paperbacks.
2. **The "500-page PDF" fear is real but rare** — 2% of documents. It needs a rule ("never hand the
   whole book over; give a table of contents and let the agent ask for pages"), not a bigger machine.

## 4. The recommendation, in plain words

**Install the simple photocopier inside the building now. Keep the forklift in the shed for later.**

- **Step 1 (now):** PDF → page-numbered photocopy using the reader you already have. Every page is
  stored once, forever, under the document's serial number. Extraction runs in a **separate small
  process**, so a malicious or broken PDF can crash *that* process, never the research run.
- **The table-of-contents rule:** when an agent asks to read a big document, it first receives a
  **map** — title, page count, headings per page, which pages are scanned — and then asks for the
  pages it needs (`pages="12-15"`) or searches inside it (`find="Brandschutz"`). Small documents are
  still returned whole. Findings then cite **source + page number**, and the verifier re-reads the
  same page to check the quote.
- **Step 2 (later):** OCR for the 3% scanned pages and the broken-letter pages, only on those pages.
- **Step 3 (only if needed):** Docling's table model on pages the agent actually requests.

## 5. Why not the other two options

**Why not Docling MCP (the courier)?** A courier makes sense when the copy shop is across town and
many offices use it. Here there is one building, one office, and the shop would be **three metres
away**. The courier adds a phone line, a contract (authentication), a queue, and a new way to fail —
and the Docling MCP server's tools convert *whole* documents to Markdown for the model, with **no
page selection**, which is precisely the thing we must not do with a 601-page file. It answers a
different question ("how does a model call a tool") than the one you have ("how does Python prepare
evidence").

**Why not Docling as the first machine?** It is excellent — but heavy: about **1.3 GB** of install
(PyTorch alone ~536 MB), ~500 MB of models downloaded on first use, **3–4 GB RAM spikes**, and
roughly **3 seconds per page on CPU** (Docling's own technical report). Your 601-page file: ~1 second
with the plain reader vs ~30 minutes with Docling. Paying that for the 97% that need no AI is the
wrong trade. Docling earns its place later, for the scanned 3% and for difficult tables — as one
tier behind the same door, not as the door.

## 6. What changes for you, and what does not

**Changes**
- PDFs become readable. Expect fewer "no data / record unavailable" findings and more page-cited
  facts from official documents — the single biggest quality lever left, bigger than any prompt.
- Findings cite `SOURCE <id> p.12`.
- The 10 MiB download cap rises for PDFs (some useful files were rejected by it).

**Stays exactly the same**
- The agents still have only two tools: `search_web` and `read_source`. The map/pages/find behaviour
  lives *inside* `read_source` as optional arguments.
- Original bytes stay the authoritative artifact.
- Nothing grades, rewrites or repairs what the model writes.
- Old run folders are untouched.

## 7. Three decisions only you can make

1. **Licence.** PyMuPDF is dual-licensed: **AGPL-3.0** (free) or a commercial licence from Artifex.
   For an internal tool this is usually fine; for a product sold or offered as a service it is a
   legal decision. Docling is MIT. If AGPL is unacceptable, Step 1 uses `pypdfium2` (Apache/BSD,
   comes with Docling) instead — slightly less capable on tables, same page-map design.
2. **Download cap for PDFs.** I propose 50 MiB (your largest stored file was 10.2 MB; p99 = 9.2 MB).
3. **When to do OCR.** 3% of documents today. My advice: ship Step 1, measure, then decide.

## 8. The one thing to remember

> The archive was never the conversation, and the reader is not the intelligence.
> Store every page once, hand the agent a map, let it ask for pages. Everything else is a tier.

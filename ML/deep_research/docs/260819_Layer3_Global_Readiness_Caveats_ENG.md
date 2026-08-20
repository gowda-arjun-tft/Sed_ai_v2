# Layer 3 — global readiness caveats and how to fix them

**Status:** audit finding, 2026-08-19. Layer 3 is built and passes its own checks. This document
lists what stops it working outside one country, and what to do about each item.

---

## The governing principle

**This module researches property anywhere in the world. It is not a German system, not a European
system, and not an English-language system.**

Every rule written into the code must hold in Tokyo, São Paulo, Riyadh, Warsaw, Mumbai and Lagos as
well as Frankfurt. Where a rule cannot hold everywhere, it must be **data the model supplies for the
property at hand**, never a pattern typed into a Python file.

The test to apply to any line of code: *would this still be true if the property were in a country I
have not thought about?* If the answer is no, that line is a defect.

---

## First, in plain words: what "PDFs cannot be cited" means

Three things happen when a researcher finds a source:

1. **Fetch** — download the page and keep an exact copy.
2. **Read** — turn it into plain text so a quote can be checked.
3. **Cite** — quote it, and the code verifies that quote really appears in the stored text.

Step 3 only works for HTML and plain text. For a PDF, step 2 returns nothing, so step 3 raises
`binary sources cannot support citations in Layer 3 v1` (`sources.py:163`).

**Why this matters more than it sounds.** The most trustworthy sources — what the design calls
Tier 1, the official ones — are almost always PDFs. Land registry extracts, zoning plans, energy
certificates, court filings, government gazettes, statistical yearbooks. That is true in Germany, and
it is equally true in Japan, Brazil and India.

So today the system can *download* the best evidence and then **cannot use it**. The researcher is
pushed down to Tier 3 and Tier 4 — news articles and interested parties — not because better sources
were unavailable, but because the code cannot read the format they come in. The output looks
complete. It is quietly built on weaker evidence than was actually found.

---

## The caveats

### 1 · The privacy guard is hard-coded to one country — and it fails both ways

`ML/deep_research/layer3/egress.py:7-11`

```python
_MONEY    = re.compile(r"(?i)(?:\bEUR\b|€)\s*[\d.,]+")
_POSTCODE = re.compile(r"\b\d{5}\b")
_STREET   = re.compile(r"(?i)\b[A-ZÄÖÜ][\wÄÖÜäöüß.-]+(?:straße|strasse|str\.|weg|allee|platz)\s+\d+[a-z]?\b")
```

This code decides what may leave the building in a web search. It is supposed to stop the tenant's
name, the rent, the valuation and the exact address reaching a search engine.

**Measured behaviour** (run against the live function):

| Query | Result | Should be |
|---|---|---|
| `office rent benchmarks 35000 sqm region` | **BLOCKED** — "protected postcode" | allowed |
| `DIN 18960 12500 sqm` | **BLOCKED** — "protected postcode" | allowed |
| `flood risk 10115 Berlin` | **BLOCKED** — "protected postcode" | allowed |
| `rent 4.200 EUR per month` | **ALLOWED** | blocked |
| `office price 500 USD psf` | **ALLOWED** | blocked |
| `Tokyo 100-0001 zoning` | **ALLOWED** | blocked |

It blocks ordinary research questions because any five-digit number looks like a German postcode, and
it lets confidential figures through because they are written in a format it does not recognise —
including the commonest German money format, `4.200 EUR`, since the pattern requires the currency to
come first.

**Outside Germany it is worse than useless.** It has no concept of a UK postcode (`SW1A 1AA`), a
Canadian one (`M5V 3L9`), a Japanese one (`100-0001`), a Brazilian CEP or an Indian PIN. It knows
`Straße` and `Allee` but not `Street`, `Rue`, `Calle`, `Via`, `丁目` or `Marg`. It knows `EUR` and
`€` but not `USD`, `GBP`, `JPY`, `CHF`, `INR`, `BRL`, `AED` or any of the ~180 other currencies.

**Fix.** Delete all three patterns. Replace with two layers:

- **Deterministic backstop, keep as-is** — the exact-literal loop at `egress.py:32-34`. It blocks any
  string that literally appears in this property's own facts. That is country-neutral by
  construction, because the literals come from the property, not from a pattern.
- **Judgement layer, new** — a cheap structured model call before each query:
  `QueryClearance(allowed: bool, leaked_fields: list[str], reason: str)` via `response_format`. The
  model is told which fields of *this* mission are confidential and decides whether the query leaks
  any of them. It handles every currency, address form and postcode format without a table, because
  it reasons about the actual mission rather than matching a pattern.

Both layers log every query either way, so the audit trail is unchanged.

---

### 2 · Filenames destroy every non-Latin script

`ML/deep_research/layer2/fs.py:15-19` — `slug()`, used across Layer 3 to build every directory and
filename, and applied to **model-supplied** names at `write_answers.py:137,157,190`.

```python
value = text.casefold().replace("&", " and ")
return re.sub(r"[^a-z0-9]+", "-", value).strip("-")
```

Anything that is not `a-z` or `0-9` becomes a hyphen. **Measured:**

| Input | Output |
|---|---|
| `Bauträger-Risiko` | `bautr-ger-risiko` |
| `Marché & valorisation` | `march-and-valorisation` |
| `建筑条件` (Chinese) | `''` — **empty** |
| `Экономика` (Russian) | `''` — **empty** |
| `التخطيط` (Arabic) | `''` — **empty** |
| `Ενέργεια` (Greek) | `''` — **empty** |

An empty slug is not a cosmetic problem. It produces an empty filename, collides with any other
empty slug, and at `write_answers.py:137` the guard `not slug(name)` causes the sixth researcher to
be **silently discarded with no log line**. A Chinese or Arabic lens name cannot exist in this system.

**Fix.** Two changes, both small:

- Normalise with `unicodedata.normalize("NFKD", ...)` and strip combining marks first, so `ä → a`,
  `é → e`, `ø → o`. That fixes every Latin-script language at a stroke.
- For scripts with no Latin form, fall back to a short hash of the original name rather than an empty
  string — `f"lens-{text_hash(name)[:8]}"` — and keep the original name in the register and the
  report. Filenames stay ASCII-safe; the human-readable name is never lost.

Then make the empty-slug case an explicit error, not a silent `continue`.

---

### 3 · Only UTF-8 pages are read correctly

`ML/deep_research/layer3/sources.py:47-48` — when a page does not declare its character set, the code
assumes UTF-8.

That assumption fails across most of the world:

| Region | Common encoding |
|---|---|
| Western Europe | ISO-8859-1 / windows-1252 |
| Central Europe | ISO-8859-2 / windows-1250 |
| Russia, Ukraine | windows-1251 / KOI8-R |
| Greece | ISO-8859-7 |
| Israel | windows-1255 |
| Arabic-speaking | windows-1256 |
| Japan | Shift-JIS / EUC-JP |
| China | GB2312 / GBK / GB18030 |
| Taiwan, Hong Kong | Big5 |
| Korea | EUC-KR |

The failure is silent and it is the worst kind. The page decodes with replacement characters, the
model reads the mangled text, quotes it, and then `record_citation` (`sources.py:165-167`) rejects the
quote as "absent from canonical source text". **The researcher sees an unexplained citation failure
on exactly the official local-language sources that matter most**, and falls back to an
English-language secondary source instead.

**Fix.** Detect the encoding rather than assume it, in this order: the HTTP `Content-Type` header →
the HTML `<meta charset>` declaration → a byte-order mark → statistical detection → UTF-8 as the last
resort. Record the encoding actually used in `index.jsonl` so a failed citation can be diagnosed.
Also replace the hand-rolled `charset=` regex with `email.message.Message`, which parses the header
correctly.

---

### 4 · Official documents cannot be cited (the PDF problem)

`ML/deep_research/layer3/sources.py:163-164`. Explained in plain words above.

**Fix.** Extract text from PDFs so `canonical_text` returns something for
`application/pdf`. This needs one dependency — the repo has none for this today. Until it exists,
make the limitation loud instead of silent: when a researcher fetches a PDF, tell it in the tool
response that this source cannot be cited and why, so it can look for an HTML equivalent rather than
discovering the failure at citation time.

Beyond PDF, the same applies to the office formats that registries and municipalities publish in —
`.docx`, `.xlsx`. Treat the extractable set as a configuration, not as two hard-coded `if` branches.

---

### 5 · Tables collapse into unreadable lines

`ML/deep_research/layer3/sources.py:29-38`. The HTML text extractor emits a newline for `<tr>` but
nothing for `<td>`, so every cell in a row runs together with no separator.

Rent rolls, cost schedules, tariff tables, statistical series — the numeric evidence this module
exists to find — arrive as one unbroken string. The model then quotes what it believes it read, and
the exact-match citation check rejects it.

This is not country-specific, but it compounds every item above: it removes the numeric evidence at
the same time encoding problems remove the local-language evidence.

**Fix.** Emit a separator (a tab or ` | `) on `<td>`/`<th>` boundaries, and a newline on `</tr>`.
Small change, disproportionate gain.

---

### 6 · No language policy anywhere

Nothing in the code or the prompts says what language a researcher should search in, what language
sources may be in, or what language the report should be written in. `shared_rules.md` is silent. The
HTTP fetcher sends no `Accept-Language` header (`openai_search.py:44-46`), so every server returns
whatever it defaults to.

In practice an English-language prompt produces English-language queries, which return
English-language sources. **For any non-English country that means the Tier 1 official sources — which
are published in the national language — are never found at all.** The tier ladder in
`shared_rules.md:4` silently inverts: the system searches Tier 3 first because that is where the
English material is.

**Fix.** Make language explicit and property-driven:

- Add to the shared rules: *search in the official language(s) of the jurisdiction first, then in
  English; quote sources in their original language and give an English translation beside the
  quote.* The mission already carries the property's location, so the model can derive the language
  itself — no country table needed.
- Store both the original quote and the translation in `citations.jsonl`, and verify the **original**
  against the stored source text. The exact-match guard then works for any language.
- Send an `Accept-Language` header derived from the mission rather than none.

---

### 7 · Minor, but fix while nearby

- **`tests/common.py:28,30`** — the test fixture uses `EUR 100,000`. Harmless, but a global system's
  fixtures should not all be one currency. Add at least one non-EUR, non-Latin fixture so these
  failures show up in the test suite instead of in production.
- **Console encoding** — this environment's default stdout is `cp1252`; printing a non-ASCII agent
  name from `cli.py` will raise `UnicodeEncodeError`. Set `PYTHONIOENCODING=utf-8` in `run.ps1`.
- **URLs with non-ASCII hosts** — `retrieval.py:9-17` never converts internationalised domain names
  to punycode, so a `.рф`, `.中国` or `.السعودية` address will not resolve. Add
  `host.encode("idna")`.

---

## What is already country-neutral — leave it alone

Credit where it is due. These were done correctly and must not be "fixed":

- **The fourteen agent names** (`layer2/settings.py:13`) are written in neutral terms — "Legal, title
  & encumbrance", "Planning, regulation & tax". Nothing names a German institution.
- **The `web_sources` lists** in `planner_prompt.md` are generic categories — "Land register",
  "Cadastral register", "Company register", "Court and insolvency registers" — not German ones. The
  model resolves them to whatever the local equivalent is.
- **All Layer 3 prompts** are country-neutral. `shared_rules.md` states principles, not jurisdictions.
- **The SSRF guard** (`retrieval.py:24-39`) and the **exact-quote citation check**
  (`sources.py:165-167`) are deterministic and locale-independent. These are the right kind of rule.

The pattern worth noticing: **everything expressed as a principle travelled fine; everything expressed
as a regular expression did not.** That is the lesson to carry into the fixes.

---

## Priority

| Order | Item | Why first |
|---|---|---|
| 1 | §1 privacy guard | It actively leaks confidential data today and blocks valid research. Both directions are wrong. |
| 2 | §6 language policy | Without it, non-English countries never reach their Tier 1 sources at all. Cheapest fix, largest gain. |
| 3 | §3 encoding detection | Silent, misdiagnosed failures on local-language sources. |
| 4 | §2 non-Latin filenames | Blocks whole scripts from existing in the system. |
| 5 | §5 table separators | Small change, restores numeric evidence. |
| 6 | §4 PDF extraction | Largest gain in evidence quality, but needs a new dependency and a decision. |
| 7 | §7 minor items | Cheap, do while nearby. |

---

## How to verify a fix worked

Add fixtures from at least four writing systems and three currencies, and assert:

1. A query containing a UK, Japanese, Brazilian or Indian postcode is blocked; a query containing an
   ordinary five-digit quantity is allowed.
2. A quote from a windows-1251, Shift-JIS and Big5 page passes the citation check.
3. A lens named in Chinese, Arabic or Greek produces a usable filename and keeps its display name.
4. A table's cell values survive extraction as separate tokens.
5. `Accept-Language` reflects the property's jurisdiction.

None of these is testable today, which is why none of these problems was caught.

---
---

# Part 2 — what restricts the model, and what to remove

**Added after a second full sweep of `ML/deep_research/layer3/`.**

## Two decisions recorded first

**PDF extraction is deferred.** It will be solved by adopting a web retrieval API that reads
documents on the web directly, rather than by adding a parsing dependency here. That API drops in
behind the existing `Retriever` protocol (`retrieval.py`) — `search()` and `fetch()` are already the
right seam, so no pipeline change is needed. §4 of Part 1 stands as background, not as work.

**Guiding rule for everything below:** *the model's output should be as free as possible.* A rule
earns its place only if it protects **evidence integrity** — that a quote really exists in a real
source that was really fetched. Anything that constrains the model's *reasoning, wording, search
strategy, or stopping judgement* is to be removed.

The sweep found **24 restrictions**. Four are legitimate. Twenty are not.

---

## A · Hard caps the model cannot argue with

### A1 — Only five search results ever reach the model
`settings.py:22` `MAX_SEARCH_HITS = 5`, applied at `openai_search.py:101` and duplicated as a bare
`[:5]` at `providers/fixture.py:28`.

Result six onward does not exist as far as the researcher is concerned. On a broad question the best
source is routinely not in the top five. The model cannot ask for more, cannot page, and is never
told anything was withheld.

**Remove the cap.** Return everything the provider gives and let the model choose what to open. If a
ceiling is genuinely needed for cost, make it large (50+) and **tell the model in the tool response
how many were withheld**, so a silent truncation becomes a visible one.

### A2 — The search budget is enforced twice, and the second one is fatal
`settings.py:20-21` (40 first round, 20 second) is enforced at `research_tools.py:72-73` as a polite
tool rejection **and again** at `llm.py:61-63` as `ToolCallLimitMiddleware(..., exit_behavior="error")`.

The first is fine — the model is told it has hit the limit and can write its report. The second
**kills the session outright**, so a researcher that reaches the cap loses everything it gathered.

**Fix.** Keep the tool-level notice; set the middleware limit above it, or to
`exit_behavior="continue"`, so the ceiling never destroys work already done.

### A3 — Three strikes and the session dies
`llm.py:64-66` — `ToolCallLimitMiddleware(tool_name="finish_round", run_limit=3, exit_behavior="error")`.

`finish_round` has **seven** distinct rejection paths (`research_tools.py:209-230`). Three of them
are wording checks. A researcher that trips wording rules three times loses a completed piece of
research.

**Fix.** Raise the limit substantially, and remove the wording-based rejections (§D) so the remaining
rejections are all substantive and correctable.

### A4 — An aggregator gets five model calls to read five full reports
`llm.py:113` — `ModelCallLimitMiddleware(run_limit=5)`, plus `recursion_limit: 30` at
`aggregator_runner.py:26`.

Pass 2 must read five long research reports, reconcile disagreements, decide what is unsettled, and
write one answer. Five turns is tight for that, and the failure mode is a hard error, which
`write_answers.py:229-244` then converts into an answer whose body reads `Status: failed`.

**Fix.** Raise both limits; they are backstops against runaway loops, not a budget.

### A5 — Large pages are discarded entirely
`openai_search.py:53-57` — a source over 10 MiB raises `ValueError` and is lost. Statistical
yearbooks and planning registers exceed this routinely.

**Fix.** Truncate and mark the record as truncated rather than discarding. A partial official source
beats a complete secondary one.

### A6 — Search snippets are cut to 1000 characters
`openai_search.py:94` — `snippet=snippet[:1000]`, before the model sees them. The snippet is how the
model decides whether a source is worth opening.

**Fix.** Do not truncate, or raise it substantially.

### A7 — Total turn cap
`llm.py:67` — `ModelCallLimitMiddleware(run_limit=max_queries * 3 + 10)`, and `sessions.py:173` —
`recursion_limit = max_queries * 4 + 50`. The multipliers `3`, `4`, `+10`, `+50` are unexplained.

**Fix.** Keep as a runaway backstop, raise it, and put both in `settings.py` with a comment saying
what they protect against.

---

## B · Forced behaviour that overrides the model's judgement

### B1 — Every result must be opened before the next search
`research_tools.py:69-70` — `Rejected: review every pending hit before searching again.`

The model must `read_source` all five hits even when the titles make it obvious four are irrelevant.
It cannot skim, cannot skip, and cannot reformulate a bad query without first paying to fetch five
pages it does not want. This is the single most expensive restriction in the layer, and it is pure
process enforcement — nothing about evidence integrity requires it.

**Remove it.** Let the model discard a pending hit with a reason, and record the discard so the
search trail stays complete.

### B2 — The model cannot stop when it is satisfied
`research_tools.py:214-215` — `Rejected: search again until no unseen source is added.`

A researcher that finds a definitive official answer on query three is forced to keep searching until
a query returns literally zero new URLs, or until the 40-query cap is reached. The design intent —
"stop when a round adds nothing" — was meant as *permission* to stop, not an *obligation* to continue.

**Fix.** Let `finish_round` accept a stated reason for stopping early, and record it. The stopping
judgement belongs to the researcher.

### B3 — Tier must be exactly 1, 2, 3 or 4
`sources.py:160-161`. There is no way to record "unrated", "mixed" or "unclear". Meanwhile the tier
is entirely model-asserted and never verified, so the rigid enum buys nothing.

**Fix.** Allow an `unrated` value with a required reason.

### B4 — An "answered" report must carry a citation marker
`research_tools.py:225-226`. **Keep this one.** It is an evidence-integrity rule and it is correct.

---

## C · Silent truncation and mutation of model output

### C1 — The sixth lens's name is cut to 80 characters
`write_answers.py:136` — `name = decision.name.strip()[:80]`, then written back into the validated
pydantic object at `:141`, **bypassing `validate_gap`**. The model's own structured field is edited
after validation.

**Fix.** Move the constraint onto the contract as a pydantic `max_length`, so the model is told the
limit up front and never has its answer silently edited.

### C2 — Content appended after validation
`research_tools.py:236-242` appends a `## Search trail` section; `write_answers.py:43` prepends a
title and appends the `DISCLOSURE` sentence. Both are unconditional and additive — far safer than a
conditional rewrite — but the model's file is not what the model wrote.

**Keep, with one change:** fence the appended block with an HTML-comment sentinel so the model's own
text remains exactly recoverable. This also fixes the `## Second round` collision in Part 1.

### C3 — Fixture quote truncation
`sessions.py:197` — `[:180]`. Test scaffolding only, but it means fixture runs never exercise a long
quote.

---

## D · Rejections based on wording rather than substance — remove all four

These most directly contradict "the model's output should be free". Each inspects the model's
*choice of words* and rejects it.

| Where | Rejects | Why it must go |
|---|---|---|
| `question_files.py:17` | Any question containing `practitioner`, `academic`, `economist`, `historian`, `skeptic` as a substring | *"What does the academic literature establish…"* is rejected. Blast radius: it raises, so all five of that agent's second rounds are cancelled. |
| `question_files.py:19` | Any question containing `"asked by"` or `"according to"` | *"According to which standard is airtightness measured?"* is rejected. Same blast radius. |
| `research_tools.py:229` | Any report citing a Tier 4 source without the literal string `tier 4` | The prompt asks for `Tier 4 only`; the code looks for `tier 4`. It scans the whole document, so *"No Tier 4 sources were used"* satisfies it. Claims to check "beside the claim" and does not. |
| `egress.py:35-41` | Any query matching three hard-coded locale patterns | Blocks valid research and leaks real confidential data. Documented in Part 1 §1. |

**Replacement pattern for all four:** the judgement moves into a structured field the model fills in,
or into a cheap structured second call. The deterministic layer then checks only facts — *does this
citation id exist*, *does this quote appear in the stored bytes*, *does this literal appear in the
query*. Words are never pattern-matched.

Additionally, **none of these should raise.** A single bad question currently cancels five research
rounds. Record the concern; keep the work.

---

## E · Structural constraints

### E1 — No code execution
`llm.py:38` excludes `execute`, and `StateBackend` cannot execute regardless. Already decided: a
restricted sandbox for researchers only. Until it lands, the economist and practitioner lenses can
only do unverifiable mental arithmetic.

### E2 — Questions round-trip through Markdown and lose data
`question_files.py:23-36`. The structured `QuestionSet` is rendered to bullets and regexed back. A
question containing a newline silently loses its remainder, and the read-back count decides whether a
second round happens at all.

**Fix.** Persist the JSON as the source of truth; render Markdown for humans only.

### E3 — What is correctly unrestricted, and must stay that way
- **No `max_tokens` anywhere.** Neither input nor output is capped. Correct — leave it.
- **The researcher has no `response_format`.** Its report is free prose, exactly as the design
  requires. Correct.
- **`AnswerDraft` is a single `markdown` field.** The structure constrains delivery, not content.
  Correct.

---

## F · The four rules that must survive

Removing restrictions must not remove the guarantees. These four are why the output can be trusted,
and none of them constrains the model's thinking:

1. **`sources.py:165-167`** — a cited quote must appear verbatim in the stored source bytes.
2. **`retrieval.py:24-39`** — the SSRF guard; no private or internal address is ever fetched.
3. **`egress.py:32-34`** — the exact-literal denylist, built from this property's own facts.
4. **`run_checks.py:221`** — every stored file hashes to its own filename.

Each checks a **fact**, not a **wording**. That is the line: verify what the model *did*, never
police what it *said*.

---

## Revised priority

| Order | Item | Effect |
|---|---|---|
| 1 | §D — remove all four wording rejections | Stops valid research being discarded and confidential data leaking |
| 2 | §B1, §B2 — stop forcing reads and forcing continued search | Largest cost saving, biggest restoration of judgement |
| 3 | Part 1 §6 — language policy | Without it, non-English countries never reach Tier 1 sources |
| 4 | §A1, §A5, §A6 — stop hiding evidence from the model | More and better sources reach the reasoning |
| 5 | §A2, §A3, §A4 — raise fatal limits | Stops completed work being destroyed at a ceiling |
| 6 | Part 1 §3, §2, §5 — encoding, non-Latin filenames, tables | Global correctness |
| 7 | §C1, §E2 — stop silently editing model output | Integrity of what the model actually said |

---
---

# Part 3 — resolution

**All items in Parts 1 and 2 are fixed, except PDF extraction, which is deferred by decision.**
`30 tests OK`, fixture dry run `24/24`, no model call.

## Part 1 — global readiness

| § | Item | Resolution |
|---|---|---|
| 1 | Locale regexes in the egress guard | The three patterns are **deleted**. `egress.py` now keeps only the exact-literal backstop, built from this property's own facts. Semantic leaks go to `clearance.py`, a structured `QueryClearance` call that reasons about the mission — so every currency, address form and postcode format is covered without any of them being written down. Decisions are cached per run and per query. |
| 2 | `slug()` destroyed non-Latin scripts | `layer2/fs.py` now NFKD-normalises and strips combining marks, so `Bauträger → bautrager` and `Marché → marche`. Scripts with no Latin form get a stable hashed identifier instead of an empty string. **ASCII roster slugs are byte-identical, so Layer 2 output is unchanged.** |
| 3 | UTF-8 assumed for every page | `text_extraction.detect_encoding` resolves BOM → HTTP header → `<meta charset>` → UTF-8 → windows-1252, using `email.message.Message` rather than a regex. The encoding used and whether it was **declared** are both written to `index.jsonl`, so a decoding guess is diagnosable instead of looking like an invented quote. |
| 4 | PDFs cannot be cited | **Deferred by decision** — to be solved by the web retrieval API, which drops in behind the existing `Retriever` protocol with no pipeline change. |
| 5 | Table cells collapsed | `<td>`/`<th>` now emit a separator. `<td>Unit 1</td><td>1,200</td>` extracts as `Unit 1 | 1,200`. |
| 6 | No language policy | `shared_rules.md` now requires searching **the jurisdiction's official language first**, quoting in the source's own script with an English translation beside it. The fetcher sends `Accept-Language: *` rather than expressing an English preference. |
| 7 | Minor | IDN hosts are punycoded so `.рф`, `.中国` and `.السعودية` resolve; a malformed port no longer raises out of a model-supplied URL; `run.ps1` sets `PYTHONIOENCODING=utf-8`. |

Magic numbers from §1 are gone too: the check count derives from `len(checks)`, and the roster and register counts derive from `AGENT_NAMES` and `LENSES`.

## Part 2 — restrictions on the model

**Removed** — every wording rejection (§D): the `"tier 4"` substring scan, the lens-name substring
filter, the `"asked by"`/`"according to"` filter, and the three egress patterns. None of them
inspects the model's words any more, and none raises, so one unlucky phrase can no longer cancel
five research rounds.

**Restored to the model's judgement** (§B): `skip_source` lets a researcher discard a result on its
title without paying for a fetch — the forced "read every pending hit" rule is gone. `finish_round`
takes an optional `stopping_reason` and no longer refuses to finish while the budget is unspent.
Tier accepts `unrated`.

**Raised or made non-fatal** (§A): search results 5 → 50 with the model *told* when a list may be
incomplete; snippets 1 000 → 20 000 characters; oversized pages truncated and flagged rather than
discarded; `finish_round` attempts 3 → 12; the aggregator's model-call limit 5 → 40 and recursion
30 → 120. Every ceiling now uses `exit_behavior="continue"` or `"end"` — **no limit destroys work
already gathered**.

**Stopped editing model output** (§C): `SIXTH_LENS_NAME_MAX_CHARS` is declared on the contract, so
the model is told the limit instead of having its validated answer truncated afterwards. Appended
sections are fenced with `<!-- l3:search-trail -->` and `<!-- l3:second-round -->`, so the
researcher's own text stays exactly recoverable.

**Calculation** (§E1): `run_python` executes in a separate interpreter in isolated mode, from an
empty working directory, with a stripped environment, sockets disabled, a 15-second timeout and
capped output. The code and its output are stored in `calculations.jsonl` and reproduced in the
report, so a derived figure is auditable. `shared_rules.md` now requires it: **any number not quoted
verbatim from a cited source must be computed by running code.** One generic capability, not a
bespoke tool per calculation.

**Questions** (§E2): `QuestionSet` is persisted as JSON and is the source of truth. The Markdown file
is a human rendering that is never read back, so a question containing a newline survives intact.

## What deliberately did not change

The four integrity rules in §F are untouched: a cited quote must appear verbatim in the stored
bytes; the SSRF guard; the exact-literal denylist; every stored file hashes to its own filename.
Each checks a **fact**, not a **wording**.

## A latent bug found while fixing

`run_checks.py` check 8 still split on the `## Second round` heading after the writer had moved to
the sentinel. It passes in the fixture run only because that run never produces a second round —
the check was vacuous, exactly as Part 1 said. Fixed, and now covered by
`tests/test_layer3_restrictions.py::test_first_round_may_contain_the_second_round_heading`, which
writes a first-round report that *contains* the heading and proves the append no longer breaks.

## New tests

- `tests/test_layer3_global.py` — slug across Chinese, Russian, Arabic and Greek; decoding of
  Shift-JIS, Big5, windows-1251 and ISO-8859-7 pages; table cell separation; the sandbox computing
  and refusing network access.
- `tests/test_layer3_restrictions.py` — the second-round heading collision; questions surviving
  newlines and lens vocabulary; `unrated` citations; the sixth-lens slug collision; the declared
  name limit; `QuestionSet` having no field that could carry attribution.
- `tests/test_structure.py` now import-checks `layer3` as well as `layer2`.

The executable files remain below 350 lines. The shared tool-command helper now lives with the
research tools, and Python execution lives with its sole caller in `calculation_tool.py`.

---
---

# Part 4 â€” the constraints were removed, not tuned

**This supersedes Parts 1â€“3 wherever they conflict.** Those parts treated the guardrails as things to
*fix*. The decision since is that they should not exist at all.

## The rule now in force

> **The model runs free. Nothing in Python limits, filters, validates, normalizes or blocks what goes
> into it or comes out of it. Everything is taken care of by the LLM.**

Anything that existed because we did not trust the model is gone. What is left is what the program
mechanically needs to run, plus one guard that protects the network rather than the model.

## Deleted outright

`egress.py`, `clearance.py`, `trail.py`, `prompts/query_clearance.md`, `tests/test_layer3_restrictions.py`.

## Removed

**Every rejection.** No tool returns `"Rejected: â€¦"` any more â€” verified, zero occurrences.
`search_web` searches, `read_source` fetches any URL whether or not a search returned it,
`finish_round` stores whatever it is handed.

**Citation verification.** `record_citation` no longer checks that the quote appears in the page, no
longer restricts the tier to a fixed set, and no longer refuses a source with no extracted text. A
citation is recorded exactly as given.

**Every cap.** Query budgets, search-hit caps, snippet caps, byte caps, fetch timeouts, session
retries, `finish_round` attempts, model-call and tool-call ceilings, the sixth-lens name length, the
fixture quote length. All deleted from `settings.py` and every enforcement site.

**All middleware.** `ModelRetryMiddleware`, `ToolRetryMiddleware`, both `ToolCallLimitMiddleware` and
`ModelCallLimitMiddleware` are gone. Agents are built with `middleware=[]`.

**The harness profile.** `excluded_tools` and the general-purpose subagent block are gone, so the
model keeps `write_file`, `edit_file`, `delete`, `execute` and the subagent alongside its own tools.

**The sandbox restrictions.** `run_python` executes the code as written. No timeout, no output clip,
no stripped environment, no isolated mode, no blocked sockets or file IO.

**Every mutation of model text.** No `.strip()` on a report, no appended search trail, no injected
title or disclosure on an answer, no dropped blank questions, no whitespace collapsing on a quote,
no spliced second-round sentinel. `validate_gap`, `validate_clearance`, `validate_questions`,
`names_a_lens` and `validate_answer` are all deleted.

**Fabricated artefacts.** A failed session or aggregator call records the failure in the register.
Nothing is written in the model's place â€” the old `Status: failed` stub answers and empty question
sets are gone.

**Eleven checks.** The check phase went from 24 to **13**. Everything that policed model output is
deleted; what remains verifies files, hashes, counts and register completeness. The report now says
*did the run complete*, not *did the model behave*.

## Changed rather than removed

**The second round gets its own file** (`<lens>.second.md`). Nothing is spliced into or split out of
the first round, so it cannot be corrupted and there is nothing to hash-check.

**Prompts rewritten.** `shared_rules.md` described ten numbered obligations. A rule in a prompt
constrains as effectively as a rule in code, so it now describes the work, the tools and the output
and leaves the judgement to the researcher. The aggregator prompts got the same pass.

## Kept, deliberately

**`RECURSION_LIMIT = 1_000_000`.** This looks like a limit and is the opposite. LangGraph defaults to
**25 steps**; without this every session would die mid-research. Removing it would have been the most
restrictive change available.

**`validate_public_url` and the redirect handler.** The one guard that is not about the model. It
does not touch reasoning, wording, search strategy or output â€” it stops the *fetcher* being pointed
at `127.0.0.1`, `10.x` or `169.254.169.254` by a page written by a stranger. A failure comes back to
the researcher as an ordinary tool message it can react to, not as a refusal.

**Structured output.** `QuestionSet`, `GapDecision` and `AnswerDraft` still use `response_format`.
That is a delivery format for code that has to read the result, not a restriction on what the model
may think or say â€” and it is what was asked for in place of parsing free text.

## Verified

`25 tests OK` Â· `13/13` checks on the offline dry run Â· no `"Rejected:"` string, no
`*CallLimitMiddleware`, no `max_length`/`min_length`, no `model_validator`, no `excluded_tools`
anywhere in `layer3`.

The only `raise` statements left in the layer are CLI and Layer-2-handoff validation, register
programming errors, and the network guard. None of them fires on something the model produced.


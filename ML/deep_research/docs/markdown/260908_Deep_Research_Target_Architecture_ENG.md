# Deep Research Target Architecture

Status: **proposed target design**, not implemented · Consolidated 08 September 2026 · Supersedes the separate "Modular Deep Research" architecture and "Phase Inputs & Outputs" documents of 07 September 2026 and the eight-domain architecture ticket write-up.

An industry-neutral research engine that turns supplied facts into focused domain research, then investigates the outside forces that influence those findings. This document holds both the architecture and the phase-by-phase handoffs; there is no separate companion.

---

## 1 · The architecture at a glance

Three layers carry different responsibilities. Layer 2 understands and organizes the subject. Layer 3 researches each domain using selected sources and processed documents. Layer 4 independently extends those findings into external dependencies and produces the cross-domain view.

```text
INPUTS · Domain plugin + requirement.md + factsheet.md
↓
LAYER 2 · Understand the subject, define domains and distribute facts
↓
LAYER 3 · Select sources, ingest documents and research each domain
↓
HANDOFF · Individual Layer 3 domain reports + requirements + final domain definitions
↓
LAYER 4 · Research external dependencies across all final domains
↓
OUTPUTS · External domain reports + dependency graph + final synthesis
```

The domain catalogue travels through the pipeline. Every layer follows the same final baseline and additional domains. Domain counts come from the selected plugin and the reviewed subject; they are not fixed globally.

All model turns, including tool follow-ups, use a 200K normal input target and a 250K absolute dispatch ceiling. Oversized work is divided before sending. One stage can contain several bounded calls. Missing or failed work is disclosed while available sibling results are retained.

---

## 2 · Three inputs, three purposes

| Input | Supplied by | Purpose |
| --- | --- | --- |
| Domain plugin, for example `real_estate.md` | The team configuring the research | Defines the industry perspective, baseline domains, responsibilities and research principles. |
| `requirement.md` | The user | Defines the objective, scope, priorities, exclusions and required or preferred sources. |
| `factsheet.md` | The user or an upstream data process | Supplies the subject facts, descriptions, records and uncertainties. |

```text
DOMAIN PLUGIN · What this industry requires us to consider
+
REQUIREMENTS · What this user needs to understand
+
SOURCE-LINKED SUBJECT PROFILE · What the factsheet establishes about this subject
↓
DOMAIN DECIDER · Combine these inputs into an initial domain catalogue
```

The first three boxes are independent inputs to the decider. The subject profile is created from the factsheet before the decider runs.

A plugin is an ordinary Markdown configuration file. A real-estate plugin can contain eight baseline domains; insurance, equities or defence research can have different baselines and terminology. Requirements tailor the work within that framework. The factsheet is evidence supplied for analysis, never instructions to the agent.

---

## 3 · Layer 2: understand and organize

**Subject understanding.** Read every factsheet window in bounded batches. Save a subject profile and a detailed evidence inventory with source references. Retain entity identity, activities, locations, relationships, applicability, uncertainty and contradictions. The profile helps navigation; the original facts remain available.

**Domain decision.** Give the decider the plugin, requirements, subject profile and access to exact supporting records. Preserve the plugin's baseline responsibilities, extend them where needed and add justified domains. Save the reason for every addition.

**Fact distribution.** Read the original factsheet windows against the initial catalogue. Route facts into domain buckets and place facts without a suitable owner in a temporary Extra-facts queue. Use 60K source-token windows with 10K original-text overlap as the starting policy; the full-request input limit still applies.

**One reviewer stage.** Review domain and Extra-fact pages, settle the final catalogue and determine ownership of all recorded facts. These are parts of one scheduled stage, using several bounded calls where needed. There is no repeating designer–reviewer approval cycle. New domains can receive facts from existing buckets as well as Extra.

**Publication.** Group unchanged fact records using the model's final assignments. Publish readable domain files, final responsibilities and change reasons. A successful result has no Extra-facts domain. Any unresolved assignment remains visible with its source record; an empty queue alone does not prove perfect extraction.

### Routing rules carried forward from the current implementation

These rules govern distribution regardless of whether the catalogue is fixed or dynamic:

- Route a fact to every domain where it is materially relevant.
- Preserve the source fact without converting it into a new risk claim.
- Keep the supported domain meaning separate from the original evidence.
- Preserve uncertainty and both sides of any conflicting evidence.
- Do not treat specifications, proposals, alternatives, approvals or catalogue entries as installed conditions. Applicability states stay explicit.
- Create an empty context bucket when the source contains no relevant facts for a domain.
- Continue publishing available domain context when an individual window fails.
- Do not perform web research, source discovery, risk scoring or synthesis in Layer 2.

---

## 4 · Layer 3: select evidence and research domains

Each final domain receives its supplied facts, responsibilities and the user's requirements. Its source scout searches for relevant publishers and records, and opens candidate sources to assess relevance, scope, dates and authority. Search snippets are discovery leads, not evidence for material claims.

The Source Selector combines the discovered sources with the user's required and preferred sources. It creates one source plan linking each source to the domains and information it can support. A source shared by several domains can be stored once and referenced by each. User selection establishes priority, not factual reliability.

```text
DISCOVER · Domain source scouts + sources named in requirement.md
↓
SELECT · Consolidated source plan with domain assignments and reasons
↓
INGEST · Open webpages; download and process selected documents
↓
RESEARCH · Domain agents interpret accessible evidence and resolve findings
↓
PUBLISH · One evidence-backed Markdown report for each domain
```

The source plan stays open to new discoveries. A researcher can add a relevant source and record its provenance during research. A newly discovered document uses the same ingestion process before its contents support a finding.

Layer 3's deliverables are the individual domain reports and their evidence records. The combined cross-domain synthesis belongs to Layer 4.

---

## 5 · Documents become usable evidence

```text
SELECTED DOCUMENT · PDF or another supported file type
↓
PRESERVE · Download original bytes, source URL and retrieval metadata
↓
EXTRACT · Parse text and tables; use OCR where appropriate
↓
REFERENCE · Save readable content with page, sheet or section pointers
↓
INTERPRET · Relevant domain researchers use the extracted evidence
```

Extraction is a processing service. It makes document contents readable; researchers decide what those contents mean for their domains. One document may support several domains without being downloaded and processed separately for each.

If extraction is partial or unreliable, keep the original, record which parts are usable, try supported parsing or OCR, and seek an authoritative alternative. A researcher discloses the remaining limitation. A document title, snippet or failed extraction cannot establish its contents. Preserve table structure and document location where available; do not manufacture a page reference when the format has none.

The extraction tiers, artifact schema, limits and failure handling are specified in the document-ingestion design.

---

## 6 · Layer 4: independent external enhancement

Layer 4 receives each Layer 3 domain report, the requirements and final domain definitions. The original factsheet is not sent again. Layer 3 evidence pointers remain available for traceability, while external research opens its own supporting sources.

An external-factor brief identifies plausible research directions. The external researcher may extend or reject those directions as evidence develops. It investigates baseline and added domains using the same source-reading and document-ingestion services.

```text
EXTERNAL DRIVER · Policy, demand, finance, infrastructure, climate or another outside force
↓
TRANSMISSION · An authority, market, supplier, network or other intermediary
↓
SUBJECT DEPENDENCY · The specific relationship identified in Layer 3
↓
VULNERABILITY OR SAFEGUARD · What amplifies or reduces the exposure
↓
EFFECT + HORIZON · The supported operational, financial or strategic consequence
```

Research can explore wider conditions before a subject-level effect is proven. Reports distinguish established external dependencies, conditional pathways, dependencies without a proven adverse event, general context and unresolved evidence. They do not invent a geopolitical or macroeconomic explanation to fill a category.

Layer 4 publishes three complementary results:

| Result | What it provides |
| --- | --- |
| Individual external-dependency reports | Detailed findings for every final domain, with evidence and uncertainty. |
| Separate dependency graph | Traceable nodes and relationships showing shared drivers, different branches, converging dependencies and supported compound effects. |
| Final synthesis | A compact manager-facing explanation of the external-dependency landscape, linked back to the graph and domain reports. |

Graph creation relates evidence already established by domain research. It merges only materially identical causes and pathways, and preserves conditional relationships as conditional. Final synthesis introduces no new evidence, causal steps or ratings. Both stages read large inputs in bounded portions when necessary; the final report does not require one oversized call.

---

## 7 · Agent harness

The harness is the working environment around an agent: its instructions, tools, permitted records and saved progress. The same Deep Agents foundation supports every role.

### 7.1 Roles

| Role | Receives | Produces |
| --- | --- | --- |
| Subject reader | Original factsheet windows | Source-linked profile and evidence inventory. |
| Domain Decider | Plugin, requirements and subject understanding | Initial domains, responsibilities and reasons. |
| Fact Distributor | Original facts and initial catalogue | Domain assignments and temporary Extra facts. |
| Domain Reviewer | All recorded facts in pages and the initial plan | Final catalogue and ownership decisions. |
| Source scout and Source Selector | Domain responsibilities and source preferences | Domain-linked source plan. |
| Domain researcher | Domain facts and accessible external evidence | Layer 3 domain report. |
| External-factor mapper and researcher | Layer 3 report, requirements and domain scope | Layer 4 external-dependency report. |
| Graph builder and synthesizer | External reports and their traceable findings | Separate dependency graph and final synthesis. |

These are responsibilities, not a requirement to create a supervisor for every role. The orchestrator schedules the known stages, while domain definitions configure the relevant research workers. Document extraction and file publication are processing functions rather than additional reasoning agents.

### 7.2 Harness behaviour

| Concern | Proposed harness behavior |
| --- | --- |
| Foundation | Reuse Python Deep Agents and the existing model construction. Configure roles from the frozen plugin, requirements and domain catalogue. |
| Planning and routing | No web tools. Supply source windows directly; give planning roles bounded reference reads only where supporting records are needed. |
| Review | Read-only access to run-owned source, fact and decision records. Save progress between pages. |
| Source selection and research | Search and source-reading tools, with extracted document content returned through source access. |
| Graph and synthesis | No new web research. Supply reports directly or read bounded portions of saved research records. |
| Memory | Large inputs and responses in durable files; small active contexts contain relevant text and exact references. |
| Recovery | Persistent checkpoints for interrupted tool-using sessions; reuse successfully saved stages and retain separate invocation identities. |
| Coordination | Native batching for independent source windows; reconcile domain-definition changes in order and research domains in a recorded order. |
| Attribution | Record the responsible phase/domain, source references, elapsed activity, model calls and token usage. |
| Output freedom | Save completed model responses without semantic Python grading, repair prompts or content-driven retries. Operational handling covers serialization, safe source access, persistence and transport failures. |

Downloaded material and factsheet text cannot expand tool permissions. The application controls access to run-owned files. Provider transport retries remain separate from model-authored conclusions. No shell, executable plugin or unrestricted host-file tool is required by this design.

---

## 8 · Memory and the input boundary

```text
FULL ARCHIVE · Original sources, fact records and exact saved decisions
↓
REFERENCE READ · Fetch a specific passage within the remaining allowance
↓
ACTIVE CONTEXT · Current work page + relevant instructions and supporting records
↓
INPUT CHECK · Count the complete request before every model turn
↓
SAVE & CONTINUE · Preserve the result, then load the next work page
```

| Input size per model request | Handling |
| --- | --- |
| Up to 200K tokens | Normal operating target. Smaller requests are used when sufficient. |
| Above 200K and up to 250K | Exceptional tolerance for a necessary bounded continuation; record the reason. |
| Above 250K | Divide or repack the input before dispatch. No silent truncation. |

The count includes instructions, plugin content, requirements, source text, tool definitions, retrieved passages and retained history. Apply it again after tool reads, including the total returned by multiple tools. Cached input still occupies context. These limits govern individual requests, not the total run cost.

Summaries can guide navigation but never replace authoritative source records. Exact storage preserves recorded bytes; page coverage and fact ownership make omissions observable. Neither proves that the model understood every fact correctly. The request-counting mechanism must be verified during implementation before claiming exact provider-side enforcement.

The Layer 2 realisation of this boundary — paged review, the bounded reference reader, storage levels and call arithmetic — is specified in the Layer 2 domain design and fact memory document.

---

## 9 · Phase handoffs

Each phase states its owner, inputs, work, model-visible tools, invocation pattern, outputs, consumer and unresolved-state behavior. Artifact names are illustrative labels, not required response schemas. Completed model responses remain saved even when an expected field or assignment is absent. The 15 phases form one workflow; phases 5 and 6 belong to a single scheduled reviewer stage.

```text
INPUTS · Plugin + requirements + factsheet
↓
LAYER 2 · Subject profile → initial catalogue → routed facts → reviewed catalogue and assignments
↓
LAYER 3 · Source candidates → source plan → readable documents → individual domain reports
↓
LAYER 4 · External briefs → external reports → dependency graph → final synthesis
```

### Layer 2 phases

**Phase 1 · Plugin and requirement intake**

| Item | Description |
| --- | --- |
| Owner | Run orchestrator; no reasoning agent. |
| Input | Selected domain plugin, `requirement.md`, `factsheet.md`. |
| Work | Preserve input copies, identities and the source-reading schedule. |
| Tools visible to model | None. |
| Invocation | No model call. |
| Saved output | Immutable input snapshots and run metadata. |
| Consumer | Subject reader and Domain Decider. |
| Unresolved state | Report unreadable input as an operational error; never manufacture its contents. |

**Phase 2 · Factsheet subject understanding**

| Item | Description |
| --- | --- |
| Owner | Subject reader. |
| Input | Every original factsheet window; plugin context and relevant requirements. |
| Work | Identify entities, uses, relationships, applicability and contradictions, with source references. |
| Tools visible to model | No web tools; source windows supplied directly. |
| Invocation | One call per bounded source window; assemble the profile in bounded portions if needed. |
| Saved output | `subject_profile.md`, detailed evidence inventory and source pointers. |
| Consumer | Domain Decider; later reviewer for supporting evidence. |
| Unresolved state | Preserve failed-window records and label profile limitations. The profile never replaces the original source. |

**Phase 3 · Initial domain decision**

| Item | Description |
| --- | --- |
| Owner | Domain Decider. |
| Input | Plugin baseline, requirements, subject profile and evidence inventory references. |
| Work | Preserve baseline responsibilities; extend or add domains with reasons. |
| Tools visible to model | Bounded read-only reference access; no web search. |
| Invocation | Normally one planning call, with supporting reads or paging when needed. |
| Saved output | `domains_initial.md` and reasons for changes. |
| Consumer | Fact Distributor. |
| Unresolved state | Save the response and disclosed uncertainty. An unusable plan is exposed; no replacement roster is invented. |

**Phase 4 · Fact distribution**

| Item | Description |
| --- | --- |
| Owner | Fact Distributor. |
| Input | Original factsheet windows and initial domain catalogue. |
| Work | Route facts with supported meaning and provenance; preserve unassigned facts in temporary Extra. |
| Tools visible to model | None. |
| Invocation | One call per source window through native batching. Starting windows: 60K tokens, 10K original-text overlap. |
| Saved output | Fact records, initial assignments, domain buckets and temporary Extra queue. |
| Consumer | Domain Reviewer. |
| Unresolved state | Save available window results and source order; expose failures without suppressing sibling output. |

**Phase 5 · Review domain and Extra facts**

| Item | Description |
| --- | --- |
| Owner | Domain Reviewer, first part of its single scheduled stage. |
| Input | All recorded domain facts and Extra facts in pages; initial catalogue, requirements and source references. |
| Work | Propose ownership corrections, responsibility extensions and justified new domains. |
| Tools visible to model | Bounded read-only access to run-owned records. |
| Invocation | Bounded review calls across all scheduled pages; fresh context as needed. |
| Saved output | Per-page review decisions, proposed domains and assignment changes. |
| Consumer | Final catalogue and placement work within the same reviewer stage. |
| Unresolved state | Preserve unreviewed pages and missing decisions visibly; no automatic review-until-approved cycle. |

**Phase 6 · Final catalogue and fact placement**

| Item | Description |
| --- | --- |
| Owner | Domain Reviewer, final part of the same stage. |
| Input | Review decisions, proposed changes, complete fact inventory and source references. |
| Work | Settle the catalogue and assign facts to final domains, including moves from existing buckets. |
| Tools visible to model | Bounded read-only reference access. |
| Invocation | Bounded decision and placement calls, without restarting the designer. |
| Saved output | `domains_final.md`, final assignments and change reasons. |
| Consumer | Layer 2 publisher; downstream domain workers use the final definitions. |
| Unresolved state | Retain unassigned IDs and their facts. Zero Extra is achieved only when every recorded extra fact has an owner. |

**Phase 7 · Layer 2 publication**

| Item | Description |
| --- | --- |
| Owner | Application publisher; no reasoning agent. |
| Input | Unchanged fact records and model-authored final assignments. |
| Work | Materialize readable domain files and the reviewed catalogue. |
| Tools visible to model | None. |
| Invocation | No model call. |
| Saved output | Final domain fact files, catalogue, assignment trace and visible unresolved records. |
| Consumer | Layer 3 source scouts and domain researchers. |
| Unresolved state | Publish available material. Keep historical Extra records for traceability without presenting an Extra domain as a completed outcome. |

### Layer 3 phases

**Phase 8 · Per-domain source discovery**

| Item | Description |
| --- | --- |
| Owner | Source scout for each final domain. |
| Input | Domain facts and definitions; requirements including source preferences. |
| Work | Find and open relevant candidate sources; record what they can support and their limitations. |
| Tools visible to model | Web search and source reading. |
| Invocation | One bounded discovery session per domain, with tool follow-up turns. |
| Saved output | Domain source candidates with URLs, purpose, source type and assessed relevance. |
| Consumer | Source Selector. |
| Unresolved state | Mark unavailable or uncertain candidates; snippets do not establish document contents. |

**Phase 9 · Source consolidation**

| Item | Description |
| --- | --- |
| Owner | Source Selector. |
| Input | Domain source candidates and sources named in `requirement.md`. |
| Work | Consolidate shared sources and map them to domain needs, priorities and selection reasons. |
| Tools visible to model | Source reading and bounded access to scout records. |
| Invocation | Bounded consolidation calls; avoid one unlimited all-source input. |
| Saved output | `source_plan.md` with domain-linked sources and unresolved access notes. |
| Consumer | Document ingestion and Layer 3 researchers. |
| Unresolved state | Preserve selection uncertainty. The plan guides research; researchers can add and verify other relevant sources. |

**Phase 10 · Document download and ingestion**

| Item | Description |
| --- | --- |
| Owner | Shared document-processing service. |
| Input | Selected document URLs, including documents discovered during research. |
| Work | Preserve original files; extract text, tables and metadata with supported parsing or OCR. |
| Tools visible to model | No separate agent tool required; readable results are available through source access. |
| Invocation | Processing per document; no standalone reasoning-agent call is implied. |
| Saved output | Original file, canonical readable content, location references and extraction status. |
| Consumer | Applicable Layer 3 researchers; the same service supports new Layer 4 documents. |
| Unresolved state | Preserve unreadable or partial files, seek authoritative alternatives and disclose limits. Never claim failed pages were read. |

**Phase 11 · Layer 3 domain research**

| Item | Description |
| --- | --- |
| Owner | Direct domain researcher. |
| Input | Layer 2 domain facts, final definition, requirements, source plan and processed evidence. |
| Work | Research the subject, interpret documents, distinguish facts from inference and self-review material claims. |
| Tools visible to model | Web search and source reading, including canonical document content. |
| Invocation | An iterative bounded research session per domain, saved independently. |
| Saved output | Individual domain Markdown report and its evidence references. |
| Consumer | Layer 4 external-factor preparation and research. |
| Unresolved state | Preserve available reports and unresolved evidence. There is no Layer 3 cross-domain synthesis. |

### Layer 4 phases

**Phase 12 · External-factor preparation**

| Item | Description |
| --- | --- |
| Owner | External-factor mapper. |
| Input | Individual Layer 3 report, requirements and final domain definition. |
| Work | Identify plausible outside drivers and the subject dependencies that make them worth investigating. |
| Tools visible to model | No web search; bounded reads of supplied research records if needed. |
| Invocation | Normally one brief per domain, paged where necessary. |
| Saved output | `external_brief.md` with provisional factors and traceable Layer 3 anchors. |
| Consumer | External researcher. |
| Unresolved state | Label uncertainty; absence of a brief does not prevent research using the available Layer 3 report and scope. |

**Phase 13 · External-dependency research**

| Item | Description |
| --- | --- |
| Owner | External researcher for each final domain. |
| Input | Layer 3 report, provisional brief, requirements and final domain definition; no original factsheet. |
| Work | Establish outside drivers, intermediaries, subject dependencies, effects and horizons. Extend discovery when evidence warrants it. |
| Tools visible to model | Web search and source reading; reuse the document-ingestion service. |
| Invocation | Iterative bounded research sessions across all final domains. |
| Saved output | Individual `external_research.md` reports, source records and uncertainty. |
| Consumer | Dependency-graph creation and final synthesis. |
| Unresolved state | Distinguish established dependencies, conditional pathways, no-event dependencies, context and evidence gaps. Preserve available sibling reports. |

**Phase 14 · Dependency-graph creation**

| Item | Description |
| --- | --- |
| Owner | Dependency-graph builder. |
| Input | Available Layer 4 domain findings, their identifiers, evidence links and classifications. |
| Work | Relate shared drivers, separate branches, convergence and supported compound effects; merge only equivalent causes and pathways. |
| Tools visible to model | Bounded reads of saved reports; no new web research. |
| Invocation | Bounded graph-building work; exact finding references connect batches. |
| Saved output | Separate `dependency_graph.md` containing traceable nodes, relationships and their uncertainty. |
| Consumer | Final synthesizer and reviewers inspecting the dependency network. |
| Unresolved state | Preserve conditional edges and missing-domain notes. Do not invent relationships to connect every node. |

**Phase 15 · Final external-dependency synthesis**

| Item | Description |
| --- | --- |
| Owner | Final synthesizer. |
| Input | Dependency graph, available external reports, requirements and domain definitions. |
| Work | Explain the external-dependency landscape compactly while preserving evidence, scope and uncertainty. |
| Tools visible to model | Bounded access to saved research; no new web research. |
| Invocation | One finalization stage; multiple bounded reads or calls when needed to respect the input ceiling. |
| Saved output | Final `research/final.md` alongside the separate graph and individual domain reports. |
| Consumer | Manager or research stakeholder. |
| Unresolved state | Disclose unavailable domains and unresolved pathways; add no new facts, causal steps or ratings. |

---

## 10 · Saved artifact layout

The names below show the proposed responsibilities of saved artifacts. They do not prescribe a migration of existing storage or a new executable schema. Final domain files follow the reviewed catalogue, including added domains.

```text
research_run/
  inputs/
    domain_plugin.md
    requirement.md
    factsheet.md
  layer2/
    subject_profile.md
    evidence_inventory/
    domains_initial.md
    domains_final.md
    facts/
    review/                 # page decisions and historical Extra queue
    assignments/            # initial and final ownership records
    domains/<domain>/facts.md
  sources/
    source_plan.md
    raw/                    # downloaded originals
    readable/               # canonical text, tables and location references
    records/                # source identity and extraction status
  layer3/
    domains/<domain>/report.md
  layer4/
    domains/<domain>/external_brief.md
    domains/<domain>/external_research.md
    dependency_graph.md
    research/final.md
  operations/
    run.json
    run.log
    usage.jsonl
    checkpoints.sqlite3
```

---

## 11 · Worked example and sample artifacts

**Fictional throughout.** Alder Hospital Property is an invented subject used only to explain the architecture. Names, passages, dates, identifiers, URLs and relationships below illustrate the proposed outputs; none is a researched finding. The `.example` URLs are placeholders. Sample fields are explanatory, not mandatory schemas or output validators.

The real-estate plugin provides eight baseline research domains. The user asks to understand a potential hospital-property acquisition and prefers official local, regulatory and utility records. The factsheet describes an operating rehabilitation hospital with a named operator and a reliance on purchased heat.

Source understanding distinguishes current operation from proposed use. The Domain Decider can extend the location domain to cover the relevant service catchment and can propose a separate healthcare-operations domain if the baseline cannot express its responsibilities clearly. The reviewer confirms the final boundaries after reading all recorded facts, including Extra.

Layer 3 investigates the stated operations, contracts and technical dependencies. Layer 4 explores outside forces that could affect those dependencies. A hypothetical heat-network service change remains conditional unless opened evidence supports both the change and the connection to this subject. Demographic information is investigated in relation to the stated service; age or population alone does not establish a positive business outcome.

**Requirement with source preferences**

```markdown
# Research requirement — fictional
Subject: Alder Hospital Property.
Objective: understand dependencies relevant to a potential acquisition.
Focus: service continuity, operator relationships and local conditions.
Preferred sources: official authorities, operator records and utilities.
Required source to attempt: https://authority.example/alder/service-plan
Exclusion: do not turn the report into a buy/sell recommendation.
```

**Domain definitions, initial and final**

```markdown
Initial domain D-LOC: Location and access.
Responsibility: assess access, catchment and local infrastructure.
Reason: baseline real-estate plugin, tailored to the hospital requirement.

Final domain D-LOC: retain the initial responsibility.
Added domain D-OPS: Healthcare operations and continuity.
Responsibility: investigate service continuity and operator dependencies.
Reason: reviewer found a distinct operational subject in F-021 and F-088.
```

**Routed fact with provenance, and an Extra-fact reassignment**

```markdown
Fact ID: F-042.
Fact: the supplied schedule lists a purchased-heat connection.
Applicability: specified; current connection status is unconfirmed.
Source: factsheet.md, window W04, supplied schedule row 12.
Initial owner: D-SYS — Systems and operations.
Supporting meaning: the schedule describes an external utility interface.

Fact ID: F-088.
Original fact: "The operator maintains an emergency service rota."
Initial destination: Extra facts.
Final owner: D-OPS — Healthcare operations and continuity.
Reason: the reviewed mandate now covers operational staffing dependencies.
Fact body: retained unchanged; historical assignment remains in the audit.
```

**Selected source and extracted document passage**

```markdown
Source ID: S-014.
URL: https://utility.example/alder/heat-service-plan.pdf
Origin: domain scout; utility records are preferred by the user.
Domains: D-SYS and D-OPS.
Type: PDF. Next step: download, extract and inspect the relevant passages.
Limitation: source selection alone does not prove this property's connection.

Document: DOC-014; original PDF retained under sources/raw/.
Location: page 7, section "Planned service changes".
Extracted text: "Service zone Z is scheduled for network works."
Status: text extracted from page 7; other pages have separate status records.
Domain use: check whether the subject is served by zone Z before claiming an effect.
```

**Layer 4 finding and the corresponding graph edge**

```markdown
Finding: EXT-SYS-01 — Heat-service continuity.
Classification: Conditional external pathway.
External evidence: DOC-014, page 7, describes planned works in zone Z.
Layer 3 anchor: F-042 specifies purchased heat; current connection is unknown.
Pathway: planned works → heat supply → possible service-continuity exposure.
Unresolved link: whether this subject is connected to zone Z and has backup heat.
Effect and horizon: not established for the subject until those links are resolved.

Graph edge: EDGE-01.
From: utility works in zone Z.   To: subject heat-service continuity.
Intermediary: heat network.
Basis: EXT-SYS-01; DOC-014, page 7; Layer 3 anchor F-042.
Status: conditional; actual connection and backup provision remain unknown.
Other domains may reference this driver without merging different consequences.
```

The final synthesis explains this conditional relationship as conditional. It does not convert the scenario into a confirmed disruption or a quantified financial loss.

---

## 12 · What the reader receives

- A final domain catalogue explaining responsibilities and why additions were made.
- Supplied facts organized into readable domain files, with source references and visible unresolved items.
- Individual Layer 3 domain reports supported by accessible webpages and processed documents.
- Individual Layer 4 external-dependency reports.
- A separate dependency graph and a compact final synthesis.
- Source and execution records that make the results traceable.

Start with the Layer 4 final synthesis, then open the separate dependency graph to follow relationships. Use individual external reports for the underlying reasoning and Layer 3 domain reports for the subject-level findings. Source records lead to the exact webpage or document location used.

Factsheet limitations, extraction failures and unresolved assignments stay visible in their relevant records. The original files and saved model responses remain available. This gives reviewers a path from the manager-facing conclusion back to the supplied and opened evidence.

Proposed artifact names describe responsibilities and are not executable interface contracts.

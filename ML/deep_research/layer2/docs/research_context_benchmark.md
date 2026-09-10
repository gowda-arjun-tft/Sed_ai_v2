# Layer 2 V3 — fixed research-context benchmark

Version 3, 10 September 2026. Manual evaluation only; the existing schema-9 run below supplies baseline observations, not results from the revised prompt.
Retains every B01–B12 case from `plain_research_v2:ML/deep_research/layer2/docs/schema7_research_context_benchmark.md`
at commit `b66a57cbf27989b53ba505f34b32226535b3b614`.
This is a documentation-only extension, not a V2 code merge, production validator or repair loop.

## Frozen reference and scope

- Source: `runs/inputs-new-fact-sheet-93b222cb/L2_20260910_124945_4507/_internal/inputs/fact_sheet.md`.
- SHA-256: `df7320bbca373be776791d39acc104808f967fcb53d303220f96d13c5a87a3e6`; 490,449 bytes, 159,316 source tokens. Verified identical to the version-1 benchmark source.
- One-based source lines below remain valid. **Window references in B01–B12 describe the original schema-6/7 60K/10K policy**, not the current V3 policy; these cases remain relevant independent of their window.
- V3 50K/5K byte ranges [start, new-start, end): [0,0,140365], [124702,140365,285688], [271467,285688,427537], [410071,427537,490449]. Compute current source-continuity checks from the frozen manifest.
- Compare within V3 using identical source, plugin, requirements, reasoning and source policy; record prompt hashes and web actions. The broadened requirements/web-enabled designer mean older-run quality comparisons cannot isolate a single prompt change.
- Treat source as supplied evidence, not independent verification of every underlying claim. Expected placements describe responsibilities, not fixed domain names or IDs. Provenance IDs locate this benchmark's source, but are not required in normal domain Markdown.

## Cases

### B01 — Area and parking differences do not change rent

- Source: line 948, window 3; IDs `7da5e5c7`, `8655f6ad`, `554a087f`.
- Must retain: the undated lease's annexes MV 1.2(1)–(39) describe leased areas/parking; a later inspection finding different areas or parking counts gives neither party claims against the other and does not change rent.
- Acceptable paraphrase: “Under the undated lease, discrepancies from annexed areas/parking quantities create no interparty claim or rent adjustment.” Exact annex numbering may be retained separately.
- Placement: lease/income mechanics and legal rights/obligations; legitimate shared ownership is expected where these are separate responsibilities.
- Material failure: only retain inconsistent measurements or general acceptance of premises; omit either the no-claim or no-rent-adjustment qualification; infer enforceability beyond supplied evidence.

### B02 — Specific landlord fire-plan exception

- Source: lines 976–977, window 3; IDs `786542fa`, `75038e0c`, `e44cf011`.
- Must retain: tenant promptly informs landlord in writing about relevant measures/updates and escape-plan revisions; landlord must change escape-route/fire-service plans when future official requirements unrelated to tenant measures or use make changes necessary.
- Acceptable paraphrase: “Landlord handles plan changes required by future authorities where not triggered by tenant works/use; tenant must promptly give written update notices.” Both trigger and exclusion remain explicit.
- Placement: technical/fire safety and lease/legal allocation, according to the supplied responsibilities.
- Material failure: replace the exception with “tenant handles fire safety” or “landlord handles authority requirements”; omit the unrelated-to-tenant condition; treat operational evacuation instructions as the same obligation.

### B03 — Rent adjustment versus conditional payment

- Source: lines 1011–1012 and 1016, window 3; IDs `23dded8b`, `3e3c1d37`, `96645063`, `4fad13fc`, `533327db`, `1b675ee0`, `2c954eb3`, `fd6c79b3`.
- Must retain: 23 May 2025 correspondence states EUR 72,458.48 previous, EUR 5,796.69 increase and EUR 78,255.17 new amount. Section 4.2 trigger is more than 7.5%, reference index 112.7; the source states 7.54214%, rounded to 7.5%. October 2025 email says the asserted increase enters payments from January 2026 under reservation pending a signed rent addendum. Retain correspondence status.
- Acceptable paraphrase: equivalent localized numeric formatting and concise dated narrative; attribute the rounding to the source without silently repairing it.
- Placement: lease/indexation and financial cash-flow responsibilities; legal duties where reservation/addendum matters.
- Material failure: infer a signed agreement, unconditional payment or effective increase from May; conflate threshold with increase amount; call an asserted increase and reserved payment inherently contradictory.

### B04 — Different building sections are not competing estimates

- Source: lines 286–288, window 1; IDs `1911de0c`, `5e72c164`, `50a805cd`, `b633058f`, `a474e04c`.
- Must retain: indicative net estimates: Zwischenbau EUR 226,876.80; Old Building 2 EUR 1,118,963.00; Neubau EUR 2,058,879.60. Keep each figure's building section and indicative status.
- Acceptable paraphrase: separate bullets or a scoped comparison; translation of building labels with identifiable equivalents.
- Placement: asset condition/capital works and finance where capital expenditure is a specific duty.
- Material failure: turn different sections into a contradiction, silently combine them into a verified budget, swap section labels or imply commissioned/completed work. Genuine uncertainty elsewhere must remain separately scoped.

### B05 — Identity, identifiers and unequal area bases

- Source: lines 63, 65 and 148, window 1; IDs `867e6878`, `261257ed`, `6c34630e`, `2f4ee38e`, `e7553f98`, `f96bd647`, `945a11f1`, `f75b8195`, `eed92df8`, `b6098f72`, `952ef8cc`, `8f003530`.
- Must retain: Amtsgericht at Auf der Steinkaut 10–12, Bad Homburg; supplied postcode variants 61348/61352 attached to records; Gonzenheim, Flur 8, parcels 122/11 and 123/1; UA002, object 2.03, internal L2.03. Energy certificate NGF 6,047 m² differs from undated indicative area schedule NGF 7,704.08, with comparability unresolved.
- Acceptable paraphrase: one coherent identity entry plus a scoped area entry; no preference for one “correct” area/address variant without support.
- Placement: property identification/title and area-dependent lease/technical duties. Do not require identity to be copied into every domain regardless of duty.
- Material failure: lose asset association, choose one measurement silently, assert equal measurement bases, infer a different asset from a postcode variant or promote a historical record's named party into confirmed current ownership.

### B06 — Energy figures and what they include

- Source: lines 66–74, 82 (window 1), 454–455 (window 2); IDs include `30210255`, `7cf6e31f`, `67177ec7`, `baba0328`, `f7ea9f39`, `b706f6be`, `18aa2777`, `eade0dcb`, `fc709bb8`, `abcdd032`, `72408e1c`, `acc2dd24`, `f26045ba`, `351fd5a8`, `f0a7ed63`, `8dc31a5a`, `bd3a59ce`, `f39515aa`, `a7f84245`, `f723287e`, `8ff1b726`, `840509ee`.
- Must retain: gas H/electricity, decentralized electric hot water, partial ventilation/cooling, mechanical ventilation without heat recovery; renewables not stated. Heat 97, electricity 21 and primary energy 143 kWh/(m²·a) retain consumption scope; hot-water inclusion is unchecked for heat, but electricity includes hot water, ventilation, lighting, cooling/other uses without separate metering. Gas 2017/2018/2019: 507,250/475,220/517,010 kWh; 2019 electricity 121,770 kWh. Keep periods; comparison figures 70/25 are not measured consumption.
- Acceptable paraphrase: several coherent systems/consumption entries; repeated values across windows need not be repeated merely for scoring.
- Placement: energy/carbon and system-operation responsibilities; no universal financial ownership just because quantities might someday imply cost.
- Material failure: label consumption as demand, historic figures as current, “not stated” as no renewables, or omit hot-water/metering qualifications; merge different scopes into an artificial contradiction.

### B07 — Maintenance condition versus template instructions

- Source: lines 146, 149–151, window 1; IDs `bf0dcc1b`, `594829f0`, `9b50159d`, `1d2629b2`, `941930f1`, `81ce8f3a`, `95752bad`, `88a88abe`, `3799b7c0`, `9dcf8df2`, `a00d1cac`, `08ba0491`, `589bb12a`, `643f27b7`, `63c55e8a`, `a3c92206`, `cae4722e`.
- Must retain: maintenance period 24 September 2025; operator retains inspection report ten years and provides it to authority/fire department on request. Listed T0F55, Empfang EG00, 2023 facade door, TS 5000, o.BS, marked o.B. without defects. A separate template section says newly unmaintained fire doors require OL FMC release before maintenance; another section concerns inaccessible doors.
- Acceptable paraphrase: separate observed door record and conditional maintenance responsibility/approval entry.
- Placement: system maintenance/fire safety and relevant compliance responsibilities.
- Material failure: turn template categories into confirmed defects/inaccessibility for T0F55 or every door; omit approval condition or report retention duty.

### B08 — Building cover versus rent-loss cover

- Source: line 397, window 1; IDs `fcbc4ad3`, `a2899262`.
- Must retain: building/installed-equipment sum insured EUR 27,214,339; rent-loss sum EUR 2,516,434, 36-month indemnity period. These are supplied coverage amounts, not proven adequacy or an accepted claim.
- Acceptable paraphrase: two labelled figures and the period, with installed equipment retained as scope.
- Placement: insurance/insurability and lease/income exposure where those duties are separate; genuinely shared ownership is appropriate.
- Material failure: swap limits, present rent-loss sum as annual or apply its period to the building limit, claim comprehensive coverage/adequacy without evidence.

### B09 — Proposed contractor work and external approval dependency

- Source: lines 152, 159–161, window 1; IDs `3ca2500f`, `e646252e`, `8d88df04`, `20fff3c2`, `0a434f59`, `db9612a8`, `3e24c5fd`, `0c691acd`.
- Must retain: Chemicon garage-restoration offer dated 4 July 2025, not proof of award/execution; repair subtotal 249,067.51 as supplied. Offer states market evidence for product suitability is unavailable/incomplete; if commissioned, contractor supplies manufacturer-based documentation, expert planner validates against repair plan, client approves in writing before execution. ZVEI terms; electrical components outside concrete have 24-month warranty; after warranty, embedded reference electrodes are replaced only if meaningful zone-data interpretation is no longer possible.
- Acceptable paraphrase: coherent procurement/approval entry and separate conditional warranty entry; preserve actors, sequence and exceptions.
- Placement: technical restoration, procurement/external supplier dependency and contractual/cost duties where explicit. Do not copy unrelated procedures into finance solely because the offer has a price.
- Material failure: treat an offer as installed equipment or completed repair; omit a responsible party/approval condition; invent a current supply shortage or unconditional electrode replacement.

### B10 — Cross-window use right

- Source: line 420, crossing windows 1→2 at byte 174958; IDs `1d346ee6`, `6e3c5485`, `2732eeed`.
- Must retain: Land Hessen's conditionally terminable personal easement, entry 2, authorized 3 November 2006 (UR 947/2006 H); permitted office/business/practice/training/residential/technical/ancillary/parking uses, further public-law-permitted uses, and third-party exercise. Attribute to the 21 November 2025 Legal Fact Book, with its supplied weak-source qualification.
- Acceptable paraphrase: linked clauses or a completed entry in window 2; preserve authorization as a use right, not proof of actual uses.
- Placement: title/legal restrictions and tenancy/use responsibilities.
- Material failure: boundary loses a permitted use, conditional termination or third-party clause; invents actual residential use; independently treats the legal summary as verified title. Overlap duplicate entries are not a failure if meanings remain correct.

### B11 — Boundary-split identifier and adjacent door scope

- Source: lines 862–864, windows 2→3; byte 329456 cuts line 863 within its provenance text. Complete IDs `13d95729`, `1947f5da`, `4f9e8756`, `50d13b98`; adjacent door-47 record IDs `b7f6261d`, `88a86f45`.
- Must retain: door 48 (1985, TG Wasser UG02, T30-1, Z-6.12-1175, TS 5000), 49 (1989, Zugang TG UG02, T30-1, Z-6.12-1175, TS 4000), 50 (1989, TRH TG UG02, T30-1, Z-6.12-1176, TS 4000). Green checks belong to doors 44,45,48,49,50; adjacent door 47's rust/defect marks must not transfer to them.
- Acceptable paraphrase: grouped door entry with per-door attributes and separate scoped condition note. Exact supplied IDs are internal provenance; not required in normal domain Markdown.
- Placement: asset/fire-door condition and maintenance responsibilities.
- Material failure: drop/guess a cut-off ID rather than use the complete supplied continuation, exchange door attributes or infer the symbol's meaning beyond supplied legend. Correct meaning with missing source ID is reported as provenance failure, separately from semantic omission.

### B12 — Independent topics without losing a linked exception

- Source: lines 449–452 and 645 (window 2), 971–977 (window 3); representative IDs `4a0ec391`, `6cbbc71d`, `2fe19481`, `112ea628`, `27acf1cd`, `6a6c2d6a`, `0ea4d032`, `b5007671`, `8daeb155`, `b93c0557`, `e44cf011`.
- Must retain: distinguish operational fire-response instructions (alarm/fire-brigade contact and reporting hazards) from contractual allocation: tenant operates at own cost insofar as legally possible, with landlord roof/structure maintenance, servicing, inspection and renewal exception; tenant insurance cost responsibility limited by section 13. Retain B02's separate plan-change exception, not just the general roof/structure rule.
- Acceptable paraphrase: independently assignable operational and contractual entries; keep each rule with its exception. Exact emergency-script repetition is not required.
- Placement: operational procedures in system/safety duties; cost/contract boundaries in lease/legal duties, also technical duties where directly supported. Multi-domain ownership is valid, but unrelated emergency-script content should not be bundled into a contractual entry just to reach legal/finance.
- Material failure: flatten everything into “tenant responsible”, treat unrelated topics as a single inseparable entry, or delete a qualification to achieve shorter output. Evaluate topic separation, not a target entry count.

### B13 — Renewal and termination notice must stay with the term

- Source: lines 957–959; IDs `85ce2f80`, `863a5099`, `7debc4e9`, `88448fed`, `db29b0ab`, `303f3414`, `bcda928b`.
- Must retain: 30 years from possession transfer; successive three-year renewals unless terminated no later than 12 months before term-end; continued use does not produce an indefinite lease and § 545 BGB is excluded. The tenant has specified termination/partial-termination rights with 12 months' notice, including a stated time 25 years after lease start.
- Acceptable paraphrase: a concise term/renewal/notice sequence, with the tenant's separate break right and qualifications.
- Placement: lease/income and relevant legal/negotiation responsibilities.
- Material failure: retain 30/3 years but lose notice or tenant break conditions; invent an expiry from an unverified start date; treat renewal as automatic regardless of timely notice.

### B14 — Preserve repair totals and their actual scope

- Source: lines 196–201; IDs `c455b3e3`, `d38226b1`, `034c0390`, `35e18229`, `011a8754`, `be6fbac6`.
- Must retain: indicative 22 January 2026 estimate, landlord 1,151,650; tenant 736,450; combined 1,888,100. Combined timing: 158,100 immediately, 89,000 year 1, 1,323,000 years 2–5, 318,000 years 6–10. The combined figure covers the full listed repair categories, not a garage-only project. Preserve distinct category/party allocations when reported; they may appear in separate appropriate domain entries.
- Acceptable paraphrase: equivalent localized figures with the indicative date, allocation and scope intact.
- Placement: technical/CapEx and financial/investment responsibilities.
- Material failure: 1,881,100 instead of 1,888,100; call the whole sum garage costs or approved spend; swap landlord/tenant amounts; drop timing that changes negotiation or investment interpretation.

### B15 — Benefiting from a right is not being burdened by it

- Source: lines 424–425; IDs `db558f78`, `8887c162`, `faf8a2f6`, `35843a40`.
- Must retain: the supplied 21 November 2025 Legal Fact Book reports no building burdens registered against the purchase property. Separately, a burden on Gonzenheim Flur 8 parcel 115/11 benefits the purchase property with access, limited to court staff, caretaker and the caretaker's family; it may accommodate the specified energy/service connections. The benefited-property owner must construct/maintain load-bearing access kept clear for fire/rescue vehicles. Retain the legal-summary/source qualification.
- Acceptable paraphrase: two compatible statements clearly identifying burdened land, beneficiary, permitted users/connections and maintenance responsibility.
- Placement: property rights/legal, operational access and relevant utility dependencies.
- Material failure: reverse the benefit direction, call these statements inherently contradictory, infer unrestricted public access, omit rescue access/maintenance responsibility or present the supplied summary as independently checked title.

## Evaluation procedure

1. Keep B01–B15 fixed. Record source/settings/prompt hashes before a later authorized run; do not insert expected answers into production prompts.
2. Evaluate shared asset metadata plus the relevant domain content together, then inspect raw distribution responses to locate any loss. A fully qualified fact in shared metadata need not be duplicated in each domain. Information only in an unrelated domain is not automatically available to this researcher. Correct metadata does not cancel a misleading domain statement. Separate source omissions/distortions from wrong placement and publication loss.
3. Record **pass / partial / fail** for each case's meaning/qualifications, scope/contradictions and responsibility placement, with source and output quotations/locations. Any equivalent coherent wording is acceptable. Report provenance fidelity separately where available; absent technical IDs in Markdown are intentional.
4. All 15 cases must pass for a 10/10 on this fixed benchmark. It is not proof of every fact in the document or future inputs. Never remove failed cases or average away a contractual exception. Append newly discovered cases with a new version.
5. Evaluate designer-added responsibilities against supplied needs: neither zero additions nor more additions alone earns a better score. Record whether web use resolved a genuine planning uncertainty and whether external claims contaminated asset facts.
6. Count calls, web actions, usage, runtime and output volume separately. They are secondary observations, not substitutes for fidelity. No automatic grader, repair or publication gate is introduced.

Scoring excludes repeated translations/duplicate occurrences of identical meaning, routine contact/bank/signature details without a research dependency, technical window labels and repeated generic legend/emergency scripts. It does not exclude dates, quantities, conditions, actors, scope or exceptions needed for a case. This affects evaluation only; Python does not remove such content from completed responses.

Offline fake responses verify transport, routing and persistence—not real extraction or discovery quality. Any live run or paid comparison needs separate authorization.

## Schema-9 baseline for the distribution refinement

Baseline: `runs/inputs-new-fact-sheet-93b222cb/L2_20260910_160837_4961` (paths below relative to it).
Its frozen source has the SHA-256 above. It completed four metadata, one designer and four distribution jobs,
with ten domains and no routing observations. These counts do not establish semantic completeness.
The following are targeted findings, not a new full B01–B15 score. Earlier cases and exclusions remain fixed.

| Case | Source and baseline output location | Combined-context observation |
| --- | --- | --- |
| B01 | Source 948; `domains/occupier-lease-income-and-counterparty-economics.md:40` | Partial: “do not change rent” survives; neither party having claims against the other does not survive in metadata or domain content. |
| B13 | Source 957–959; same domain line 32; `asset_metadata.md:52` | Partial: renewal notice survives, but the tenant's separate break-notice period and exclusion of indefinite continuation / §545 do not. |
| B04 | Source 286–288; all domain files and metadata checked | Missing: the three separately scoped indicative net section estimates are absent. Other renovation totals do not replace them. Source 866 also associates EUR 226,876.80 with another section label; retain that ambiguity without silently relabelling estimates. |
| B14 | Source 196–201; `domains/asset-integrity-systems-and-operational-resilience.md:34,44`; `domains/finance-debt-and-macro-transmission.md:11`; `asset_metadata.md:122,165–174` | Distorted: technical line 34 correctly retains EUR 1,888,100, but line 44 calls it an “indicative project total” inside garage procurement. Finance prints EUR 1.8886 million. Correct allocations elsewhere do not repair these assertions. Metadata's garage paragraph also leaves estimate scopes unreconciled. |
| B15 | Source 424–425 and 1341–1344; `domains/rights-public-law-and-ownership-governance.md:19`; `asset_metadata.md:28,183` | Scope concern: domain text calls the records a “conflict” before establishing comparable burdened property/register scope. The later official letter references sheet 278 and must not be ignored; preserve uncertainty rather than assert either a proven conflict or proven compatibility with that letter. |
| B02/B03/B06/B08 | Relevant lease, energy and insurance domain files; source locations remain in the cases above | Regression anchors already retained include the landlord fire-plan exception, reserved payment pending addendum, historic energy periods/metering qualifications and distinct building/rent-loss amounts. This does not mark every subcriterion passed without a full case review. |

The section estimates lie entirely in V3 window 1; B01 and B13 lie entirely in window 3.
The corresponding raw distribution responses already omit them, and the published contributions preserve
the raw text. These particular losses are not chunk-boundary or Python assembly losses. The precise model-internal
cause is unobservable. Metadata is deliberately an overview, not a replacement for detailed source distribution.

For a later authorized comparison, freeze this run's four original source windows, final metadata, usable domain
plan and model/settings; vary only the distribution prompt. Save four new distribution responses and evaluation
separately, without changing or resuming the baseline. Record both prompt hashes and exact request dependencies.
Check all B01–B15 against combined context, including regressions; report fidelity before token/call differences.
If material omissions persist, test smaller distribution windows only as a separately authorized next experiment.
No live comparison, source-verification stage or production quality gate is introduced here.

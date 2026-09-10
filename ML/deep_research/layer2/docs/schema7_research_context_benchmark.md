# Layer 2 V2 — fixed research-context benchmark

Version 1, frozen 10 September 2026, before any prompt-comparison model calls.
This is a manual, source-backed evaluation inventory, not a production validator or repair loop.
Current result: **not evaluated against a fresh model run**.

## Reference material

- Frozen source: `runs/inputs-new-fact-sheet-9563041d/L2_20260909_171314_855f/_internal/inputs/fact_sheet.md` (repository-relative).
- SHA-256: `df7320bbca373be776791d39acc104808f967fcb53d303220f96d13c5a87a3e6`.
- Source size: 490,449 bytes; 159,316 `o200k_base` tokens. Locations below are one-based lines in that file, not exact fact byte offsets.
- Window 1: source bytes [0,174958); window 2: [140365,329456); window 3: [299878,490449). New material starts at 0, 174958 and 329456 respectively. The latter two boundaries cross lines 420 and 863.
- [Schema-7 audit and completed schema-6 comparison](260909_Layer2_Schema7_Run_Audit_171314.md): schema-7 run above versus schema-6 `L2_20260909_123721_13fb`, using identical source/plugin/requirements and model settings. Its two material omissions motivated cases B01/B02.
- [Earlier schema-6 audit](260909_Layer2_Schema6_Run_Audit_ENG.md): different, partial run `L2_20260909_065353_b707`. Its omission candidates are historical leads, not automatically confirmed failures in the completed comparator.

Use the frozen source as supplied evidence, not proof that every underlying document claim is true. Preserve weak, undated or proposed status where material. Cases may span several evidence entries; do not demand exact wording, entry count or fixed domain IDs. Responsibility labels below describe duties, not mandatory domain names. Assess the actual plugin-derived definitions.

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

## Evaluation procedure and exclusions

1. Verify source, plugin, requirements, settings and window policy match the baseline; record prompt hashes separately. Evaluate frozen cases without inserting expected answers into production prompts.
2. For each case inspect all understanding responses/ledger entries, initial/final owners and corresponding domain Markdown. Record actual fact IDs and quotations. Separate extraction omissions, distortions, ownership errors and publication loss. A meaning found in another coherent entry counts; keyword absence alone does not prove omission.
3. Mark each case **pass / partial / fail** for meaning and qualifications, scope/contradictions, responsibility placement, and internal source-ID fidelity. A case passes only when all must-retain meanings survive, there is no material distortion and relevant responsibility placement is usable. Give a reason and output references for every partial/fail.
4. Report each dimension and the number of fully passing cases out of 12; do not average away a missing contractual exception. A requested 10/10 means all these fixed cases pass, not exhaustive accuracy for the entire source or future inputs. Do not remove failed cases or revise weights after seeing results; append discoveries as a separately versioned expansion and retain original results.
5. Record prompt/input/cached/output tokens, runtime, calls, reviewer tool operations and domain-token volume separately. Lower counts are secondary measures, not success criteria. No automatic semantic grader, repair or publication gate is introduced.

Excluded from the score: repeated translations/duplicate occurrences of the same meaning; routine contact details, bank routing and signatures unless they establish a research dependency or responsibility; technical window offsets and file labels; repeated generic legend/emergency wording without an additional asset-specific condition. These exclusions reduce score noise, not production evidence: no fields or entries are deleted by Python. Do not exclude dates, responsible parties, exceptions, quantities or provenance needed by a case. Source contradictions and ambiguities are preserved, not corrected using outside research.

Offline fake responses establish contract/persistence behavior only. They cannot establish that a real model extracts these cases correctly. Any live comparison, spending or extra verification stage needs separate authorization.

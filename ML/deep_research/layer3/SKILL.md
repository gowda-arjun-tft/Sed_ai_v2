---
name: cdi-domain-storm-research
description: Mandatory STORM procedure for property-specific risk research in one CDI domain.
---

# CDI domain-scoped STORM research

## Objective

Produce one compact Markdown report of current and emerging risks that reach the value of the
assigned property through its assigned domain. Find what retrieved evidence adds, contradicts or
dates about this address; expose disagreement; verify citations and property linkages; and preserve
material uncertainty. Supplied defects are anchors to research outward from, not findings.

## Procedure

1. Extract the explicit property anchors, supplied facts, contradictions and research questions from
   the assignment. Write the address, district, parcel, occupier, named systems and named suppliers
   as a compact anchor block. Do not convert missing input into a property finding.
2. Send one `task` call to each of `practitioner`, `academic`, `skeptic`, `economist`, and
   `historian`. Emit all five calls in the same response so the independent briefs can run in
   parallel. Each task carries the mission, mandate, handoffs, the anchor block, the applicable time
   horizon, one lens-specific research question, and the boundary of what the other four lenses own
   so the briefs compose instead of overlapping. Instruct each lens to research outward from the
   anchors rather than re-auditing the supplied file.
3. Compare the five returned briefs. Separate supplied property facts, newly discovered external
   facts, property-risk inferences and unknowns. Map direct conflicts, evidence strength, duplicate
   causal chains, unsupported context and blind spots.
4. Draft only findings that follow: new evidence → property fact → exposure → vulnerability →
   effect on building, people or operations → value transmission → time horizon. Treat information
   without that linkage as context only. One finding is one root cause: where candidate findings
   share a root cause, a common trigger or the same absent record, they are a single finding whose
   distinct effects are listed inside it, never siblings. Four separate blocks for fire doors, smoke
   extraction, fire alarm and electrical protection are one finding on incomplete statutory safety
   assurance.
5. Review the draft for unsupported claims, lost disagreement, repeated input, double counting,
   missing property linkages and generic national or macro commentary, then revise it. Delete every
   line that carries no name, date, quantity, identifier, classification or source link, and every
   finding that would read the same about another comparable building.
6. Group the draft's cited claims and sources into coherent verification clusters. Send one `task`
   call per cluster to `citation-verifier`, emitting the calls in one response. Include the exact
   claims, property linkages, value transmissions, quotations, source titles and URLs in each task.
7. Apply the verifier findings, preserve unresolved limitations, and return the complete corrected
   domain report directly as the final Markdown response.

The coordinator researches through its fixed subagents and does not search the web directly.
Lens briefs and verifier verdicts are evidence for coordinator judgement, not structured status
envelopes or application-controlled artifacts. The final assistant response is authoritative.

## Final domain report

Return these sections:

1. `# <Domain name>`
2. `## Domain risk picture` — a brief property-specific conclusion.
3. `## Property-linked risks` — one compact block per root cause containing:
   - `Risk finding`
   - `New/current evidence`
   - `Existing property fact`
   - `Property linkage`
   - `Value transmission` — income, recoverability, CapEx, loss of use, insurability, compliance
     cost or liquidity/exit, with the mechanism and the direction of effect
   - `Likelihood: Low | Medium | High | Unknown`
   - `Impact: Low | Medium | High | Unknown`
   - `Affected building, people, operations or economics`
   - `Time horizon and status`
   - `Sources`
4. `## Contradictions and material unknowns`
5. `## Evidence gaps` — one table, columns `| Gap | Blocks which finding | Where the record lives |`
6. `## Supplied anchors with nothing found` — one line per anchor retrieved evidence could not extend
7. `## No material pathway established` — use when researched information remains context only.

Unresolved records belong in the evidence-gaps table, once, never as prose inside a finding. Write
telegraphically: fact fragments over sentences, each fact stated once, no connective filler and no
narration of what the research did or could not establish. Retain direct Markdown source links. Do
not include recommendations, mitigations, action plans, owners, decision gates, approval or
rejection language, repricing, or an investment conclusion. Existing safeguards may be reported only
as facts relevant to exposure or vulnerability.

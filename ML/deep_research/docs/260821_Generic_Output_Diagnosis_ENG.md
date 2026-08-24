# Why the research output is generic — diagnosis

No code changed. Evidence: the live run `runs/inputs-1-.../L3_20260821_124129_5d66`
(231 queries, 8 domain reports), its prompts, and 4 web searches of my own.

## Verdict

You are right on both counts. **It is a prompt problem, and it is in both layers.**
The method (STORM fan-out, coordinator, verifier) is fine. The prompts point every
agent at the **domain in general** instead of **this building, this street, now** —
so the system researches German law and macro statistics, restates the fact sheet,
and never looks out the window.

One number tells the whole story: **of 231 search queries in the run, zero were
about current or upcoming events near the property.** I then spent 4 searches of
my own and immediately found two material, findable facts the run missed.

---

## Proof: what 4 searches found that 231 missed

**1. A light-rail construction site is opening in the courthouse's own district.**
The U2 extension (Gonzenheim → Bad Homburg Bahnhof, 1.6 km) had its groundbreaking
on **9 December 2025**. Through **2026**: the Gonzenheim station is dismantled, a
drainage canal is relocated, and works on Frankfurter Landstraße begin
**05.08.2026** — all in the property's district. Access, noise, parking and court
operations during the hold period; improved transit after.
([bad-homburg.de](https://www.bad-homburg.de/de/stadt/aktuelles/spatenstich-fuer-die-verlaengerung-der-u2-oz5mnkkyvr),
[bad-homburg-u2.de](https://www.bad-homburg-u2.de/das-projekt.html),
[vgf-ffm.de](https://www.vgf-ffm.de/en/news/planned-construction/bad-homburg-construction-project/))

**2. The city's own development framework names this property.** "Bad Homburg
2030" proposes a **new S-Bahn stop "Steinkaut"** explicitly to serve *"regional
bedeutsame Ziele (Amtsgericht, Kaiserin-Friedrich-Gymnasium, ... Taunus Therme)"*,
plus the **"Bornberg" development area** in the land-use plan and a model quarter
for car-reduced living around the stop.  A value-relevant, official, public plan
that names the asset — unfound.
([badhomburg2030.de — Idee: Neuer S-Bahn-Halt "Steinkaut"](https://badhomburg2030.de/topic/nord/thought/7679),
[badhomburg2030.de/topic/nord](https://badhomburg2030.de/topic/nord))

Neither is exotic. Both sit on the city's own websites, in German, one query away.
The run never asked because **no prompt ever tells any agent to look**.

---

## Where the 231 queries actually went

| domain | queries | what they were |
|---|---|---|
| Energy & Carbon | 39 | **All law**: GEG §71a, GEIG, EPBD 2024, KfW/BAFA funding, Hessen Solarpflicht — applies to every non-residential building in Germany |
| Ground & Climate | 39 | The best domain: real address-specific hazard-map and Altlasten queries |
| Finance & Debt | 34 | **All macro**: ECB rates, Bundesbank lending surveys, Destatis GDP, EBA/BaFin guidelines — a textbook, not this property |
| Occupier & Lease | 35 | Generic German public-lease law; the historian lens drifted to *"Eisenhardt Castle 1895 lease Prussian justice authorities"* |
| Rights & Public Law | 31 | Decent: Bebauungsplan 117, Heilquellenschutz 1985 — address-specific |
| Location & Market | 32 | Market reports; **one** query touched the new Justizzentrum question, none followed up |
| Asset Integrity | 18 | Law lookups (BetrSichV, GaVO, TPrüfV, DIN 14675) |
| **Geopolitics & Dependencies** | **3** | All three about the Schwimmbadweg fire-alarm line. **The domain you flagged effectively did not run.** |

Zero queries against local news, the city council, the planning portal, event
calendars, or construction announcements. Zero containing "2026" with the town
name. The system is structurally blind to *now* and *nearby*.

---

## Root causes, each anchored to a prompt line

### Layer 2 — the mission itself is generic (you were right)

Open your own file:
`mission_md/asset-integrity...md` begins with **nine consecutive paragraphs that
all say the same thing** — *"Establish the current condition, compliance,
capacity, inspection status..."* nine times with shuffled word order.

Cause: [chunk_router.md](../layer2/prompts/chunk_router.md) says *"Make each
non-empty mission specific to what that domain must establish **from this
chunk**"* — so every chunk writes its own mandate paragraph and the merge
concatenates all nine. A researcher receiving "establish everything, nine times"
produces "everything, generically."

What the mission never contains: **questions**. The fact sheet is full of hooks —
garage gate failed, €1.888m programme unindexed, SV-Prüfungen missing,
Trinkwasser/Löschwasser unseparated (€77,000), parking split inconsistent — and
the mission transcribes them as context instead of raising them as *the things to
answer*. Nothing instructs the router to extract discrepancies, anomalies and open
questions as first-class output.

Also missing entirely from the mission: an **address/geo block** (street,
district = Gonzenheim, parcel, neighbours). Without it, no downstream agent has
the search anchor for "nearby."

### Layer 3 — five prompt defects

**1. The lenses aim at the domain, not the property.**
[academic.md](../layer3/prompts/lenses/academic.md): *"Establish what governing
authorities, technical standards, official statistics... support for the
domain"* → 39 law queries. [economist.md](../layer3/prompts/lenses/economist.md):
scenario/transmission language → 34 ECB/Bundesbank queries.
[historian.md](../layer3/prompts/lenses/historian.md): *"precedents, cycles"* →
Prussian castle leases from 1895. Each lens does exactly what its prompt says —
and no prompt says **"about this address."** That is the genericness, mechanically.

**2. No environmental scan exists anywhere.** No prompt — not SKILL.md, not
shared_rules, not any lens — contains the concepts *nearby*, *current*,
*upcoming*, *news*, *construction*, *events*, *planning applications*. What you
asked for ("what is going on around it that affects the building and the people
in it") is not a hard research problem; it is an **uninstructed** one.

**3. The vocabulary still cannot say "risk."**
[shared_rules.md](../layer3/prompts/shared_rules.md) asks for *"established
facts, reasoned inferences, unknowns, immaterial matters"* — an evidence-status
vocabulary. Risk severity, likelihood, "no risk here" remain unsayable, so every
report reads as an evidence audit instead of a risk register.

**4. SKILL.md orders the advice you don't want.** Its final-report spec demands
*"scenarios, handoffs, and **actions**"* — which is where *"Do not approve final
acquisition..."* comes from. You asked for research that points out risks, not an
underwriting memo. The prompt requests the memo.

**5. The geopolitics domain is starved by design.** Its Layer 2 mission is nearly
empty (the sheet says nothing geopolitical), the prompt says "research the
mission," so it made 3 queries and stopped. Nothing translates "geopolitics" into
what it concretely means for a German public building: Land Hessen budget stress
and court-structure reform (tenant continuity), energy supply, sanctioned or
single-source building-technology vendors, cyber exposure of court IT,
demonstration/security risk at a justice site. The lens roster
(practitioner/academic/skeptic/economist/historian) contains no
outward-looking perspective at all.

### The one thing that is *not* prompt

The nine-fold mission duplication is mechanical (chunk-merge concatenation without
dedup) — fixable either by a one-line merge change or by a router-prompt
instruction to write questions instead of mandates. Everything else above is
prompt.

---

## Areas of improvement, ranked

| # | change | layer | fixes |
|---|---|---|---|
| 1 | **Missions become questions.** Router extracts, per domain: (a) verbatim facts as now, (b) a deduplicated list of *specific open questions and anomalies* ("the garage gate failed — status, cost, operational impact?"), (c) an address/geo block. One mission paragraph, not nine. | L2 | generic missions, restatement |
| 2 | **Add an environmental-scan duty to every domain** (or one shared lens): "Search for current and planned events within the property's district and town — construction, transport, planning applications, city-council decisions, local news from the last 24 months, announced projects for the hold period. Name what you checked and found nothing on." The U2 and S-Bahn finds above are the acceptance test. | L3 | nearby/current blindness |
| 3 | **Point every lens at the property.** One added sentence per lens: "Every search and every finding must connect to this address, its occupier, or its immediate market. National frameworks only when this building deviates from them — never recite a framework that applies to every building in Germany." | L3 | law/macro recitals |
| 4 | **Risk-register output contract.** Findings as `risk: none/low/med/high` + fact + one-line effect on the building or its people + source. Delete "actions/scenarios/handoffs" from the final-report spec. "No risk found — working as documented" becomes a legal one-line finding. **No recommendations section.** | L3 | advice instead of research, no-risk unsayable |
| 5 | **Give geopolitics a concrete checklist** in its domain prompt: tenant-state budget and court reform, energy dependence, vendor/sanctions exposure of installed systems (the BMA is Siemens), cyber/physical security environment of a justice building. Silent fact sheet ⇒ these questions still run. | L3 | the empty domain |
| 6 | **Anti-restatement rule** in shared_rules: "The fact sheet is known to the reader. Report only what public evidence adds, contradicts, or dates. Never re-describe the property." | L3 | reports that echo the input |
| 7 | Dedup the merged mission mechanically (belt to #1's braces). | L2 | nine-paragraph mandates |

Everything already working stays: the search discipline is genuinely good
(`site:` operators, primary sources, German-language queries), Ground/Climate and
Rights show address-specific research is *possible* with the current tools — the
other domains were simply never told to do it.

## Acceptance test for the next run

1. ≥3 queries per domain containing the town or district name plus a
   time anchor (2025/2026/news/geplant).
2. The U2 works and the "Steinkaut" S-Bahn proposal appear in Location's report —
   they are one query away and the city names the courthouse itself.
3. Geopolitics ≥10 queries against its checklist.
4. Zero sentences of acquisition advice; every finding carries a risk verdict,
   including explicit `no risk` lines.
5. No report restates a fact-sheet fact without adding public evidence to it.

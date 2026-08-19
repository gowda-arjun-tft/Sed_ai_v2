# Phase 4 — checks and the run record

No model. Ordinary code.

```
Input     everything in runs/<run_id>/
Happens   the run is checked end to end and the record is completed
Output    runs/<run_id>/run.json          completed
          runs/<run_id>/check_report.md   what passed, what failed
```

---

## The one check that matters most

**Every fact in the fact sheet reaches at least one bucket, or is recorded as unrouted.**

```
### blocks in the fact sheet
  = blocks in routed pieces + blocks in set-aside sections

blocks in routed pieces
  = facts appearing in at least one bucket + entries in _unrouted.md
```

Both sides are counted by code. Nothing here depends on the model reporting its own work
correctly.

This is the only failure in the whole run that is invisible afterwards. A fact that never reached
an agent looks exactly like a fact no researcher found — and fourteen researchers will produce a
confident report with a hole in it that nothing downstream can detect.

Everything else in this list can be spotted by reading the output. This one cannot.

## The full check list

### Inputs

| # | Check |
|---|---|
| 1 | Both input files present in `inputs/`, hashes match the originals |
| 2 | `planner_prompt.md` holds exactly fourteen agent definitions |
| 3 | The fourteen names match the frozen list character for character |

### The cut

| # | Check |
|---|---|
| 4 | Every `###` block is in exactly one piece file or one set-aside section — never both, never neither |
| 5 | Total block count across pieces and set-aside sections equals the count in the original |
| 6 | Every piece carries its parent `##` heading |
| 7 | Every set-aside section has a recorded reason |

### Routing

| # | Check |
|---|---|
| 8 | Every row in `progress.csv` is `done` |
| 9 | Per piece, `facts_routed + facts_unrouted` equals `facts_in_piece` |
| 10 | **Every fact block in every bucket appears character for character in a piece file** |
| 11 | Every routed fact reached at least one bucket |
| 12 | `_unrouted.md` count is reported, with each reason |

### Missions

| # | Check |
|---|---|
| 13 | Fourteen mission files, one per agent name |
| 14 | Every `agent` value is one of the fourteen frozen names |
| 15 | **Every `context[].fact` appears character for character in that agent's bucket** |
| 16 | Entry count equals the bucket's fact count |
| 17 | Every `mission` field is non-empty |
| 18 | An empty `context` is accompanied by a mission saying the fact sheet is silent |
| 19 | Every `context[].where` locator resolves to a real line in the original fact sheet |

Checks **10** and **15** are the transcription guards. Together they prove that a fact went from
the fact sheet, through a bucket, into a mission without being reworded on the way.

## `check_report.md`

Written whether or not everything passed.

```markdown
# Run L2_20260819_a3f1 — check report

19 checks · 19 passed · 0 failed

## Coverage
fact sheet blocks           412
  routed                    381
  set aside                  27      Not covered, Audit appendix, 4 others
  unrouted                    4      listed below

## Buckets
Building condition, capital expenditure & warranty      88 facts
Occupier, lease & income                                61
…
Geopolitical, trade & supply chain                       0      empty, mission written
```

The bucket sizes are worth reading even when everything passes. A wildly uneven distribution — one
agent with two hundred facts and six agents with none — is not a failure, but it says something
about either the property or the routing, and it is better seen now than after seventy researchers
have run.

## `run.json`, completed

```json
{
  "run_id": "L2_20260819_a3f1",
  "started_at": "2026-08-19T09:42:11Z",
  "finished_at": "2026-08-19T09:58:40Z",
  "model": "gpt-5.6-luna",
  "deepagents_version": "0.7.7",
  "fact_sheet": { "bytes": 65824, "sha256": "…", "blocks": 412 },
  "pieces": 9,
  "sections_set_aside": 6,
  "model_calls": { "routing": 9, "missions": 14 },
  "facts": { "routed": 381, "set_aside": 27, "unrouted": 4 },
  "buckets": { "…": 88, "…": 61 },
  "checks": { "run": 19, "passed": 19, "failed": 0 }
}
```

## What a failure means

| Failing check | What it means | Recovery |
|---|---|---|
| 3 | the roster does not match the design | stop. Fix `planner_prompt.md`, restart |
| 5 | the cut lost or duplicated blocks | stop. A splitter bug — do not route on top of it |
| 9 | the agent skipped facts in a piece | re-run that piece into fresh buckets |
| 10 or 15 | a fact was reworded on the way | re-run the affected step; if it recurs, the pieces or buckets are too large |
| 11 | a fact reached nothing and was not recorded | the worst outcome. Find it, and fix why it was silently dropped |
| 13 | a mission is missing | re-run phase 3 for that agent alone |
| 18 | an empty bucket produced an empty mission | re-run that mission with the prompt corrected |

**A failed run is not partly delivered.** `missions/` is either complete and checked, or it is not
handed to Layer 3. Fourteen researchers started against an unchecked set of missions produce work
that has to be thrown away.

## Once this is built

Two things in the design document need updating, because building this changes them:

1. **"One request, never split" is replaced.** The reason for that rule was that a fact belonging
   to two agents must be visible as such. The bucket method meets it differently — every routing
   step sees all fourteen definitions and may append one fact to several buckets. Update section 3
   of the design.

2. **The run layout is no longer undesigned.** The design lists "the folder layout on disk" as not
   yet designed. Phase 0 settles it, and it should be moved out of that list.

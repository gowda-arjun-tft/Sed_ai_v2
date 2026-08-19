# Phase 0 — the run folder and the two inputs

No model. Ordinary code.

```
Input     a claims JSON file, from anywhere on disk
          planner_prompt.md, from the repository
Happens   a run folder is created and both inputs are copied into it
Output    runs/<run_id>/inputs/ containing both files, and run.json
```

---

## The run folder

Every run gets its own folder, named so two runs can never overwrite each other:

```
runs/L2_20260819_a3f1/
```

`L2` for Layer 2, the date, and four random characters. The date makes runs sortable and the
random suffix makes a collision impossible when two runs start in the same minute.

**Everything the run touches lives inside this folder.** The agent's filesystem route is anchored
here, so it cannot read or write anything outside it.

## The two inputs are copied, not referenced

```
runs/L2_20260819_a3f1/inputs/
  claims.json            copied from wherever it was produced
  planner_prompt.md      copied from the repository
```

Copying rather than pointing at the originals means a finished run is self-contained. Six months
later the claims input may have been regenerated and `planner_prompt.md` may have been edited; the
run folder still shows exactly what was used.

Neither copy is ever modified after this phase.

### `claims.json`

The output of Layer 1 for one property. It is either a list of non-empty claim objects or an object
with a `claims` list. Claim keys are unrestricted and are preserved without interpretation.

Record its size and a hash in `run.json`, so it can be proved later that the run used the file it
claims to have used.

### `planner_prompt.md`

One file, stored and change-tracked with the code, holding everything that does not change from
one property to the next:

- the rules — all fourteen agents run on every property · "nothing found" is a valid result ·
  never report that something does not exist · a general fact is not a finding
- the **fourteen agent definitions**, in a fixed order, each with `name`, `establishes`,
  `do_not_cover`, `take_as_given`, `web_sources`
- the required structure of a mission

This file is read twice: phase 2 uses the definitions to route facts, phase 3 uses them to write
missions. It is passed as part of the system prompt, not as a file the agent reads, so it is
present on every model call without the agent having to fetch it.

**It is the only place the agent definitions exist.** Two copies drift.

## `run.json`

Written at the start and updated at the end.

```json
{
  "run_id": "L2_20260819_a3f1",
  "started_at": "2026-08-19T09:42:11Z",
  "input": {
    "source_path": "…/claims.json",
    "bytes": 65824,
    "sha256": "…",
    "claims": 42
  },
  "input_file": "claims.json",
  "input_format": "json",
  "planner_prompt": { "bytes": 0, "sha256": "…" },
  "model": "gpt-5.6-luna",
  "deepagents_version": "0.7.7",
  "agent_count": 14
}
```

## Checks before phase 1 starts

1. The run folder did not already exist.
2. Both input files copied, and their hashes match the originals.
3. `planner_prompt.md` contains exactly fourteen agent definitions, and the fourteen names match
   the frozen list in the design document character for character.
4. `claims.json` is valid JSON and contains at least one non-empty claim object.

A failure at check 3 stops the run. A wrong or missing agent name here becomes a missing mission
at the end, and it is much cheaper to catch now.

## What can go wrong

| Problem | What happens | What to do |
|---|---|---|
| JSON is invalid or has no claims | phase 1 has nothing safe to route | stop, and look at how Layer 1 produced it |
| `planner_prompt.md` has thirteen or fifteen definitions | the roster does not match the design | stop at check 3 |
| an agent name differs by a character | phase 3 writes a mission nothing downstream will accept | stop at check 3 |
| the run folder exists | a previous run would be overwritten | generate a new suffix and retry |

# Phase 2 — routing facts into fourteen buckets

The agent. One model call per piece.

```
Input     runs/<run_id>/pieces/pNNN_*.md          one piece at a time
          the fourteen agent definitions           in the system prompt
Happens   for each fact in the piece, the agent decides which agents need it
          and appends it to their buckets
Output    runs/<run_id>/buckets/<agent-name-slug>.md    fourteen files, growing
          runs/<run_id>/progress.csv                     one row updated per piece
```

---

## What happens, step by step

```
read progress.csv, find the first piece still "pending"
        │
        ▼
read that piece                             read_file, built in
        │
        ▼
for each ### block in it:
    which of the fourteen agents needs this fact?
    append it to each of their buckets      append_to_bucket, custom
        │
        ▼
mark the piece done, with a count           mark_piece_done, custom
        │
        └──► next pending piece, until none remain
```

The agent holds **one piece plus the fourteen definitions**. It never holds the fact sheet, and
never holds a bucket. The buckets grow on disk.

## A fact may go to several buckets

This is the point of the design, not an edge case.

The garage award — *"Angebotssumme gesamt: 702.668,06 EUR (netto)"* — belongs to
**Building condition, capital expenditure & warranty** because it is what the repair costs, to
**Occupier, lease & income** because whether it is recoverable from the tenant decides who pays,
and to **Market, valuation & exit** because it bears on the valuation.

All three get the same fact, copied exactly, with the same locator. Each will draw its own
conclusion inside its own subject.

**Every routing step sees all fourteen definitions**, which is what makes this possible. This is
how the design's original requirement — that a fact belonging to two agents must be visible as
such — is met without sending the whole fact sheet in one request.

## A fact may go to no bucket

Some facts belong to no agent. That is a real answer, and it is recorded rather than passed over
in silence: the agent appends it to `buckets/_unrouted.md` with one line on why.

Phase 4 reads that file. A handful of entries is normal. A large number means either the roster
has a gap or the routing is going wrong, and either is worth knowing before fourteen researchers
are started.

## The two custom tools

### `append_to_bucket`

```python
@tool(parse_docstring=True)
def append_to_bucket(agent_name: str, fact_block: str, reason: str) -> str:
    """Append one fact to one agent's bucket.

    Args:
        agent_name: Exactly one of the fourteen agent names. Any other value is rejected.
        fact_block: The complete ### block, copied character for character from the piece.
        reason: One short line on why this agent needs it.
    """
```

**Why a tool rather than `edit_file`.** Appending with `edit_file` means reading a file that grows
all run, rewriting it whole, and doing that once per fact. It is slow, it puts the growing bucket
back into the context window every time, and `edit_file` with an empty `old_string` corrupts the
whole file on every backend. A dedicated append does none of that.

**Why `agent_name` is validated in the tool.** The fourteen names are frozen strings. Validating
here turns a wrong name into an immediate error the agent can correct, instead of a fifteenth
bucket file nobody notices until phase 3.

**Why `reason` is required.** It costs one line and it makes the routing auditable. When a
researcher later asks why it was given something, the answer is in its bucket.

### `mark_piece_done`

```python
@tool(parse_docstring=True)
def mark_piece_done(piece_id: str, facts_routed: int, facts_unrouted: int) -> str:
    """Record that a piece has been fully processed.

    Args:
        piece_id: The piece id, e.g. "p003".
        facts_routed: How many ### blocks from this piece went to at least one bucket.
        facts_unrouted: How many went to none.
    """
```

The ledger is what makes the run resumable. It is kept out of the model's file-writing path so a
bad edit cannot corrupt it.

## The system prompt

The harness supplies no base prompt since v0.7 — with `system_prompt=None` the model gets nothing.
What is written here is all there is.

It contains:

- **the role** — you are allocating facts to fourteen research agents
- **the fourteen definitions**, verbatim from `planner_prompt.md`: name, `establishes`,
  `do_not_cover`, `take_as_given`
- **the work loop** — read the next pending piece, route every fact in it, mark it done
- **the routing rules**, below
- **the output rule** — you produce nothing but tool calls in this phase

The definitions are the largest part and they are the part that matters. Argument descriptions in
the tool schema teach usage better than examples in the prompt, so the prompt states each thing
once and does not repeat what the schemas already say.

### The routing rules

1. **Copy the fact exactly.** The evidence, source, locator and interpretation go across character
   for character. Nothing is summarised, shortened or reworded on the way into a bucket.
2. **Send a fact to every agent whose subject it touches.** Not the single best fit.
3. **Use `do_not_cover` to decide.** If a definition says a subject belongs to another agent, the
   fact goes to that other agent, not this one.
4. **A fact that belongs to nobody goes to `_unrouted.md`,** with a reason.
5. **Never invent a fact, and never merge two.** One `###` block in, the same block out.
6. **Route every block in the piece before marking it done.** The count in `mark_piece_done` must
   equal the number of blocks in the piece.

## Planning is switched on

`TodoListMiddleware` is added. The tool itself does nothing — it writes a list into state and
echoes it back — and LangChain's evals found it slightly worse and more expensive on short tasks,
which is why it is opt-in since v0.7.

It is worth it here for two reasons. This run is twenty to thirty steps over a long horizon, which
is the case the middleware exists for. And the list in state is what a progress display reads while
the run is going.

Import it from `langchain.agents.middleware`, not from `deepagents` — 0.7.7 does not re-export it.

## Resuming after a crash

`progress.csv` is the record. On restart, the agent reads it and starts at the first piece still
marked `pending`. Pieces already done are not re-read and their facts are not appended twice.

This matters because the buckets are append-only. Re-running a piece would duplicate every fact in
it, and a duplicated fact in a bucket becomes a duplicated fact in a mission.

## Checks before phase 3 starts

1. Every row in `progress.csv` is `done`. None left `pending`.
2. For every piece, `facts_routed + facts_unrouted` equals the `facts_in_piece` counted by code in
   phase 1.
3. Every fact block in every bucket appears character for character in some piece file.
4. `_unrouted.md` has been read by a human, or its count is zero.

Check 2 is the one that catches a silently skipped fact, and it is only possible because phase 1
counted the blocks with code before the model ever saw them.

## What can go wrong

| Problem | What happens | What to do |
|---|---|---|
| the agent summarises a fact into a bucket | check 3 fails on an exact-match comparison | fix the prompt; the rule is already there, so this means the piece was too large |
| a fact is routed to one agent when it belongs to three | nothing fails. The researchers that needed it never see it | this is the real risk of the phase. Keep pieces small enough that the model is not rushing |
| the agent marks a piece done early | check 2 fails | it is caught, and the piece can be re-run into fresh buckets |
| a bucket ends up empty | possible and sometimes correct — no property has material on every subject | phase 3 handles it. See that plan |
| a run is restarted without reading `progress.csv` | every fact is appended twice | make resume the only start path, so there is no way to skip the ledger |

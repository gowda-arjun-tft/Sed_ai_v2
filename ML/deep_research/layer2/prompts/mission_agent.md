# Your task

One property's fact sheet is in your run folder. Turn it into fourteen research missions — one per
agent on the roster below.

## Where things are

| | |
|---|---|
| The fact sheet | `/run/inputs/fact_sheet.md` |
| Where missions go | `/run/missions/<agent-name-slug>.json` |
| Scratch space, if you want it | `/run/staging/` |

Your file tools (`read_file`, `write_file`, `ls`, `glob`, `grep`) use those `/run/…` paths.
`read_file` takes an offset and a limit, so any part of the sheet can be read on its own.

`run_python` runs in a separate process on the real filesystem, where the same folder is
`{run_dir}`. Use that path in code.

## The one rule about your own head

**Keep the source text in any single context under about 20,000 tokens.**

Not because anything truncates — nothing does, and nothing will reject you for going over. Because
attention decays long before the context window is full. A head holding 300,000 tokens of fact sheet
answers worse than one holding 20,000, and it cannot tell that it is doing so.

Two things then happen on their own, quietly, and neither raises an error:

- Any single tool result over **20,000 tokens** is moved out to a file and replaced by a pointer. So
  reading half a large sheet in one call does not put it in your head anyway — it puts a path there.
- If the conversation ever reaches **about 892,000 tokens** (85% of this model's 1,050,000-token
  input), the harness summarises to survive and **keeps only the most recent tenth**. Not the older
  half — roughly the older *nine tenths* are replaced by a summary. A fact you read early stops
  existing, and nothing tells you it is gone.

**Forgetting looks exactly like success**, which is why this rule is written down.

So: never hold the whole sheet if the whole sheet is large. Read what you need, or hand the reading
to a helper whose head starts empty.

## Measure before you read

You have Python and it does not get tired. Ask it first:

- how long is the sheet?
- how many `###` fact blocks does it hold?
- what are the section headings, and at what line does each start?

That costs you a few hundred tokens no matter whether the sheet is 16,000 tokens or three million.
Now you know which shape of work you are in before you have spent any attention.

**Do not make yourself count. Do not make Python judge.** Python counts, finds, diffs and checks.
You decide what belongs where.

## Then pick your shape

**If the sheet fits comfortably in one head** — read it and write the fourteen missions. One sitting,
no helpers, no staging. This is the common case and it needs no machinery.

**If it does not** — spread it so that no head ever holds too much:

1. Cut it at **section headings**, not at a byte count. A heading is where one thought ends.
   Roughly 20,000 tokens per slice.
2. Give each slice to a fresh `slice-reader`. Tell it the slice bounds and where to write. It reads
   only that slice, decides which agents each fact belongs to, and writes its findings to
   `/run/staging/<slice-name>/<agent-slug>.json`. **Each slice-reader writes only inside its own
   folder** — that is what lets many of them run at once without ever colliding.
3. Then give each of the fourteen agents to a fresh `mission-writer`. It gathers that one agent's
   facts from across the staging folders and writes `/run/missions/<agent-slug>.json`. It reads only
   its own subject, never the other thirteen.

Several `task` calls in one message run in parallel.

Two notes on your helpers. **Neither can delegate further** — they have no `task` tool, so any
splitting has to be decided by you before you hand work over. And a **general-purpose** helper also
appears in the `task` list: it has the same tools but knows nothing about this job, so tell it
everything or prefer the two named above.

Both helpers do have `run_python` and the same file tools you do. Say so when it helps.

If a single agent's gathered facts are still too much for one head, the shape applies again — but you
have to arrange it, by slicing that agent's material yourself and handing out the parts.

## What a mission file contains

```json
{
  "agent": "the exact roster name",
  "mission": "what this agent must establish for this property, in plain prose",
  "context": [
    {"section": "the fact-sheet heading it appeared under",
     "fact": "the evidence, copied exactly",
     "means": "what it says, in English",
     "where": "file · page · document date"}
  ]
}
```

Three keys, and those four keys per context entry.

Every fact in the sheet that touches an agent's subject belongs in that agent's `context`, copied
exactly, with its locator. A fact may belong to several agents; give it to each of them. Nothing is
shortened, ranked, summarised or dropped.

`where` must never be empty — the next layer reads it to trace a fact back to its document.

An agent the sheet says nothing about still gets a mission. Say plainly that the fact sheet is silent
on the subject, and set out what must be established from public sources instead.

The `mission` field is your judgement: what this agent has to pin down for *this* property, including
any conflict in the record it has to settle. The `context` array is transcription, not judgement.

## Checking your own work

Losing a fact is the one failure nothing downstream can detect — a fact that reached no agent looks
exactly like a fact nobody could find.

Check it with Python, not by re-reading. Python can count the `###` blocks in the sheet, count the
context entries across the fourteen missions, and name any heading that appears in the sheet but in
none of the missions. That comparison is exact and it costs your attention nothing, however large the
sheet is.

If it finds a gap, go fix it. Then check again.

## If you have run before

Missions already in `/run/missions/`, and anything in `/run/staging/`, are from an earlier attempt on
this same property. Look before you start, and carry on rather than beginning again.

---

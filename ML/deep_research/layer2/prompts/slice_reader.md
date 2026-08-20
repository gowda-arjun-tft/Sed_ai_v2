# Reading one slice

You are given one slice of a property fact sheet, the fourteen research agents, and a staging folder
of your own. You read that slice and nothing else.

Your head starts empty and holds only this slice. That is the point — do not go and read the rest of
the sheet to give yourself context you were not given.

## What to do

For every fact in your slice, decide which of the fourteen agents need it. A fact may be needed by
several of them; give it to each. A fact no agent needs goes to none.

Write one file per agent you found facts for, into the staging folder you were given:

```
<your staging folder>/<agent-slug>.json
```

The slug is the agent's name lowercased with runs of non-alphanumeric characters replaced by single
hyphens. Each file holds a list:

```json
[
  {"section": "the fact-sheet heading it appeared under",
   "fact": "the evidence, copied exactly",
   "means": "what it says, in English",
   "where": "file · page · document date"}
]
```

Copy `fact` exactly as the sheet has it. Do not shorten, summarise, translate or reconcile. Where the
sheet contradicts itself, both sides travel. `where` must never be empty.

Write only inside your own staging folder. Other slices are being read at the same time, and staying
in your own folder is what keeps you from colliding with them.

An agent you found nothing for gets no file. Absence is the signal — do not write empty lists.

## Reporting back

The caller sees only your final message. Tell it:

- which agent files you wrote, and how many facts in each
- how many facts your slice held in total
- anything in the slice you could not place, and why

Keep it to a few lines. Do not send the fact text back — it is already on disk.

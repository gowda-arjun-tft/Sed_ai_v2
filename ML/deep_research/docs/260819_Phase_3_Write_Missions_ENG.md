# Phase 3 — turning each bucket into a mission

The agent. One model call per bucket, fourteen in total.

```
Input     runs/<run_id>/buckets/<agent-name-slug>.md    one bucket at a time
          that agent's definition                        in the system prompt
Happens   the agent reads one bucket and writes one mission file
Output    runs/<run_id>/missions/<agent-name-slug>.json  fourteen files
```

---

## Why this is a separate phase

Phase 2 decided **which** facts each agent gets. This phase decides **what to tell it to do with
them**. They are different jobs and they need different context.

Routing needs all fourteen definitions in view at once, so a fact can go to several agents.
Writing a mission needs one agent's definition and one agent's facts, and nothing else. Keeping
them apart means each call sees only what it needs.

It also means the fourteen calls are independent. If one fails, it is re-run on its own.

## What one call sees

```
the agent definition        name, establishes, do_not_cover, take_as_given
the bucket                  every claim routed to this agent, in the order it arrived
the mission schema          the required shape of the output
```

The bucket for a busy agent may be large. This is acceptable: one bucket is a fraction of the
JSON input, and the claims in it are already on one subject, which is the easiest case for a model
to reason about.

If a bucket is genuinely too large, split the call: write the `context` array from the bucket in
parts, then write the `mission` prose from the agent definition plus the list of section headings
present. The `mission` field does not need every fact in view to be written well.

## What comes out

```json
{
  "agent": "Building condition, capital expenditure & warranty",
  "mission": "…plain prose…",
  "context": [
    { "claim": {"any": "key-value data"}, "input_pointer": "/claims/0" }
  ]
}
```

Three fields. The shape is fixed by the design document.

### The `context` array is a transcription, not a judgement

Every claim in the bucket becomes one `context` entry. `claim` is the complete input object and
`input_pointer` identifies its position in the copied JSON. No field names are assumed.

**Nothing is selected, ranked, dropped or shortened here.** The list has no maximum length. If the
bucket holds ninety claims, the mission holds ninety entries. All the choosing already happened in
phase 2.

Because it is transcription, it can be checked exactly: every `claim` object must equal the object
at its JSON pointer and appear in the bucket. See phase 4.

### The `mission` field is the judgement

This is the one thing the model actually writes. It is plain prose naming, for this property:

- what this agent must establish, in its own subject
- any conflict in the record it has to settle — where the bucket holds two values for one thing
- anything unusual about this property the agent should know before it starts

The example in the design document shows the shape: the condition agent is told about the two
competing garage figures, the four construction generations, and the ninety-six inspection
reports, then told to report gross.

**All three of those come from the bucket.** The mission is written from what is in front of it,
not from general knowledge about buildings.

## An empty bucket is a normal outcome

Some agents will have nothing. A German data room contains no facts about interest rates or
supply chains, so those buckets are empty on most properties.

**An empty bucket still produces a mission.** The rule that all fourteen agents run on every
property has no exception, and an agent with no starting facts is exactly the case the rule
exists for — nobody decided in advance that the subject did not apply.

The mission for an empty bucket says so plainly:

```json
{
  "agent": "Geopolitical, trade & supply chain",
  "mission": "The JSON input is silent on this subject. Establish the position
              from public sources, and state plainly that the property's documents did not
              address it. …",
  "context": []
}
```

The design document already requires this: a mission must have a non-empty `mission` and either a
`context` entry or an explicit statement that the JSON input is silent.

## Should the fourteen calls run in parallel?

They are independent, so they could. Two options:

**One agent, fourteen calls in sequence.** Simplest. Matches the instruction to build this as one
agent. Fourteen calls is not slow.

**Fourteen subagents in parallel.** Faster, and each gets a clean context holding only its own
bucket. But subagents do not inherit the system prompt, each needs its own, and the harness
overhead is only worth paying for multi-step output-heavy delegation. Writing one file from one
bucket is a single step.

**Start with sequential.** Move to subagents only if the wall-clock time turns out to matter, and
note that if you do, each subagent must be told to return a short confirmation rather than the
mission text — a subagent returning raw data defeats the isolation it exists for.

## Checks before phase 4

1. Fourteen mission files exist, one per agent name.
2. Every `agent` value is one of the fourteen frozen names, character for character.
3. Every `context[].claim` exactly equals a claim in that agent's bucket.
4. The number of `context` entries equals the number of claims in the bucket.
5. Every mission has a non-empty `mission` field.
6. A mission with an empty `context` says in its `mission` field that the JSON input is silent on
   the subject.

Checks 3 and 4 together are what prove the transcription lost nothing and invented nothing.

## What can go wrong

| Problem | What happens | What to do |
|---|---|---|
| the model shortens a long fact | check 3 fails | the rule is in the prompt; if it recurs the bucket is too large for one call, so split as described above |
| the model drops facts from a large bucket | check 4 fails | same fix |
| the model writes a mission that ignores the bucket | nothing fails automatically | read the mission for the busiest agent and compare it against that bucket. The one manual read in the whole run |
| an empty bucket produces an empty mission | check 5 or 6 fails | the prompt must state that empty buckets still get a real mission |
| the model renames an agent | check 2 fails | validated the same way as in phase 2 |
| two agents get near-identical missions | not caught by any check | expected when a fact went to both. Their definitions differ, so the missions should differ in what they ask for. Worth reading once |

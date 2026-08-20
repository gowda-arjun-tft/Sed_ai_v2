# Layer 3 — harness redesign

No code changed. This is the report.

## Verdict

Layer 3 is **not a harness**. It is a five-phase Python state machine that calls the model as a
subroutine roughly **196 times per run**, and the model is never allowed to decide the method.

Layer 2 went from 1,053 lines of pipeline to one agent with a prompt. Layer 3 has **2,637 lines**, of
which **1,038 are pure orchestration** that a prompt should own. The research quality problem and the
code volume problem are the same problem: the method lives in Python, so it cannot adapt, and every
adaptation has to be written as another module.

---

## What it does today

```
Phase 0  create_run          Python
Phase 1  run_researchers     14 missions × 5 lenses      = 70 agent runs
Phase 2  write_questions     14 structured calls         = 14
Phase 3  run_second_round    up to 70 more agent runs    = 70
Phase 4  write_answers       14 gap + ≤14 sixth + 14 agg = 42
Phase 5  run_checks          Python
                                                   total ≈ 196 graph invocations
```

Each of those 196 is itself a multi-turn model↔tool loop, and **every `search_web` call is an extra
OpenAI Responses request** with `web_search` ([openai_search.py:102](ML/deep_research/layer3/providers/openai_search.py#L102)).
The real request count is several times 196.

The sequence is hardcoded in [cli.py:26-34](ML/deep_research/layer3/cli.py#L26-L34) as four `if`
statements. The model never decides whether a second round is warranted, whether five lenses suit
this mission, whether to go back and search after seeing the synthesis, or when it is done.

**That is the STORM method implemented in Python instead of handed to an agent.**

---

## Five real problems

### 1. A live normalization function that fails the run

This is a bug, not a design opinion. `finish_round` tells the model:

> `status`: How this round ended, **in your own words.**

Then check 13 requires every status to be one of five exact English strings
([settings.py:52](ML/deep_research/layer3/settings.py#L52), [run_checks.py:160](ML/deep_research/layer3/pipeline/run_checks.py#L160)).
Probed:

```
'answered'                 -> PASSES
'half done'                -> PASSES
'inconclusive'             -> FAILS THE WHOLE RUN
'partially answered'       -> FAILS THE WHOLE RUN
'Answered'                 -> FAILS THE WHOLE RUN   ← capital A
'answered with caveats'    -> FAILS THE WHOLE RUN
'no public record found'   -> FAILS THE WHOLE RUN
```

The tool invites free text; the checker demands a whitelist; a capital letter fails a whole
fourteen-mission run. This is exactly the pattern removed from Layer 2. It has never fired because
the only offline path is a fixture that hardcodes `"answered"`.

### 2. No memory. Seventy sessions start from zero on the same property

[llm.py:62](ML/deep_research/layer3/llm.py#L62) gives every researcher a bare `StateBackend()`. No
`store=`, no `memory=`, no `CompositeBackend`, no filesystem. So:

- the agent's `read_file`/`write_file` write to thread state that **evaporates** at session end;
- the second round runs on a **different `second_thread_id`** ([register.py:64](ML/deep_research/layer3/register.py#L64)), so a
  researcher has no memory of its own first round;
- nothing carries between the fourteen missions.

All fourteen missions concern **one property, one jurisdiction, one market**. The legal lens fetches
the land registry; the economist lens on mission 8 has no idea that page exists and searches for it
again. The only sharing is `query_cache`, a Python dict-on-disk the agent cannot see or reason about.

The 19-column `register.csv` with a `threading.RLock` is real memory — but it is **Python's memory
about the agent**, not the agent's memory. The thing doing the work is the only participant with
amnesia.

### 3. The aggregator cannot check anything

Three structured agents, all with **`tools=[]`** ([llm.py:83](ML/deep_research/layer3/llm.py#L83)).
The aggregator that writes the final answer for a mission gets five reports pasted into a user
message and cannot read a source, verify a quote, or compute a number.

`AnswerDraft` is `{markdown: str}` — a Pydantic wrapper around a string, existing only to satisfy the
plumbing. `QuestionSet` hardcodes the five lens names as fields, so **a sixth lens can never be sent
questions**.

### 4. The fixture path is fake production code, and 13/13 proves nothing

`sessions.py::_run_fixture_one` (63 lines) walks the tools by hand to fake a session.
`write_questions` writes an **empty `QuestionSet()`** for all fourteen. `_fixture_answers` writes a
canned sentence.

So the offline run that reports **13/13 passed** produced: zero real questions, fourteen canned
answers, no model call. The tests prove the plumbing; they say nothing about research. ~120 lines of
production code exist only for that.

### 5. Duplicated and unread artefacts

- **`calculation_tool.py`** (81 lines) is Layer 2's `python_tool.py` with logging bolted on. Its
  `calculations.jsonl` is never read or checked.
- **`question_files.py`** (49 lines) writes a `.json` source of truth *and* a `.md` that its own
  docstring calls "a human rendering that is **never read back**". Checks 6 and 7 then police both.
- **`ResearchState.query_count`** is a whole state-schema extension carrying a sequence number that
  `text_hash` already derives.

---

## What to delete

| File | Lines | Why |
|---|---|---|
| `pipeline/run_researchers.py` | 47 | phase sequencing → prompt |
| `pipeline/run_second_round.py` | 61 | the agent decides if a second round is needed |
| `pipeline/write_questions.py` | 101 | contradiction mapping → prompt |
| `pipeline/write_answers.py` | 261 | gap scan + sixth lens + synthesis → prompt |
| `pipeline/state.py` | 13 | no phases to mark |
| `sessions.py` | 242 | the harness runs the loop |
| `aggregator_runner.py` | 36 | one `ainvoke` |
| `question_files.py` | 49 | unread duplicate artefact |
| `register.py` | 147 | replaced by the checkpointer + the agent's own notes |
| `calculation_tool.py` | 81 | fold into one `run_python` |
| **Total** | **1,038** | |

Plus: `TERMINAL_STATUSES`, `ResearchState`, `QuestionSet`, `GapDecision`, `AnswerDraft`,
`create_structured_agent`, checks 6/7/13, the three `provider == "fixture"` branches.

## What to keep

**These are capabilities, not controls.** Every one survives.

| File | Lines | Why it stays |
|---|---|---|
| `text_extraction.py` | 136 | Encoding detection is what makes a non-English source quotable at all. Assuming UTF-8 mangles windows-1251, Shift-JIS, Big5. The best file in the layer. |
| `sources.py` | 212 | The evidence store: raw bytes, canonical text, hashes, citations. This is what makes verification possible. Trim `record_calculation`. |
| `retrieval.py` | 58 | `normalize_url` is the dedupe key. `validate_public_url` is the one guard you approved keeping — it protects your network from a URL suggested by an untrusted page, not the model's judgement. |
| `providers/` | 179 | Search and fetch. |
| `usage.py` | 78 | Recording, never limiting. Layer 2 just gained a smaller version of this. |
| `create_run.py` | 143 → ~90 | Drop register seeding and the dead directories. |
| `run_checks.py` | 179 → ~110 | Bookkeeping only, like Layer 2's eight. |

---

## The redesign

**One agent per mission. Fourteen invocations, not 196.** Exactly Layer 2's shape.

```python
create_deep_agent(
    model=MODEL_SPEC,
    system_prompt=<SKILL.md> + <mission> + <boundaries>,
    tools=[search_web, read_source, cite, run_python],
    middleware=[],
    backend=CompositeBackend(
        default=StateBackend(),                                  # harness scratch stays ephemeral
        routes={
            "/run/":      FilesystemBackend(root_dir=run_dir),   # real notes, real files
            "/memories/": StoreBackend(),                        # shared across the 14 missions
        },
    ),
    memory=["/memories/AGENTS.md"],
    store=store,                                                 # goes here, not on the backend
    subagents=[practitioner, academic, economist, historian, skeptic],
    permissions=[FilesystemPermission(operations=["write"],
                                      paths=["/run/inputs/**"], mode="deny")],
    checkpointer=saver,
)
```

Three things that change the character of the thing:

**A filesystem.** The agent can keep working notes, re-read them, list what it has already covered,
and write `research/<slug>.md` itself — no `finish_round` keyhole, no Python writing on its behalf.

**Memory scoped to the run.** `/memories/` namespaced by `run_id` means the property, the
jurisdiction, the market and the sources found once are available to all fourteen missions. **Still
no cross-property memory** — AGENTS.md forbids it and that stays true, because the namespace is the
run.

**Five lens subagents via `task`.** Several `task` calls in one message run in parallel, which is how
the five lenses actually go concurrent. Each carries its own prompt (subagents never inherit). Note
two facts verified while fixing Layer 2: deepagents silently adds a **`general-purpose`** sixth
option, and **no subagent gets `task`** — so the lens agents cannot fan out further, and the prompt
must say so.

The attribution firewall becomes a prompt rule rather than a schema with nowhere to put a name: the
mission agent holds all five reports, and when it sends a second-round question it sends *the thing
to establish*, never another lens's wording or identity.

Estimated result: **2,637 → ~1,250 lines**, and the method becomes editable in Markdown.

---

## The SKILL.md rewrite

The current [SKILL.md](ML/deep_research/layer3/SKILL.md) is a good method pointed at the wrong target.
It is a Claude Code skill: `$ARGUMENTS`, the `Agent` tool, `Write`, `report-template.html`,
`storm-reports/*.html`, and "topic". None of that exists here.

**What it already gets right, and Layer 3 does not:** its lens prompts are ~120 words each and
specify what to research, which gap to surface, the exact return shape, and *"THE ONE THING only a
practitioner would say."* Layer 3's lens prompts are **two lines**
([prompts/lenses/academic.md](ML/deep_research/layer3/prompts/lenses/academic.md)). The skill's
prompts are strictly better and should replace them.

**Its Phase 4 is the biggest single quality win available.** Adversarial citation verification
against the primary source — Layer 3 has *no equivalent*. And Layer 3 can do it far better than the
original skill could, because it already stores every source's raw bytes and canonical text: a
`run_python` snippet can check **every quote against `sources/text/*.txt` exactly**, offline, for
free. The skill had to spawn agents to re-fetch pages and guess.

### The mapping

| STORM phase | Becomes |
|---|---|
| 0 · Scope the topic | **Delete.** Layer 2 already scoped it. Read the mission, `establishes`, `do_not_cover`, `take_as_given`. Never ask a user. |
| 1 · Five lenses, parallel agents | **Keep, verbatim quality.** Five `task` calls in one message. Rewrite each prompt for property due diligence, and require `cite` for every claim. |
| 2 · Map the contradictions | **Keep, inline.** This is what `aggregator_pass1` did with a hardcoded schema. Now it is judgement, and it produces the second-round questions. |
| 3 · Synthesize HTML | **`research/<slug>.md`.** Drop the template, the CSS, the `open <path>` step. |
| 4 · Adversarial review + verify | **Keep and strengthen.** Quote-checking becomes exact and offline against the stored text. |
| — | **Add: the second round.** Question-only, no attribution. CDI's own requirement; STORM has no equivalent. |
| — | **Add: the sixth lens.** The skill's "missing 6th lens" is currently a separate `GapDecision` schema. It becomes one paragraph. |

### Things to carry over unchanged

- *"Real research only. No invented studies, numbers, or URLs."*
- *"The panel is author-built. Agreement across lenses is a strong hypothesis, not independent
  proof."* — already in `aggregator_pass2.md`, and it is the most important sentence in the layer.
- *"Reliability = evidence quality, not confidence."* The source hierarchy becomes **guidance** beside
  `cite`'s free-text `tier`, not a whitelist.
- The **claim safety guide** (assert / caveat / avoid). This maps onto due diligence better than onto
  the skill's original purpose — it is exactly what a DD reader needs from a research file.
- *"Verification is mandatory. A report delivered without Phase 4 is not a Storm Research report."*

### Things to cut

`report-template.html`, the topic-slug filename derivation, `storm-reports/`, the platform-specific
opener, `$ARGUMENTS`, the Montserrat/Roboto design note, and the agent-count budget (*"do not fan out
wider than five lenses"*) — that last one is a cost cap on the model, and it goes.

---

## Two things I want your call on before writing code

**1. Fourteen agents, or one?** The plan above runs one agent per mission — fourteen top-level
invocations, each fanning out five lenses. The alternative is **one** agent for the whole run that
decides how to sequence all fourteen missions itself. That is purer, and it is what Layer 2 does.
I recommend fourteen: fourteen missions × five lenses × two rounds will not fit one context, and the
20,000-token rule from Layer 2 applies here with far more force. But it is one agent per *subject*
rather than one agent per *run*, and that is a real departure from Layer 2's shape.

**2. What replaces `register.csv`?** The checkpointer gives durable resume for free, and the agent's
own notes on `/run/` give it visibility. But `register.csv` is also the human-readable audit trail —
84 rows showing what each researcher did. If you want that view kept, it should be **derived** after
the run from the checkpoints, citations and usage logs (reporting), not maintained during it
(control). Say which you want and I will build it that way.

# Layer 2 — how the code works

Layer 2 turns **one property fact sheet** into **fourteen mission files**, one per research subject.
Layer 3 then researches each mission on the open web.

```
fact_sheet.md  ──►  runs/L2_20260820_a1b2/missions/*.json  ──►  Layer 3
```

Three steps. Only the middle one calls a model.

```
  1. create_run.py        2. agent.py              3. report.py
  ─────────────────       ────────────────         ────────────────
  build the folder        the agent reads the      eight checks,
  copy + hash inputs      sheet and writes the     check_report.md,
  (no model)              fourteen missions        finish run.json
                          (the model)              (no model)
```

`cli.py` runs those three in order. That is the entire control flow — there is nothing between
them. How the sheet is read, how facts are allocated, whether helpers are used: all of that is the
agent's decision, written in English in `prompts/mission_agent.md`, not in Python.

---

## The files

| File | Lines | What it is for |
|---|---|---|
| `cli.py` | 194 | Entry point. Parses arguments, runs the three steps, prints the result. |
| `create_run.py` | 159 | **Step 1.** Builds the run folder, copies and hashes the two inputs. |
| `agent.py` | 239 | **Step 2.** Builds the deepagents agent. Contains no procedure. |
| `report.py` | 288 | **Step 3.** Eight bookkeeping checks, then the two record files. |
| `settings.py` | 68 | Every fixed value: model, roster, paths. |
| `planner.py` | 79 | Loads and verifies the fourteen-subject roster. |
| `python_tool.py` | 115 | The `run_python` tool — the agent's calculator and auditor. |
| `fs.py` | 133 | File, hash and JSON helpers. Shared: Layer 3 imports these too. |
| `prompts/*.md` | 352 | The method. Four prompts, in English, read at run time. |

`fs.py`, `planner.py` and `settings.py` are **shared with Layer 3**, which imports from them in about
twenty places. They are not private to Layer 2, so renaming them is not a local change.

---

## The flow, function by function

### Start

`__main__.py::_run` → `cli.py::main`

`main` reads `.env` for the API key (`load_dotenv_key`) and then picks one of three modes:

| Mode | What happens |
|---|---|
| a fact sheet path | step 1, step 2, step 3 |
| `--resume <folder>` | step 2, step 3 — continues the existing conversation |
| `--check-only <folder>` | step 3 only — no model call |

### Step 1 — `create_run.py::create_run`

Called once, with the fact sheet path, `PLANNER_PATH` and `RUNS_DIR`. It builds:

```
runs/L2_20260820_a1b2/
    run.json          status: "started"
    inputs/
        fact_sheet.md      byte-identical copy, hashed
        planner_prompt.md  byte-identical copy, hashed
    missions/         empty — the agent fills it
    staging/          empty — the agent's scratch space, used only if needed
```

| Function | Does |
|---|---|
| `create_run` | The whole step. Validates, then copies, then records. |
| `_make_run_dir` | Draws `L2_<date>_<4 hex>` and `mkdir`s it — a `FileExistsError` means redraw. |
| `_initial_record` | The starting `run.json`: input hashes, model, effort, harness version. |

Two things are validated, and both are about a **human-supplied file** rather than model output: the
fact sheet is non-empty and has at least one `##` heading (a wrong-file mistake — someone passed
JSON or the wrong path), and the planner prompt still holds the frozen roster. Both fail before a
single model call is paid for.

The inputs are **copied, not referenced**, so a run stays readable after the source document moves or
changes — and the hashes prove which bytes it was checked against.

### Step 2 — `agent.py::create_mission_agent`, run by `cli.py::write_missions`

```
cli.write_missions
  └─ cli.checkpoint_saver          open runs/.../checkpoints.sqlite3
      └─ agent.create_mission_agent
          ├─ agent.configure_provider   register the model profile
          ├─ agent.system_prompt        mission_agent.md + planner_prompt.md
          └─ agent.subagents            slice-reader, mission-writer
      └─ agent.ainvoke(agent.mission_request())     ← one user message
```

| Function | Does |
|---|---|
| `configure_provider` | Registers the model profile (high effort, Responses API, `store=False`). Owned here because the registry is global and both layers share `MODEL_SPEC`. |
| `system_prompt` | `mission_agent.md` with the real run path substituted, then `planner_prompt.md` verbatim. Since deepagents 0.7 this is the *entire* prompt — the harness adds none. |
| `subagents` | Two CDI helpers plus an explicit general-purpose helper. Each carries its own prompt, because subagents never inherit the parent's. |
| `create_mission_agent` | Assembles the harness. Makes no model call — tests inspect it offline. |
| `mission_request` | The one user turn: *"Read the fact sheet and write the fourteen mission files. Tell me what you wrote and how you checked it."* |
| `cli.final_message` | Keeps the agent's closing account → `agent_report.md`. |
| `cli.usage_summary` | Counts the top-level turns, tokens and tool calls → `run.json`. |

**What the agent is given:** the file tools (`read_file`, `write_file`, `ls`, `glob`, `grep`,
`edit_file`, `delete`), `task` to spawn a helper, and `run_python`. Capabilities, not instructions.

**What it is not given:** any ceiling. No model-call limit, no tool-call limit, no retry policy, no
tool that validates or rejects what it produces.

### Three harness facts

Verified by building the graph and reading it, not from documentation:

- **A third helper is explicit.** Layer 2 declares `general-purpose` so Layer 3's process-wide
  disabling of the implicit helper cannot change Layer 2 based on import order. The
  `task` tool offers three, not two. It has the same tools and no idea what a mission file is, which
  is why `mission_agent.md` names it and says to prefer the two specialists.
- **No helper can delegate.** `SubAgentMiddleware` attaches to the main agent only, so no subagent
  has `task`. Delegation is exactly one level deep. Both helper prompts say so plainly.
- **`middleware=[]` does not mean a bare graph.** The harness always installs its own filesystem,
  subagent, summarisation and tool-call-repair middleware — those are what make the file tools and
  `task` exist at all. What the empty list omits is any ceiling of ours.

### Layer 2 is not a sandbox

`run_python` executes model-authored code in a subprocess on the host. That subprocess inherits the
environment (`OPENAI_API_KEY` included), the host filesystem and host network access, with no
timeout, output cap or import restriction. The `FilesystemPermission` deny on `inputs/**` constrains
the built-in file tools only — **it cannot constrain a subprocess.**

The absence of limits is deliberate and was asked for. The consequence is not a limit but a fact
about authority: Layer 2 does no web research, but nothing stops a snippet from reaching the network.
Run it only on input you would run any untrusted script against.

The backend is a `CompositeBackend`: `/run/` maps to the real run folder, and everything else stays
in memory. That matters — it keeps the harness's own artefacts (`/large_tool_results/`,
`/conversation_history/`) out of the run folder, where they would otherwise land beside the
deliverable.

### Step 3 — `report.py::run_checks`

```
run_checks
  ├─ _load_missions      read missions/<slug>.json for each of the fourteen names
  ├─ _build_checks       the eight checks + the fact counts
  │    └─ fact_blocks    count ### blocks in the sheet
  ├─ _write_report       check_report.md
  └─ write_json          run.json: checks, facts, status, finished_at
```

| # | Check |
|---|---|
| 1 | Both inputs match their recorded hashes |
| 2 | The planner copy still holds the frozen roster |
| 3 | Fourteen mission files exist, one per roster name |
| 4 | Every mission parses, has exactly `agent`/`mission`/`context`, and `context` is a list |
| 5 | Every mission names its own agent |
| 6 | Every context entry has the four keys and a non-empty `where` |
| 7 | Fact counts — **printed, never judged. Always passes.** |
| 8 | Every mission carries prose |

Every check asks whether the deliverable is *present and well-formed*. None asks whether the agent's
judgement was good, and none can change what it produced. A failure means the run is incomplete.

Check 7 is the deliberate gap. A fact belonging to three subjects appears three times, so sheet
totals and mission totals differ for good reasons and no threshold would be honest. It prints
`sheet=41 context_entries=57 distinct_facts=39` and says nothing about whether that is right.

The lossless check the code used to do, the agent now does *during* the run, with Python, against
both sides on disk — and unlike a code gate it can go and fix what it finds, then check again.

### A crash is not a failed check

`_context_of` exists because the agent authors these files, so `context` can arrive as anything JSON
allows — `null` for "no facts" is the likeliest. Four such shapes used to raise out of `run_checks`,
and because the exception happened *before* `check_report.md` was written and `run.json` stamped, the
run was left with **no report at all** and `status` stuck at `"started"`. That reads as a run that
never finished rather than one that produced malformed output.

The rule now: a wrong shape is a **failed check**, never a crash. A corrupt `run.json` and a deleted
fact sheet are handled the same way. Only a *missing* `run.json` still raises, because that is the
wrong folder being passed, not agent output. `tests/test_layer2_robustness.py` pins all of it.

An empty `context` list still passes — coverage is never gated. That distinction is the whole point.

---

## What the agent produces

One file per subject, at `missions/<slug(agent name)>.json`:

```json
{
  "agent": "Occupier, lease & income",
  "mission": "What this agent must establish for this property, in plain prose.",
  "context": [
    {"section": "Lease and income evidence",
     "fact":    "\"EUR 100,000\"",
     "means":   "The annual rent is EUR 100,000.",
     "where":   "lease.pdf · p9"}
  ]
}
```

Three top-level keys, four keys per context entry. `mission` is judgement; `context` is
transcription, copied exactly and never shortened, ranked or merged. `where` must never be empty —
it is what Layer 3 traces a fact back through.

A subject the sheet says nothing about still gets a mission, saying so plainly. That is a normal,
passing outcome.

---

## The prompts — where the method actually lives

| Prompt | Read by | Says |
|---|---|---|
| `mission_agent.md` | the main agent | Measure first, keep any one context under ~20,000 tokens, pick your shape, check yourself with Python. |
| `planner_prompt.md` | the main agent | The fourteen subjects, with `establishes` / `do_not_cover` / `take_as_given` / `web_sources`, plus the roster JSON `planner.py` parses. |
| `slice_reader.md` | a `slice-reader` | Read one slice, stage what you found per subject into **your own folder**. |
| `mission_writer.md` | a `mission-writer` | Write one subject's mission from facts handed to you or staged on disk. |

### The 20,000-token rule

The one thing the prompt insists on: **no single context holds much more than 20,000 tokens of
source text.**

Not a limit. Nothing truncates and nothing rejects. Attention decays long before a context window
fills, and two harness behaviours then compound it silently. Both numbers were read off the installed
deepagents 0.7.7 and this model's profile:

| What | When | What it does |
|---|---|---|
| Tool-result offload | a single result over **20,000 tokens** | moved to `/large_tool_results/`, replaced by a pointer |
| Summarisation | conversation reaches **85% of max input — about 892,500 tokens here** | keeps `("fraction", 0.10)`: **the most recent tenth** |

That second row is worth reading twice. It is not "the older half gets compressed" — an earlier
version of this document and of the prompt said that, and it understated the loss badly. Roughly the
older **nine tenths** are replaced by a summary, and a fact read early stops existing with no error
raised. *Forgetting looks exactly like success*, which is why the rule is written down rather than
left to be discovered.

The 20,000 figure is not arbitrary either: it happens to be exactly the harness's own offload
threshold, so reading more than that in one call puts a file path in the agent's head, not the text.

### How the agent uses it

**Measure before you read.** Python answers "how long, how many `###` blocks, where does each heading
start" for a few hundred tokens, whether the sheet is 16,000 tokens or three million. Then the agent
knows which shape of work it is in before spending any attention:

- **Sheet fits in one head** → read it, write the fourteen missions. One sitting, no helpers, no
  staging. This is the common case and it needs no machinery.
- **Sheet does not fit** → cut at section headings (~20k per slice) → one `slice-reader` per slice,
  each writing only inside its own staging folder → one `mission-writer` per subject, gathering that
  subject's facts from across the staging folders.

Several `task` calls in one message run in parallel. Each `slice-reader` owning its own folder is
what makes that safe: no locks, no shared file, no ledger.

The division of labour, stated in the prompt: **Python counts, finds, diffs and checks. The agent
decides what belongs where.** Neither does the other's job.

---

## Resume

`cli.py::checkpoint_saver` opens `checkpoints.sqlite3` in the run folder. LangGraph writes the whole
conversation there after every step, and `write_missions` always uses the same `thread_id`, so
rerunning a folder continues that conversation with everything the agent had already read and
decided:

```powershell
.\run.ps1 -Resume '.\runs\L2_20260820_a1b2'
```

This replaced a `progress.csv` the code maintained and the agent could not see. The checkpointer is
durable in the framework, needs no bookkeeping, and covers reasoning as well as files.

Note what resume does *not* do: it continues the conversation, it does not decide the work is
finished. Resuming a run that already reports `complete` asks the agent again — usually one cheap
turn, since the prompt tells it to look at what exists and carry on, but the CLI prints a note first
so paying for a finished run is never a surprise.

## What a finished run leaves behind

```
runs/L2_20260820_a1b2/
    run.json            record: input hashes, model, checks, facts, usage
    check_report.md     what the code could confirm
    agent_report.md     what the agent says it did and how it checked itself
    missions/*.json     the deliverable, fourteen files
    inputs/             the two byte-identical copies
    staging/            whatever the agent used, if anything
    checkpoints.sqlite3 the conversation, for resume
```

`agent_report.md` and `run.json`'s `usage` block are both recent additions, and both close gaps
rather than add control:

- **The account.** `mission_request` asks the agent to say how it checked itself, and `write_missions`
  used to discard the answer. It is the only record of the self-verification — the report counts
  files and keys and cannot see reasoning.
- **The cost.** `usage.top_level_model_calls`, `input_tokens`, `output_tokens` and
  `top_level_tool_calls`. Read the names literally: work inside a `slice-reader` or `mission-writer`
  runs on its own message list and is **not** counted, so a delegating run really costs more. The
  undercount is in the field name rather than hidden behind it. Recording is not limiting — nothing
  reads these numbers to stop or shape anything.

---

## Running it

```powershell
.\run.ps1 -FactSheet 'C:\path\to\fact_sheet.md'     # new run
.\run.ps1 -Resume '.\runs\L2_20260820_a1b2'         # continue
& $Python -m ML.deep_research.layer2 --check-only '.\runs\L2_20260820_a1b2'   # report only
```

Exit code is 0 when every check passed, 1 otherwise. Offline tests:

```powershell
& 'C:\src\anaconda3\envs\compute\python.exe' -m unittest discover -s tests -v
```

| Test file | Covers |
|---|---|
| `test_layer2_agent.py` | Tool surface, no ceiling middleware, both helpers carrying their own prompt, no helper able to delegate, and the prompt's summarisation numbers checked **against the installed package** rather than restated |
| `test_layer2_inputs.py` | The roster, the input checks, the fact count, `agent_count` derived from the roster |
| `test_layer2_robustness.py` | Every malformed-context shape fails cleanly; an empty one still passes; `final_message` across provider content shapes; the usage summary |
| `test_checks.py` | The report, including that emptying a mission's context still passes |
| `test_layer3_handoff.py` | Layer 3 records what Layer 2 actually reported, and no module restates a check count |

No test calls a model or the public web.

## What only a real run can settle

Everything above was verified offline. Three things cannot be:

1. **Does it measure before reading?** The prompt says to. Whether the agent does it, or reads
   straight in, is behaviour.
2. **Does it over-engineer a small sheet?** On the ~16,000-token sheet the one-sitting path is
   correct. If it stages anyway, the prompt is nudging too hard toward the large-sheet shape.
3. **What does a run actually cost?** `usage` now records the top-level half of the answer. The
   subagent half needs a run with delegation to observe at all.

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
| `subagents` | The two helpers the agent may spawn. Each carries its own prompt, because subagents never inherit the parent's. |
| `create_mission_agent` | Assembles the harness. Makes no model call — tests inspect it offline. |
| `mission_request` | The one user turn: *"Read the fact sheet and write the fourteen mission files. Tell me what you wrote and how you checked it."* |

**What the agent is given:** the file tools (`read_file`, `write_file`, `ls`, `glob`, `grep`,
`edit_file`, `delete`), `task` to spawn a helper, and `run_python`. Capabilities, not instructions.

**What it is not given:** any middleware. No model-call ceiling, no tool-call ceiling, no retry
policy, no tool that validates or rejects what it produces. The only Python restriction in the layer
is a write-deny on `inputs/`, and that protects a hash Layer 3 verifies.

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
| 4 | Every mission parses and has exactly `agent`, `mission`, `context` |
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
fills, and past about 85% the harness silently compresses the older half of the conversation into a
summary — so a fact read early stops existing with no error raised. *Forgetting looks exactly like
success*, which is why the rule is written down rather than left to be discovered.

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

`test_layer2_agent.py` builds the graph and inspects it — tool surface, no middleware, both helpers
carrying their own prompt, the 20k rule present in the prompt. `test_layer2_inputs.py` covers the
roster, the input checks and the fact count. `test_checks.py` covers the report, including that
emptying a mission's context still passes. No test calls a model.

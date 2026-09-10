# Claude development handover

Prepared 2026-09-10 for `C:\Users\Arjun Gowda\Desktop\Sed_ai_v2`.
This is a snapshot for continuing development. Inspect the current checkout and running services
before relying on recorded status; no repair or research task is authorized by this file alone.

## Start here

The user will use Claude for development because Codex usage is limited. Read [AGENTS.md](AGENTS.md)
for the controlling repository contracts and [docker/README.md](docker/README.md) for execution.
The current branch is **plain_research**, with **Layer 2 schema 6**. `plain_research_v2` has schema 7
and remains a separate branch. Do not merge V2 behavior while working on the original branch.

Two complete Codex skills have been copied into the Windows personal Claude folder:

- `~/.claude/skills/deep-agents-builder/SKILL.md`: Python Deep Agents harness design and changes.
- `~/.claude/skills/prompt-framework/SKILL.md`: prompt design, refinement and evaluation.

Read the references required by the selected skill. Use the exact name `deep-agents-builder`,
with the extra hyphen; the older `deepagents-builder` remains installed but is not the selected
guide. The project's permissive JSON and Model-Output Freedom rules govern over stricter generic
examples. Skill copies are snapshots, not an automatic sync with Codex.

## Environment and working files

Claude runs from Windows; execute application Python in the existing development container.
Claude was not installed in the development container during inspection. Windows personal skills
are not automatically installed in a container or on another computer.

| Location | Meaning |
| --- | --- |
| Windows project / container `/app` | The same original files, Git, inputs, notebook and runs |
| `sedai-dev-1` | Shared development environment; Linux Python `/usr/local/bin/python` |
| `sedai-notebook-1` | Separate browser service with image-backed code and volume-backed runs |
| `CDI_Layer2_Layer3.ipynb` | User interface; three research cells with editable controls |

The development image tag `sedai-v2-dev:local` does not select the application branch. Its shared
mount follows the host checkout. The browser service does not switch application code with that
checkout, although its notebook file is shared. Avoid simultaneous notebook edits.

Use VS Code **Dev Containers: Reopen in Container**, then select **SedAI Docker — Python 3.12**.
After switching branches, finish active work before restarting the notebook kernel, otherwise
previously imported modules can remain in memory. Reload changed notebook source from disk before
saving stale editor content over it. Paths use forward slashes; on Linux a backslash is a filename
character. The previous failure was `/app/inputs\\new_fact_sheet.md`, not a missing dependency.

## Layer 2 on this branch

Application settings: Deep Agents **0.7.7**, `gpt-5.6-luna`, selected reasoning (currently high),
three provider transport retries, nominal 60K source windows with 10K overlap and concurrency five.
Assembled inputs target 300K estimated tokens with an exceptional ceiling of 350K; there is no
application output-token cap. Keep these settings unless a later task explicitly changes them.

| Stage | Input and responsibility |
| --- | --- |
| Read facts | Original windows only; preserve profile and detailed evidence, without plugin or requirements |
| Choose domains | Understanding evidence, plugin, requirements and current definitions; tool-free for new runs |
| Sort facts | Original source plus domains; extract and route facts again in schema 6 |
| Review domains | Fact/ownership pages, domains, plugin and requirements; identify changes |
| Finalize domains | Settle definitions and proposed changes |
| Assign facts | Assign preserved facts to final domains; Python publishes available results |

Source reading and sorting are tool-free. Review uses native read-only `ls`, `glob`, `grep` and
`read_file` over registered evidence, with SQLite persistence. Schema 6 has historical designer
capability behavior frozen per run. Do not replace it with schema 7's extract-once/correction flow.

- `ML/deep_research/layer2/backend/`: runner, storage, publication, recovery, logging and CLI adapter.
- `ML/deep_research/layer2/ML/`: harness, input accounting and the six numbered prompts.
- `ML/deep_research/layer2/plugins/real_estate.md`: selected industry definitions; Python has no fixed roster.
- `inputs/new_fact_sheet.md` and `inputs/requirement.md`: user evidence and requirements; preserve their content.
- Public Python entrypoints: `ML.deep_research.layer2.create_run` and `run_all`.

Outputs are grouped under `runs/<input-group>/L2_*`: readable `README.md`, `domain_plan.md`,
`domains/*.md`, and `unresolved.md` when needed. Internal snapshots, fact ledger and assignments
are under `_internal/`; raw responses, usage, revisions and SQLite databases are under its `trace/`.
Operational events are in `run.log`. Preserve these artifacts and their frozen prompts.

Layer 3 runs eight researchers plus synthesis. Layer 4 produces internal/candidate reports,
external research and synthesis. Dynamic Layer 2 schemas 6/7 are **not yet integrated** with them;
the notebook's downstream cells use historical inputs. Integration is separate work.

## Current changes to preserve

At handover, Docker setup is uncommitted: `.devcontainer/`, `.dockerignore`, `compose.yaml`,
`docker/`, workspace settings, notebook path fixes, structure tests, guidance and Railway Track.
The Claude instructions and this handover are additional local files. Run `git status --short`
and inspect the diff; never reset or overwrite these changes to make the tree clean.

The Docker changes import infrastructure only from V2 commit `b66a57c`. Research code, prompts,
schema 6 and pinned application dependencies were preserved. No container rebuild/restart was needed.
The notebook's saved traceback is historical output; it does not describe the corrected source.

Previously recorded checks, not a newly executed evaluation:

- Docker setup: **151 offline tests passed**, compilation, dependency and disposable SQLite checks passed.
- Subsequent notebook correction: **8 focused structure tests passed**; all three cells compiled,
  and both Layer 2 input paths existed in Docker.
- Container terminal and a separate diagnostic kernel reported Linux, `/usr/local/bin/python` and schema 6.
- Existing research containers were not restarted. No model calls were made for those checks.

See [Docker verification history](railway-track/tracks/2026-09-10-plain-research-docker.md).

## Output-quality findings from the prior comparison

The user's priority is research quality. Cost and speed do not compensate for losing material
qualifications. The original `plain_research` output retained more of the checked qualifications
than the compared V2 outputs; this was a targeted source-backed comparison, not exhaustive proof.

| Output | Finding |
| --- | --- |
| `L2_20260909_123721_13fb` (original, schema 6) | Retained the checked area/parking rent protection, landlord fire-plan exception, reserved-payment status and building-section figures |
| `L2_20260909_171314_855f` (earlier V2) | Missed area/parking protection and the specific landlord exception; retained reserved-payment wording |
| `L2_20260910_062611_bd5e` (previous Docker V2) | Retained those three contractual qualifications; missed some building-section figures |
| `L2_20260910_080100_ae8c` (latest compared V2) | Missed area/parking protection and payment under reservation pending a signed addendum; retained the landlord exception |

The original and earlier V2 runs are under `runs/inputs-new-fact-sheet-9563041d/`. The latest
compared V2 is under `runs/inputs-new-fact-sheet-93b222cb/`. The `062611_bd5e` run was only found
in the browser container's `/app/runs/inputs-new-fact-sheet-93b222cb/` during comparison.

Relevant frozen source locations: line 948 (area/parking differences do not create claims or
change rent), line 977 (landlord fire-plan exception), line 1016 (payment under reservation),
and lines 286–288 (separate indicative building-section costs). Recheck locations against the
frozen source before a future audit; do not hardcode this property's facts into production prompts.
The latest missing clauses were absent from understanding responses before publication.
Some V2 responses also treated compatible pending contractual states as contradictions.

These are findings for future decisions, not instructions to modify prompts, rerun research or
repair historical outputs. Complete assignment tracking does not prove complete source extraction.

## Commands and working rules

From the Windows repository terminal:

```powershell
docker compose exec -T dev python -m docker.diagnose
docker compose exec -T dev python -m unittest discover -s tests -v
docker compose exec -T dev python -m compileall -q ML tests docker
docker compose exec -T dev python -m pip check
git diff --check
```

If Docker is not on PATH, its verified executable location is
`$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe`; invoke it with PowerShell `&`.
From the VS Code container terminal, use the same Python commands without the Compose prefix.
Use `%run -m docker.diagnose` in a temporary notebook cell for environment verification.

Follow `AGENTS.md`: use existing helpers, keep code readable, keep executable files below 350 lines,
use meaningful offline checks, and record authorized meaningful work through Railway Track.
Do not add semantic validators, output repair calls, content retries or automatic summarization.
Preserve raw outputs, partial publication and the separation of execution status from coverage.
Inspect SQLite connection/recovery code before changing it; bounded read retries and the idle
connection address observed operational failures and are not dead code.

Use one writer per run. Do not start, resume, stop or rewrite research runs without an explicit
request. Do not run project-wide Compose shutdown commands while browser research is active.
Never print credentials. Follow the existing login and permission controls for Claude.
The old automated Codex-to-Claude bootstrap was blocked and never installed; this handover replaces
that workflow with direct Claude development. Do not delegate work back to Codex.
The earlier $8 paid optimization experiment remains inactive. A future live comparison requires
separate authorization and identical inputs/settings; a passing offline test is not extraction accuracy.

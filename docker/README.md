# Docker Python for the shared research workspace

Use the original project, Git, notebook, inputs and runs in VS Code, with Docker Python.
On `plain_research_v3`, Layer 2 now uses schema 9; Docker still runs the currently checked-out code.

## Open the original workspace

1. Start Docker Desktop's Linux engine and open this repository in VS Code.
2. Use the company-approved Microsoft Dev Containers extension:
   **Dev Containers: Reopen in Container**.
3. Confirm **Dev Container: SedAI Docker** and select **SedAI Docker — Python 3.12**
   (interpreter `/usr/local/bin/python`) in the notebook.
4. After a branch switch, wait for active research to finish and restart the notebook kernel.
   A kernel holding modules from another branch does not automatically reload the checked-out code.

Development mounts the entire original project read-write at `/app`. There is no second code
copy or nested volume hiding runs, inputs or outputs. Edits and new development runs appear on
Windows immediately. Git is available; only `/app` is trusted for ownership checks.
Do not change branches during active development research. Closing VS Code leaves development
running; opening it never executes notebook cells.

## Check before research

In the container terminal:

```bash
python -m docker.diagnose
python -c "from ML.deep_research.layer2.backend.settings import LAYER2_SCHEMA_VERSION; print(LAYER2_SCHEMA_VERSION)"
python -m pip check
```

Expected on `plain_research_v3`: Linux, `/usr/local/bin/python`, successful imports and Layer 2 schema **8**.
In a temporary notebook cell, run `%run -m docker.diagnose`; do not run research cells as a test.
Saved Windows outputs are historical, not evidence of the active interpreter. Select the
container kernel explicitly even if the notebook metadata still names `compute`.

Then edit Layer 2 controls and run its cell when ready. All three notebook cells remain, but
dynamic Layer 2 schema-9 outputs feed the new Layer 3 source preparation/research workflow;
Layer 4 remains disabled for these runs. Existing schema and frozen-path
restrictions apply: browsing old runs does not authorize conversion or resume.

## Builds and separate browser research

Infrastructure is reused from V2 commit `b66a57c`; application requirements are identical.
Reuse the existing compatible development container without recreation. If dependencies or the
image require rebuilding, ensure development has no active job, then use only:

```powershell
docker compose --profile dev build dev
docker compose --profile dev up -d --no-deps dev
```

Preserve existing project/service identities. The tag `sedai-v2-dev:local` names infrastructure,
not the mounted code's branch. Source changes require no rebuild. The image installs pinned
application dependencies, caches `o200k_base`, provides Jupyter and runs as non-root.

The browser `notebook` service is separate: its code comes from its image and its research stays
in existing named volumes. It does not switch application code with the checkout. Its notebook
file is shared, so avoid simultaneous notebook edits. Do not rebuild/recreate/stop browser
research as part of this setup. Do not use project-wide `docker compose down` or delete volumes.
Old development volumes remain backups. The optional `cli` service uses separate volume-backed
state; use the VS Code container terminal for the shared-project workflow.

## Storage and secrets

The shared mount includes Git and ignored files such as `.env`. Compose supplies the API key
through the existing runtime environment. Never print it or include it in image layers.
Docker ignore rules exclude secrets, inputs, runs, outputs and Git from builds.
No Conda installation or Docker socket is mounted. Browser publishing stays loopback-only
with authentication enabled. No Windows security setting is changed.

Use one environment per active run. SQLite on Windows-mounted storage may be slower than
Docker-managed volumes; disposable tests do not guarantee every concurrent workload.
Historical runs are not migrated, resumed or rewritten by setup.

## Offline verification

### Research checkpoint volume

Persistent Layer 3 research requires the development service's named volume
`sedai-research-checkpoints`, mounted at `/var/lib/sedai/research-checkpoints`, with
`SEDAI_RESEARCH_CHECKPOINT_DIR` set to that path. It does **not** cover `/app`, source,
runs or outputs. New image directories give the existing non-root appuser ownership.
The original browser container/service mounts are unchanged.

After finishing active development work, rebuild/recreate **only development** to add this mount:

```bash
docker compose --profile dev build dev
docker compose --profile dev up -d --no-deps dev
```

Never perform this while its notebook/terminal is running research. Reopen the project in its Dev
Container, reload the saved notebook (preserve unsaved edits first), and restart only an idle kernel.
Do not execute cells automatically. Run research commands in this container, not Windows Conda.
The optional runtime-only `cli` service is not configured for the new research checkpoints; use
`docker compose exec -T dev /usr/local/bin/python -m ML.deep_research.layer3 ...` instead.

Preflight requires a writable dedicated Linux mount before any paid phase; there is no Windows or
`/app` SQLite fallback. Each domain receives its own database and stable checkpoint thread. Volume
contents survive container recreation, but deliberately deleting the volume prevents unfinished
research from resuming even though project reports/evidence still exist. Restore the volume backup
or explicitly create a new linked run; never silently restart missing threads. Deleting local data
does not delete uploaded OpenAI files. Do not delete volumes as part of ordinary setup or cleanup.

Docker was absent from PATH but was found under the user's Docker Desktop installation. During
implementation the idle development service alone was rebuilt/recreated, and the dedicated mount,
Linux interpreter, installed Deep Agents 0.7.7 and writable SQLite preflight were verified.
The browser container's ID and start time remained unchanged; no research was executed.
VS Code may need to reconnect after recreation. Reload the saved notebook and select a fresh
Docker kernel; do not overwrite newer disk content with an old unsaved editor buffer.
The host `run.ps1` research actions delegate to the development container and translate project paths;
legacy preparation/upload-only actions retain their existing Windows interpreter behavior.

Research capability version 2 runs one domain at a time with execution-owned HTTP clients and
a durable 80-logical-call allowance per domain. The counter stays with project-side retained work;
the same checkpoint thread and counter are required for resume. Do not delete either to reset a run.
New linked runs can import existing notes from a disposable copy of the parent database/WAL; this
does not resume the parent's thread or change its SQLite files. Missing notes are reported explicitly.
The editable `inputs/user_research_instruction.md` is frozen on creation. Reload the saved notebook
after preserving unsaved edits, and restart only an idle kernel to load the revised controls/code.
No container rebuild or restart is required for these source changes.

```bash
python -m unittest discover -s tests -v
python -m compileall -q ML tests docker
python -m pip check
git diff --check
```

Validate Compose from the host with `docker compose config --quiet`, not printed expanded secrets.
Tests cover the shared mount, interpreter and all three compilable notebook cells with portable paths.
No model calls are required. Historical schema-6 scale results do not measure the new Markdown workflow.
Actual results and limitations are in the
[Docker track](../railway-track/tracks/2026-09-10-plain-research-docker.md).

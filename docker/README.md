# Docker Python for plain_research

Use the original project, Git, notebook, inputs and runs in VS Code, with Docker Python.
Layer 2 stays schema 6; no V2 research code or prompts are imported.

## Open the original workspace

1. Start Docker Desktop's Linux engine and open this repository in VS Code.
2. Use the company-approved Microsoft Dev Containers extension:
   **Dev Containers: Reopen in Container**.
3. Confirm **Dev Container: SedAI Docker** and select **SedAI Docker — Python 3.12**
   (interpreter `/usr/local/bin/python`) in the notebook.
4. After a branch switch, wait for active research to finish and restart the notebook kernel.
   A kernel holding imported V2 modules does not automatically reload schema-6 code.

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

Expected: Linux, `/usr/local/bin/python`, successful imports and schema **6**.
In a temporary notebook cell, run `%run -m docker.diagnose`; do not run research cells as a test.
Saved Windows outputs are historical, not evidence of the active interpreter. Select the
container kernel explicitly even if the notebook metadata still names `compute`.

Then edit Layer 2 controls and run its cell when ready. All three notebook cells remain, but
dynamic Layer 2 outputs are not integrated with Layers 3/4. Existing schema and frozen-path
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

```bash
python -m unittest discover -s tests -v
python -m compileall -q ML tests docker
python -m pip check
git diff --check
```

Validate Compose from the host with `docker compose config --quiet`, not printed expanded secrets.
Tests cover the shared mount, interpreter and all three compilable notebook cells with portable paths.
No model calls are required. The manual Windows scale harness is not ported or run here.
Actual results and limitations are in the
[Docker track](../railway-track/tracks/2026-09-10-plain-research-docker.md).

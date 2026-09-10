# Container runtime

A Linux container for the existing CDI deep-research application. Research behavior, schemas,
prompts, tools, concurrency and context policies are unchanged; this only provides a second place
to run the same code. The host PowerShell workflow (`.\run.ps1`, the `compute` interpreter) is
untouched; its availability still depends on the host's security policy and selected environment.

## Why

On Windows, `import uuid_utils` fails because Application Control blocks its Rust extension:

```
ImportError: DLL load failed while importing _uuid_utils:
An Application Control policy has blocked this file.
```

`uuid_utils` is a transitive requirement of `langchain-core` and `langsmith`, so most of the
offline test suite cannot import. The container installs the Linux (`manylinux`) wheel instead.
**No Windows security control is disabled, modified or bypassed.** The host policy stays exactly
as it is; the container is a separate, approved deployment target.

## Prerequisites

Docker Desktop with the Linux engine (per-user install at
`%LOCALAPPDATA%\Programs\DockerDesktop`). If `docker info` fails with
`dockerDesktopLinuxEngine ... cannot find the file specified`, Docker Desktop is not running:

```powershell
Start-Process "$env:LOCALAPPDATA\Programs\DockerDesktop\Docker Desktop.exe"
```

Verified with Docker 29.6.2, Compose v5.3.1, `OSType=linux`, `Architecture=x86_64`.

## Build

```powershell
docker compose build
```

## Start the notebook

For VS Code, use the **original project with Docker Python** workflow below. Starting Jupyter does not switch
an already-open VS Code notebook away from a local Conda kernel. The host environment can still
be blocked by company Application Control; container verification does not repair Windows Conda.

```powershell
$env:JUPYTER_TOKEN = 'choose-a-long-random-value'   # optional; omit for a random per-start token
docker compose up -d notebook
docker compose logs notebook                        # prints the URL, including the token
```

Open `http://127.0.0.1:8888/lab?token=...`.

- Published on **loopback only** (`127.0.0.1:8888->8888/tcp`); the listener is `127.0.0.1`, never
  `0.0.0.0`, so it is unreachable from the network.
- **Token authentication stays enabled.** An unauthenticated `GET /api/contents` returns HTTP 403.
- **Starting the container never runs a cell and never resumes a run.** JupyterLab only renders the
  document; immediately after start `/api/kernels` is `[]` and `connections` is `0`. Research
  begins only when a human runs a cell.

## VS Code: original project with Docker Python

Install the approved Microsoft **Dev Containers** extension on the host. Open this repository,
then run **Dev Containers: Reopen in Container**. VS Code must show **Dev Container: SedAI Docker**.
Inside it, open `CDI_Layer2_Layer3.ipynb` and select **SedAI Docker — Python 3.12**, or the container
Python interpreter `/usr/local/bin/python`. Do not select Windows `compute` or base Conda.
Python and Jupyter extensions install in the remote container through its configuration.
The named kernelspec is `sedai-docker`. VS Code can also show the same interpreter as
**Python 3.12.14**; its path must be `/usr/local/bin/python`, not a Windows path.

This uses only the `dev` service and the separate `sedai-v2-dev:local` image. It does not restart
`notebook`, execute cells, publish another port, or share the browser service's research volumes.
The integrated terminal, extensions and notebook kernel run in Linux. Check before research:

```bash
python -m docker.diagnose
```

For the same check inside a temporary notebook cell, use `%run -m docker.diagnose`.
Both must report Linux, `/usr/local/bin/python`, and successful imports. This check has no model calls.

There is one working project, not an exported copy:

| Path | Backing | Behavior |
| --- | --- | --- |
| `/app` | Original Windows repository, read-write | Code, Git and notebook are the originals |
| `/app/inputs` | Original Windows `inputs` | Factsheets and requirements are editable |
| `/app/runs` | Original Windows `runs` | Previous runs are visible; new development runs save here |
| `/app/outputs` | Original Windows `outputs` | Generated development files appear on Windows |

The complete repository is mounted, including `.git` and ignored files such as `.env`.
Credentials still arrive through the existing runtime environment and never enter the image or logs.
Neither Conda nor the Docker socket is mounted. Git is installed in development; only `/app` is
trusted in the container's Git configuration. Remote URLs and credentials are not changed.
Container Git matches the host's `core.autocrlf=true` setting, avoiding false whole-file changes.
The original notebook's code, controls and outputs are preserved; no startup script rewrites it.
Native kernel selection may update its Python-version metadata; it does not rerun its cells.
Its older introduction may say `compute`: for this workflow, select Docker Python as described above.
Closing VS Code leaves the service running. To stop development only, use `docker compose stop dev`.
Do not run `docker compose down` while browser research is active: it affects the whole project.

Code edits take effect directly: **no image rebuild and no export step are needed**.
Rebuild only for dependency/image changes, using approved pins. A rebuild cannot overwrite the
mounted project. Windows-specific workspace Conda overrides have been removed; the Dev Container
selects `/usr/local/bin/python`. Windows sessions can still select their own interpreter explicitly.

The image includes the `o200k_base` tokenizer asset under `/opt/tiktoken-cache`. A completely
network-disabled fresh container can count tokens without a first-use download.

The old `sedai_sedai-dev-workspace`, `sedai_sedai-dev-runs` and `sedai_sedai-dev-outputs` volumes
remain untouched as backups, but are no longer mounted. Differing files were exported to
`outputs/dev-workspace-before-sharing-20260910` before switching; nothing was merged automatically.

Historical runs are browsable, not automatically portable or executable. Existing schema checks
and frozen path restrictions still apply. Do not execute one run from Windows and Docker at once.
The browser service's current research remains in its original volumes, not in the shared `runs`.
SQLite on the Windows bind mount can be slower than named volumes; use one environment per run.
Verification and rollout results are recorded in the
[shared-workspace track](../railway-track/tracks/2026-09-10-shared-docker-workspace.md).

## Run CLI entrypoints

These `cli` examples use the browser service's isolated run volumes. In the shared VS Code terminal,
run `python -m ML.deep_research.layer2 ...` directly to use the original project and its `runs`.

```powershell
docker compose run --rm cli python -m ML.deep_research.layer2 --help
docker compose run --rm cli python -m ML.deep_research.layer2 `
    inputs/<your-fact-sheet>.md `
    --domain-plugin ML/deep_research/layer2/plugins/real_estate.md `
    --requirements inputs/requirement.md
docker compose run --rm cli python -m ML.deep_research.layer2 --resume runs/<L2-run>
docker compose run --rm cli python -m ML.deep_research.layer2 --check-only runs/<L2-run>
docker compose run --rm cli python -m ML.deep_research.layer3 --help
docker compose run --rm cli python -m ML.deep_research.layer4 --help
```

Use container-relative paths (`inputs/...`, `runs/...`). A real Layer 2 run needs
`OPENAI_API_KEY`; see **Secrets**.

## Tests

```powershell
docker compose run --rm cli python -m unittest discover -s tests
docker compose run --rm cli python -m compileall -q ML tests
docker compose run --rm cli python -m pip check
```

The suite is offline and makes no model calls. It needs the `inputs/` mount, which Compose always
provides, because `tests/test_structure.py` reads `inputs/requirement.md`.

## Stop, recreate, remove

```powershell
docker compose down          # removes containers and the network; KEEPS the named volumes
docker compose up -d notebook  # same saved state comes back
docker compose down -v       # DESTROYS research volumes AND retained development backups
```

Only `-v` deletes research state. This was verified: state written by one container was read back
by a new container after `docker compose down`.

## Browser/CLI container paths and persistence

| Container path | Backing | Mode | Holds |
| --- | --- | --- | --- |
| `/app` | image layer | rw (ephemeral) | application code, prompts, plugins, tests |
| `/app/inputs` | host `./inputs` bind | **read-only** | factsheet and requirements |
| `/app/CDI_Layer2_Layer3.ipynb` | host file bind | rw | the notebook UI and its editable controls |
| `/app/runs` | volume `sedai_sedai-runs` | rw | run.json, run.log, `_internal/`, raw responses, publications, `evidence.sqlite3`, `checkpoints.sqlite3` |
| `/app/outputs` | volume `sedai_sedai-outputs` | rw | Layer 3/4 source cache |

**The host `runs/` and `outputs/` directories are deliberately not mounted.** Consequences, all
intended:

- Historical runs (schema 2–7) are invisible to the container, so nothing can migrate, resume or
  rewrite them. Layer 2 also rejects pre-schema-7 runs by itself.
- No run directory ever has a host writer and a container writer at the same time.
- Container runs and host runs are separate populations. Choose one place per run.

Notebook edits made in JupyterLab write through to the host file, so controls survive `down`/`up`
and stay visible to VS Code and Git.

### SQLite suitability — measured, not assumed

Layer 2 uses `PRAGMA journal_mode=WAL` for `evidence.sqlite3` and a LangGraph
`AsyncSqliteSaver` for `checkpoints.sqlite3`. Both storage options were tested inside the
container with the application's own `EvidenceStore` under its real access pattern
(300 writes, then 24 concurrent readers, then interleaved writer + 8 readers):

| Storage | `journal_mode` | 300 writes | 24 concurrent reads | Consistent | Write errors | Checkpointer |
| --- | --- | --- | --- | --- | --- | --- |
| Volume (ext4 in the Linux VM) | `wal` | **1.24 s** | 0.72 s | yes | 0 | ok |
| Windows bind mount (virtiofs) | `wal` | **11.33 s** | 0.71 s | yes | 0 | ok |

Both passed this disposable test; it does not prove every concurrent workload is safe.
Named volumes were chosen for browser/CLI because writes were **~9x faster** and because a
volume cannot be written by the host at the same time. Damaged-index recovery was also verified:
a corrupted `evidence.sqlite3` was rebuilt and the bad bytes retained as
`evidence.sqlite3.damaged-<id>`.

### Getting outputs out of a Docker volume

Volumes are not browsable in Explorer, so use one of these.

```powershell
# 1. Copy a finished run to the host (recommended for humans).
docker compose run -d --name sedai-export cli sleep 3600
docker cp sedai-export:/app/runs/L2_20260910_120000_abcd .\exported\
docker rm -f sedai-export

# 2. Read results without copying.
docker compose run --rm cli sh -lc "ls runs && cat runs/<L2-run>/README.md"
docker compose run --rm cli sh -lc "cat runs/<L2-run>/domains/*.md"

# 3. Back up the whole volume to a tar next to the repo.
docker run --rm -v sedai_sedai-runs:/from -v "${PWD}:/to" `
    busybox tar czf /to/sedai-runs-backup.tar.gz -C /from .

# 4. Restore a backup into a fresh volume.
docker run --rm -v sedai_sedai-runs:/to -v "${PWD}:/from" `
    busybox tar xzf /from/sedai-runs-backup.tar.gz -C /to
```

Back up with the container stopped, so SQLite is not mid-write. Copying a run to the host makes it
a read-only copy for humans; do not resume it from the host — resume the container-side original.

## Secrets

`OPENAI_API_KEY` is supplied at runtime only. Compose substitutes it from the host shell or the
host `.env`, which is excluded from the build context by `.dockerignore` and never enters an image
layer. Nothing prints the value. With no key set, Layer 2 fails cleanly with
`OPENAI_API_KEY is empty` before any network call.

`JUPYTER_TOKEN` is optional; when unset, JupyterLab generates a random token per start.

## Browser/CLI security posture

- Runs as non-root `appuser` (uid/gid 1000). Volumes inherit that ownership.
- `no-new-privileges:true`; no privileged mode, no added capabilities, no Docker-socket mount, no
  host mounts beyond read-only `inputs/` and the notebook file.
- Loopback-only port publishing.
- `.dockerignore` keeps `.env`, `runs/`, `outputs/`, `backup_runs/`, `inputs/`, `.git/` and caches
  out of the image and the build context.

## Browser/CLI baseline verification

| Check | Result |
| --- | --- |
| `import uuid_utils` | 0.17.0, native extension loads |
| Deep Agents / LangChain / LangGraph imports | ok |
| Layer 2, Layer 3, Layer 4 imports | ok |
| Framework versions vs host `compute` | identical (see `constraints.txt`) |
| Frozen settings | schema 7, `gpt-5.6-luna`, 60000/10000 window, concurrency 5, 300K/350K |
| `python -m unittest discover -s tests` | **159 tests, OK** |
| `python -m compileall -q ML tests` | ok |
| `python -m pip check` | No broken requirements found |
| Notebook JSON, kernel `python3`, 3 code cells compile | ok |
| Unicode filenames and content, atomic writes | ok (`Grundstück_ünïcode_✓.md`, `✓ · m² · αβ😀`) |
| Read-only `inputs/` mount | write refused: `Read-only file system` |
| SQLite WAL, concurrency, checkpointer, damaged-index recovery | ok (table above) |
| State survives container recreation | ok, verified across `docker compose down` |
| Jupyter: 403 unauthenticated, 0 kernels at start, loopback listener | ok |
| Live model or research calls during tests | none |

Environment differences from the host, both harmless: container Python is **3.12.14** (host
3.12.13) and bundled SQLite is **3.46.1** (host 3.53.2). WAL, `substr`, temp tables and the
recovery path all behave the same.

## Platform-compatibility changes made

1. **Notebook path separators.** Four literals used Windows backslashes inside raw strings, e.g.
   `Path(r"inputs\new_fact_sheet.md")`. On Linux that is one filename containing a backslash, so
   it does not resolve. They now use forward slashes, which work identically on Windows and Linux.
   Only the separator changed; the control names, values and surrounding code are untouched.
2. **`tests/test_structure.py` separator assertions.** Three assertions pinned the backslash form.
   They now accept `[\\/]`, so one notebook satisfies both platforms. The controls are still
   pinned by name, prefix and suffix — nothing was weakened beyond the separator.

`storage_path()` in `backend/fs.py` already guards its Windows extended-path form with
`os.name == "nt"` and returns a plain resolved path elsewhere, so no application change was needed
there.

## Limitations

- `tests/layer2_scale.py` imports `ctypes.wintypes` for Windows working-set and I/O counters and
  therefore **cannot run in the container**. It is a manual scale harness, not part of the offline
  suite (`unittest discover` collects `test*.py` only) and nothing imports it, so the 159-test run
  is unaffected. Run it on the host, or port the counters, if scale figures are needed.
- Layer 2 schema 7 remains **not integrated with Layers 3/4**, unchanged by this work. The Layer 3
  and Layer 4 notebook cells point at historical run folders that are not mounted in browser/CLI.
  Development can browse those folders; schema and frozen-path compatibility still govern execution.
- Browser/CLI and host runs are separate populations. Development shares host runs, but no migration
  or Windows/Linux frozen-path conversion is performed.
- The image is amd64. It was not built or tested on arm64.
- No real research run was executed: no paid model calls were made, so end-to-end runtime,
  provider latency and live extraction behavior in the container remain unverified.

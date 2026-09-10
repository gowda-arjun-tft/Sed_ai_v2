# Docker containerization

Package the existing application and its Python dependencies into a reproducible Linux
container so the research pipeline and notebook run with their current behavior, without
changing research behavior, schemas, prompts or the host PowerShell workflow.

## 2026-09-10 11:23 IST

**User**

Containerize Sed_ai_v2 on the `plain_research_v2` branch using the approved Docker environment,
without changing research behavior. Create a minimal Dockerfile, Compose configuration,
`.dockerignore` and concise documentation. Use a supported Linux Python image matching the
application's actual Python requirement and preserve installed framework versions. Mount inputs
read-only where practical, persist runs/logs/responses/evidence/checkpoints outside the container,
check SQLite suitability for the chosen Docker storage, avoid simultaneous host/container writers,
never migrate or resume historical runs automatically, keep secrets and research data out of the
image and build context, run as non-root where practical, and provide localhost-only authenticated
Jupyter that does not auto-execute research cells. Verify imports, the offline unittest suite,
compilation, `pip check`, notebook JSON and cell compilation, Unicode/mounted-path/atomic-write and
SQLite persistence with disposable fixtures, and confirm no live model calls. Report exact blockers
instead of weakening controls. Do not commit or push without authorization.

**Agent**

Completed: Added `docker/Dockerfile` (python:3.12-slim), `compose.yaml` (`notebook` and `cli`
services), `.dockerignore`, `docker/constraints.txt` pinning the 62-package `requirements.txt`
closure to host-verified versions, `docker/requirements-notebook.txt` for JupyterLab/ipykernel
under the same constraints, and `docker/README.md`. Inputs are bind-mounted read-only, the
notebook file read-write, and runs plus Layer 3/4 caches use Docker-managed volumes; host `runs/`
and `outputs/` are not mounted, so historical runs stay invisible and no run has two writers.
Non-root `appuser`, `no-new-privileges`, loopback-only authenticated JupyterLab, secrets supplied
at runtime. Two platform-compatibility edits only: four notebook path literals changed from
Windows backslashes to forward slashes, and three `tests/test_structure.py` separator assertions
relaxed to `[\\/]`. No application logic, schema, prompt, tool, concurrency or context policy was
changed, and Layer 2 schema 7 remains unintegrated with Layers 3/4. Nothing committed or pushed.

**Verification**

Ran in the container: `python -m unittest discover -s tests` — 159 tests OK;
`python -m compileall -q ML tests` — OK; `python -m pip check` — no broken requirements.
`import uuid_utils` succeeds (0.17.0 native wheel), resolving the host Application Control
`ImportError`; Deep Agents, LangChain, LangGraph and all three layers import; framework versions
match the host `compute` environment; frozen settings confirmed as schema 7, `gpt-5.6-luna`,
60000/10000 window, concurrency 5, 300K/350K. Notebook JSON valid, kernel `python3` present, all
three code cells compile, editable controls present. Unicode filenames/content and atomic writes
verified (`Grundstück_ünïcode_✓.md`); read-only `inputs/` mount refuses writes. SQLite compared
on both storage types with the application's own `EvidenceStore` (300 writes, 24 concurrent
readers, interleaved writer plus 8 readers): `wal` on both, consistent, zero write errors,
checkpointer OK, volume 1.24s vs bind mount 11.33s; damaged-index recovery rebuilt and retained
`evidence.sqlite3.damaged-<id>`. Fixture state written by one container was read back by a new
container after `docker compose down`. JupyterLab returns HTTP 403 unauthenticated, reports zero
kernels and zero connections at start, and listens on `127.0.0.1:8888` only. Notebook save
round-tripped to the host byte-identically. `git diff --check` clean; tracked diff is 12
insertions and 7 deletions across two files; host `runs/` still holds its seven historical Layer 2
runs and `inputs/` is unmodified. Disposable fixtures were deleted afterwards. No paid model,
web-search or research calls were made, so end-to-end container runtime and live extraction
behavior remain unverified. `tests/layer2_scale.py` still requires Windows (`ctypes.wintypes`) and
cannot run in the container; it is outside the offline suite.

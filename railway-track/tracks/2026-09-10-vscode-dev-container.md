# VS Code container-only development workspace

## 2026-09-10 12:07 IST

**User**

Implement an explicit full VS Code Dev Container with a container-only code copy, persistent
separate workspace/run volumes, read-only inputs, Docker-labelled Python kernel and export
instructions. Preserve the running browser notebook service, host inputs/source and research
behavior. Verify offline without paid calls, security changes or automatic research execution.

**Agent**

Completed: Added native VS Code Dev Container configuration with a separate development image,
container-only workspace and independent runs/outputs volumes. Installed the Dev Containers
extension and verified the actual remote window; Python/Jupyter installed remotely for appuser.
Registered `sedai-docker` with display name `SedAI Docker — Python 3.12`; VS Code's Python
environment selector may label the same executable `Python 3.12.14`.
The container-copy notebook has Docker instructions and unchanged code cells. Added a small
offline diagnostic, tokenizer-asset caching, export/rebuild guidance and one structure regression.
No research implementation, host notebook, inputs or historical run was edited by this task.
Changes remain local; no commit or push.

**Verification**

- VS Code visibly reports `Dev Container: SedAI Docker @ desktop-linux`, `/app` workspace.
- Integrated terminal and diagnostic-only VS Code notebook both report Linux,
  `/usr/local/bin/python`, and successful aiosqlite, uuid_utils, Deep Agents, LangChain,
  LangGraph and all three layer imports. Non-root UID 1000 and remote extensions confirmed.
- First development suite: 160 passed. A fresh `--network none` check exposed the missing
  first-use tokenizer cache; cached the public o200k_base asset at image-build time.
  Final image: 160 passed with networking disabled (42.784 seconds); compileall and pip check passed.
  Final synchronized workspace structure checks: 8 passed. PowerShell parsing and git diff --check passed.
- Workspace text and disposable SQLite data survived recreation of dev only. Inputs reject writes;
  mounts contain only the three development volumes and read-only host inputs. Selected-file export
  to a new host outputs directory matches exactly. No .env/.git/host settings/Docker socket mounted;
  API key absent from image configuration and supplied only at runtime.
- Browser container retained ID `87df437773eb1ecf856430cdab11832f560409d82e427db6c7176257d24bec18`
  and start time `2026-09-10T06:15:21.250073494Z`; no restart or run migration. Development has no research runs.
- Scratch notebook initially copied as root was corrected to appuser ownership and saved/executed
  successfully. Diagnostic artifacts remain under outputs/devcontainer-verification-20260910-1225
  on the host and outputs/devcontainer-verification in development. They contain no research or secrets.
- No model calls, research cells, dependency upgrades or Windows security changes. These checks
  establish environment readiness, not live research quality or downstream schema compatibility.

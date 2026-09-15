# Shared Responses reasoning request fix

## 2026-09-14

**User**

Fix the first metadata request failure without restarting the failed workflow.

**Agent**

Completed: normalized the shared Responses model builder to use only the native reasoning
object. The installed adapter retained an unsupported reasoning_effort argument whenever
per-stage reasoning was also supplied. Selected stage effort/summary overrides still win;
historical default effort is unchanged. No dependencies, prompts, graph, run files or
containers were changed/restarted. No live request or automatic recovery was performed.

**Verification**

Reproduced the exact TypeError in Docker with HTTP blocked before the fix. Deep Agents
0.7.7 and installed adapter source confirmed the duplicate-key conversion path.
21 focused settings/Domain Decider/research-memory tests passed; after adding a full
mock-HTTP async invocation, all 5 settings tests passed. All eight stage payloads bind
to the real SDK signature, including historical effort and constructor override cases.
Docker compilation and git diff --check passed. Full suite not rerun for this narrow
builder fix; live provider acceptance remains untested.

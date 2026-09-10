# Layer 2 web-search controls

## 2026-09-10 20:29 IST

**User**

Expose Layer 2 controls for web-search depth and verbosity, while keeping web search available only to the domain-decider stage.

**Agent**

Completed: Layer 2 exposes independently selectable low/medium/high web-search depth and response verbosity, frozen per new run and bound only to the domain designer. The notebook keeps those controls with its paths, invocation and final status paths; its introduction and redundant path/schema comments were reduced. Metadata and distribution remain without web tools. No prompt or additional architecture change was made during the notebook cleanup.

**Verification**

Focused offline Layer 2 input, request-option and structure tests passed. The final notebook JSON parsed successfully, all three code cells compiled, and the focused notebook regression test passed. Scoped `git diff --check` passed. No model or web-search call was made; changes are local and uncommitted.

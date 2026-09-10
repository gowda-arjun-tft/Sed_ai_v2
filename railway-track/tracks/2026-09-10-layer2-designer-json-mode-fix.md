# Layer 2 designer web-search / JSON-mode compatibility

## 2026-09-10 21:32 IST

**User**

Remove API-enforced JSON mode only from the web-enabled designer, retaining prompt-requested domain JSON and final Markdown. Add safe provider diagnostics and offline recovery coverage. Do not resume the failed run, change notebook/prompts/model/schema, or make live calls.

**Agent**

Completed: The designer retains native web search/depth/verbosity but no API JSON-format setting; the unchanged prompt requests domain JSON. Distribution retains JSON mode and final reports remain Markdown. Added safe provider error identifiers/status and an exact known incompatibility diagnostic, without logging arbitrary messages or bodies. Existing fingerprints automatically distinguish corrected designer requests while leaving metadata eligible for reuse. Documentation and repository guidance reflect the retained behavior. Changes are local and uncommitted.

**Verification**

39 focused offline tests passed, including an injected HTTP 400 and a four-window recovery fixture that reused every saved metadata response and completed only design/distribution. All 140 offline tests passed in Docker (91.550s) with socket connections blocked. Compilation, pip check and git diff --check passed; the full suite includes function-docstring, file-length and notebook checks. SHA-256 comparisons confirmed the real failed run, notebook and all three prompts remained unchanged. No model call, paid comparison or actual run recovery occurred. Offline request checks remove the confirmed incompatible combination; live completion and extraction quality remain unverified.

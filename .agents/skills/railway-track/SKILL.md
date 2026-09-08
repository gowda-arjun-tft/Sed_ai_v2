---
name: railway-track
description: "Maintains lightweight, durable repository memory in railway-track/vision.md, railway-track/architecture.md, railway-track/tracks/, and railway-track/change.md. Use for user-authorized features, fixes, refactors, migrations, configuration or security changes; accepted durable product or architecture decisions; and material clarifications, reversals, or rollbacks of tracked work. Do not use for read-only analysis or review, unapproved planning, greetings, routine status, or mechanical edits with no durable project impact."
---

# Railway Track

Preserve concise, truthful project context without creating a project-management system.

Railway Track records authorized work; it never authorizes the underlying work, expands its scope, or overrides the host's instruction precedence, permissions, safety controls, user direction, or applicable repository guidance. If a request materially conflicts with documented vision, boundaries, or architecture and does not explicitly authorize changing them, identify the exact conflict and ask before proceeding.

## Required Records

Maintain these repository-relative paths:

```text
railway-track/
├── vision.md
├── architecture.md
├── change.md
└── tracks/
```

| Record | Authoritative content | Mutation rule |
| --- | --- | --- |
| `vision.md` | Current approved product purpose, principles, boundaries, and durable direction | Narrowly edit current truth when authorized direction changes or an explicitly confirmed correction is needed. |
| `architecture.md` | Current implemented technical system | Narrowly edit current truth when retained implementation changes or repository evidence proves it incomplete or wrong. |
| `tracks/` | Chronological request, execution, and verification history for each outcome | Append checkpoints. Only the owner of an open checkpoint, or an agent receiving an explicit handoff, may finalize its placeholders. |
| `change.md` | Derived chronological index of significant verified outcomes and accepted decisions | Append linked entries at the bottom. |

Each information type has one authoritative home. Other records may contain a concise linked summary, but must not duplicate the complete narrative. During adoption only, a current-truth record may explicitly point to one established authoritative document instead of copying it; do not split the full narrative between both files.

## When to Record

- **Meaningful** work changes behavior, an interface or contract, data or schema, security or privacy, dependencies, build/deployment/runtime configuration, system structure, durable repository instructions, or durable product direction. Diff size alone does not decide this.
- **Approved** means explicitly requested or confirmed by an authorized user or controlling repository instruction. Never infer approval.
- An **outcome** is one independently deliverable or revertible result with shared acceptance criteria.
- **Implemented** means present in the final retained repository state, not merely planned or attempted.
- **Verified** means evidence relevant to the acceptance criteria was collected after the final retained state. File inspection verifies content or structure, not runtime behavior.
- **Significant** means a future maintainer would need the outcome to explain current behavior, intent, architecture, security posture, or a rollback.

Record meaningful implementation work, accepted durable product or architecture decisions, material clarifications to active tracked work, reversals, and rollbacks. An accepted decision is recordable before implementation, but must not be described as implemented architecture.

Append a checkpoint to the existing track when a clarification changes the scope, constraints, or acceptance criteria of the same outcome. Create a separate track for a distinct outcome. Do not record brainstorming that was not accepted, read-only analysis or review, acknowledgements, routine status, greetings, unrelated conversation, or mechanical edits with no durable project impact.

Store concise, faithful summaries. Never store raw transcripts, secrets, personal data, or invented intent.

## Initialize

When explicitly asked to initialize Railway Track, or before the first meaningful repository change in a repository where Railway Track is already installed or configured:

1. Resolve one tracking root, normally the Git root containing the installed skill. If multiple repositories, worktrees, or monorepo roots make the target ambiguous, ask before creating records.
2. Inspect repository instructions, available user direction, every required path, and version history when available for an existing or moved Railway Track installation.
3. Classify every occupied required path before writing anything. If it is unrelated or materially conflicts with the Railway Track role, do not partially initialize or repurpose it; report all known collisions and ask.
4. Create `railway-track/tracks/` and only the missing record files. Never truncate an existing file or reconstruct historical changes.
5. If an occupied required path clearly serves the same Railway Track role, preserve its substantive content and useful headings.
6. When established documentation elsewhere already owns equivalent truth, keep that narrative authoritative and use a concise cross-reference from the Railway Track record.
7. Populate current truth only from repository evidence and user-provided direction. Use `Not established` for an unknown required section; never guess.
8. Give a newly created `change.md` only `# Changes`. Never erase or backfill an existing change record.
9. If initialization accompanies an actionable request, create its track checkpoint before implementing that request.

Use these headings for a new `vision.md`:

```markdown
# Product Vision
## Product Purpose
## Target Users
## Principles
## Boundaries
## Major Capabilities
## Long-Term Direction
```

Use these headings for a new `architecture.md`, omitting sections that clearly do not apply:

```markdown
# System Architecture
## System Overview
## Components
## Data and Storage
## External Services
## Deployment
## Security
## Key Flows
```

Preserve useful existing headings when adopting Railway Track in an established repository.

## Track Workflow

1. Read `vision.md`, `architecture.md`, `change.md`, and the relevant track. When version control exists, inspect staged, unstaged, and untracked changes before editing.
2. State the requested outcome, applicable constraints, and evidence that would demonstrate completion. Resolve any unapproved conflict with current vision, boundaries, or architecture before implementation.
3. Search existing tracks before creating one. Use `YYYY-MM-DD-short-topic.md` with a lowercase kebab-case outcome slug. Reuse a track only for the same outcome; if the filename belongs to another outcome, make the new slug more specific and never overwrite it.
4. Add a checkpoint before implementation with the **Agent** value exactly `In progress` and **Verification** exactly `Not run`. The current task owns that open checkpoint. When work is delegated, one coordinating writer owns Railway Track updates and workers return evidence to it.
5. Perform only the authorized work. Do not treat Railway Track bookkeeping as permission for additional repository or external changes.
6. Verify the final retained state against the outcome. For a bug fix, reproduce the failure before editing when feasible and verify the same case afterward; record when reproduction was not possible.
7. Update current truth to match any retained implementation or approved durable direction.
8. Finalize the task's open checkpoint once by replacing its placeholders with one terminal status, the actual retained result, and the checks actually run.
9. Append a change entry only when the finalized result qualifies under **Change Log**.

Use this checkpoint format:

```markdown
## YYYY-MM-DD HH:MM TZ

**User**

Concise summary of the meaningful instruction.

**Agent**

In progress, or a terminal status followed by the actual retained result.

**Verification**

Checks actually run and their results, or `Not run` with the reason.
```

A checkpoint is open only while its **Agent** value is exactly `In progress`. Any other non-placeholder value is finalized. Begin every new finalization with exactly one of these statuses:

- `Completed:` The requested outcome is retained and relevant acceptance evidence passed. For a decision-only outcome, explicit approval is the verification.
- `Partial:` An independently useful requested subset is retained, requested work remains, or retained implementation lacks complete verification. Use `Partial` even when a blocker prevents the remaining work; state retained and remaining parts separately.
- `Blocked:` A named external condition or required decision prevented completion and no independently useful requested subset qualifies as `Partial`. State the blocker and all retained changes.
- `Failed:` The attempt did not produce a usable verified outcome. State what failed and whether anything remains changed.
- `Cancelled:` The user or controlling authority stopped the outcome. State what, if anything, remains changed.
- `Superseded:` A replacement instruction made the prior direction obsolete. State the retained state and continue with a new checkpoint.

Never claim `Completed` when relevant verification failed or was not run. Before a normal exit, finalize the task's own checkpoint truthfully; do not silently discard partial work unless authorized.

When direction changes materially, finalize the current checkpoint at its actual state, then append a new checkpoint for the replacement direction. Never rewrite an earlier **User** summary. Age alone never makes an open checkpoint stale. Treat it as stale only when the user, host, or task coordination establishes that its owner ended or was interrupted. A later agent may finalize it only after an explicit handoff; without one, append a recovery checkpoint explaining the known stale state.

Treat a rollback or revert as a distinct outcome, normally in a new track linked to the original. Preserve the original history, update current truth to the retained post-rollback state, verify the restored behavior, and append a compensating change entry when the rollback is significant and verified.

Checkpoint timestamps are display and chronology labels, not unique identifiers. Append order resolves equal timestamps. Do not backdate checkpoints, and keep finalized track filenames stable as link targets.

## Current Truth

- Update `vision.md` when approved durable product direction changes or the user explicitly confirms a correction to current intent.
- Update `architecture.md` when the retained implemented system changes, including an incomplete retained state, or repository evidence proves the current description incomplete or wrong.
- Do not put planned but unimplemented behavior in architecture. Keep plans, task status, rejected options, and historical explanations in tracks.
- Remove or revise stale current-truth statements narrowly; preserve their history in tracks and the change log.
- Never leave contradictory statements active in vision or architecture. If evidence and current authorized direction conflict, expose the conflict instead of rewriting records to hide it.

## Change Log

Before editing `change.md`, reread its latest contents. Append at the bottom; never reorder, backdate, or silently rewrite earlier entries. Use one primary tag per entry:

| Tag | Use when the significant outcome primarily... |
| --- | --- |
| `[ADDED]` | Introduces a new implemented capability or component. |
| `[CHANGED]` | Alters existing behavior, instructions, configuration, or a contract. |
| `[REMOVED]` | Removes an implemented capability, component, or supported behavior. |
| `[FIXED]` | Corrects unintended behavior or an objectively wrong implemented result. |
| `[SECURITY]` | Changes security or privacy posture. |
| `[ARCHITECTURE]` | Changes implemented system structure, boundaries, data flow, or deployment design. |
| `[DECISION]` | Records an explicitly accepted durable product or architecture decision. It may precede implementation and must not imply that implementation exists. |

Choose the tag describing the outcome's dominant reason; do not stack tags.

Use this format. Every new entry must link its authoritative track:

```markdown
- YYYY-MM-DD HH:MM TZ [TAG] Concise important outcome. ([track](tracks/YYYY-MM-DD-short-topic.md))
```

Record only significant verified implemented outcomes, independently significant verified partial outcomes, and explicitly accepted durable decisions. Do not log pending, blocked, failed, cancelled, rejected, speculative, or unverified implementation. Correct an ordinary factual error by appending a linked correction rather than silently rewriting history.

## Team Safety

- Prefer separate track files for distinct outcomes so contributors edit different files.
- Use one coordinating writer for shared records. Delegated workers return results and verification evidence instead of editing the same checkpoint or shared record.
- Treat pre-existing staged, unstaged, and untracked changes as another contributor's work. Do not alter, discard, stage, or claim them. If authorized work overlaps unexplained changes and both cannot be preserved safely, stop and ask.
- Reread a shared record immediately before editing it. If it changed since the prior read, merge the newer content before retrying. After editing, reread the file and inspect the resulting diff to confirm that no newer entry was lost.
- Follow each record's mutation rule. Never finalize another task's checkpoint without explicit handoff, and never overwrite newer context with an older local copy.
- Finalized history is immutable except for immediate in-place removal of secrets, personal data, or unsafe content. Redaction is the sole safety exception to opening a checkpoint first: remove the material immediately without repeating it, verify its absence, then append an already-finalized non-sensitive audit checkpoint. Use the affected track, the track linked by an affected non-track record, or a dedicated redaction track when neither exists. Choose the terminal status from the actual result and verification. Add `[SECURITY]` only when the redaction is significant and verified. Repairing links after an explicitly authorized file move is also allowed when historical meaning does not change.
- Append ordinary historical corrections. Do not silently rewrite them.
- During a merge conflict, preserve every valid checkpoint and change entry, remove conflict markers, and retain append order for equal timestamps.

## Finish

Before a normal exit, finalize the task's own open checkpoint. Report which Railway Track records changed, what verification ran and its result, what remains incomplete or unverified, and whether changes are only local or were committed or published. Copying a skill file is not proof that the host discovered or activated it.

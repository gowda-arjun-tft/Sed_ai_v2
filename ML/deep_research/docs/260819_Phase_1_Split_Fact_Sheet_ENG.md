# Phase 1 — cutting the fact sheet into pieces

No model. Ordinary code.

```text
Input     runs/<run_id>/inputs/fact_sheet.md
Happens   every retained ## section becomes exactly one piece
Output    runs/<run_id>/pieces/pNNN_<slug>.md
          runs/<run_id>/progress.csv
```

## Input contract

The fact sheet is non-empty Markdown with at least one `##` section. Structured sheets use `###`
fact blocks:

```markdown
## Identity, title and land

### Land-register reference

**Evidence:** "Bad Homburg v.d.Höhe Gonzenheim 2967"
**Source:** `register.pdf` — locator `p1`.
**Interpretation:** The property is registered on sheet 2967.
```

The complete `###` block is the atom. Evidence, source locator, and interpretation must remain
together. If the sheet contains no `###` facts, complete `##` sections become the atoms and the
run records `split_mode: sections`.

## Sections set aside

These sections are not property facts and are stored under `pieces/_skipped/` with their reason:

| Section | Reason |
|---|---|
| Not covered | Lists gaps rather than property facts |
| Audit appendix | Run bookkeeping |
| How to read this document | Reader instructions |
| Coverage at a glance | Coverage counts |
| Reader note | Reader instructions |
| Executive readout | Summary duplicated from full fact sections |

The executive readout is routed when it contains evidence not present elsewhere. Set-aside
content is never discarded and remains part of the lossless-cut check.

## Splitting rule

1. Every retained `##` section becomes exactly one piece.
2. Never combine two sections, even when both are small.
3. Never split one section, even when it is large.
4. Preserve every complete `###` fact block and the parent `##` heading.
5. Record an estimated token count only as metadata; it never controls a boundary.

Each piece begins with a metadata comment containing its `pNNN` identity, source section, part
number, and estimated token count. `progress.csv` records the number of facts and starts every row
as `pending`.

## Gate before phase 2

1. Every input atom appears in exactly one piece or set-aside file.
2. Piece and set-aside counts equal the original count.
3. No piece is empty.
4. Every piece carries a parent `##` heading.

The comparison is deterministic and model-free. Phase 2 cannot start if any fact was lost,
duplicated by the section cut, or altered.

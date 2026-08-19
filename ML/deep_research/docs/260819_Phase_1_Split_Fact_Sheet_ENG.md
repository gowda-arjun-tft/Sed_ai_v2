# Phase 1 — split JSON claims into pieces

No model. Ordinary code.

```text
Input     runs/<run_id>/inputs/claims.json
Happens   complete claim objects are grouped into bounded pieces
Output    runs/<run_id>/pieces/pNNN_claims.md
          runs/<run_id>/progress.csv
```

## Accepted JSON contract

The external input is JSON-only. It may be either:

```json
[
  {"claim_type": "annual_rent", "amount": 100000}
]
```

or:

```json
{
  "claims": [
    {"claim_type": "annual_rent", "amount": 100000}
  ]
}
```

Every claim must be a non-empty JSON object. Claim field names are deliberately unrestricted;
Layer 2 preserves the complete object instead of guessing which keys mean evidence, source, or
interpretation. Empty inputs, scalar claims, invalid JSON, and Markdown inputs stop before a run
is created.

## Internal claim blocks

Each object becomes a deterministic block containing the complete JSON value and its input JSON
pointer:

````markdown
### Claim 001

**JSON Pointer:** `/claims/0`

```json
{
  "claim_type": "annual_rent",
  "amount": 100000
}
```
````

These Markdown files are internal agent artifacts, not an input dependency. They give the model a
clear claim boundary while the JSON object remains the source of truth.

## Splitting rule

Claims stay in input order. The splitter groups complete blocks until the next block would exceed
the soft 8,000-token target, then starts another piece. A single oversized claim remains intact;
claims are never truncated or divided.

Each piece begins with `## Claims` and a metadata comment carrying its piece id, part number, and
estimated size. `progress.csv` records the exact number of claims in every piece.

## Gate before phase 2

1. Every input claim appears in exactly one piece.
2. Every key and value survives JSON serialization unchanged.
3. No piece is empty.
4. Every piece carries its `## Claims` parent heading.

The lossless comparison is deterministic and model-free. Phase 2 cannot start if any claim is
missing, duplicated by the cut, or altered.

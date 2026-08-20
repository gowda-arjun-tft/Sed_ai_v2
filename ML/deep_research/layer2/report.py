"""Step 3 of 3 -- the run report.

No model. Eight checks, then two artefacts: `check_report.md` for a human and a
completed `run.json` for Layer 3.

**Every check here is bookkeeping.** Each one asks whether the deliverable is
*present and well-formed* -- fourteen files, three keys, four keys per context
entry, a non-empty locator. Not one of them asks whether the agent's judgement
was good, and none of them can change what the agent produced. By the time this
module runs, the agent has finished; a failure means the run is incomplete, not
that the agent misbehaved.

**What is deliberately not checked.** There is no coverage threshold, no
transcription comparison and no wording rule. A fact that legitimately belongs to
three subjects appears three times, so sheet totals and mission totals differ for
good reasons and no threshold would be honest. Check 7 therefore prints the
counts and draws no conclusion -- that is the number a human needs, and the
judgement is not this module's to make. `test_checks.py` pins this by emptying a
mission's context and asserting the report still passes.

The agent does its own lossless check during the run, with Python, against both
sides on disk -- and unlike a code gate it can go and fix what it finds.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .fs import atomic_write_text, load_json, now_iso, read_text, sha256, slug, write_json
from .planner import load_planner
from .settings import AGENT_NAMES

# `(number, label, passed, detail)`. A plain tuple because both layers' CLIs
# consume it the same way and it has to stay trivially printable.
Check = tuple[int, str, bool, str]

# The mission contract, and the reason it is a set comparison rather than a
# subset test: an extra top-level key would mean the agent invented structure
# Layer 3 will not read, which is worth reporting.
MISSION_KEYS = {"agent", "mission", "context"}
CONTEXT_KEYS = {"section", "fact", "means", "where"}


def fact_blocks(text: str) -> list[str]:
    """Every `###` block in the sheet, for counting only.

    A block runs from its `###` heading to the next heading of any level, so a
    `##` section boundary ends a block as well.

    This is the last regex in Layer 2 that looks at the fact sheet, and it counts
    structure rather than reading content: no field labels, no expected wording,
    nothing language-specific. `(?!#)` excludes `####` and deeper so a nested
    heading is not counted as a second block.

    The regex extraction that used to live here -- pulling `Evidence:`,
    `Source:` and `Interpretation:` out of each block with patterns -- is gone.
    The agent transcribes those itself, which is why nothing in Python needs to
    understand the shape of a fact block or the English labels it happened to use.
    """
    headings = list(re.finditer(r"(?m)^##(?:#)? (?!#).+?\s*$", text))
    return [
        text[
            heading.start() : headings[index + 1].start()
            if index + 1 < len(headings)
            else len(text)
        ].strip()
        for index, heading in enumerate(headings)
        if heading.group(0).startswith("### ")
    ]


def run_checks(run_dir: Path) -> list[Check]:
    """Check one run folder, write both artefacts, and return the results.

    Args:
        run_dir: A `runs/L2_*` folder, finished or half-finished.

    Returns:
        The eight checks in order. The caller's exit code is
        `0 if all passed else 1`.

    Side effects, in this order:

    1. `check_report.md` is written -- so it exists even if stamping fails,
    2. `run.json` gains `checks`, `facts`, `status` and `finished_at`.

    Safe to run again on the same folder. `--check-only` does exactly that, and
    it is how a run whose report was interrupted is completed without another
    model call.
    """
    run = load_json(run_dir / "run.json")
    fact_copy = run_dir / "inputs" / "fact_sheet.md"
    planner_copy = run_dir / "inputs" / "planner_prompt.md"
    missions = _load_missions(run_dir)

    checks, facts = _build_checks(fact_copy, planner_copy, missions, run)
    _write_report(run_dir, run, checks)

    passed = sum(ok for _, _, ok, _ in checks)
    run["checks"] = {
        "run": len(checks),
        "passed": passed,
        "failed": len(checks) - passed,
    }
    run["facts"] = facts
    # Layer 3 refuses a run that does not say "complete" with every check passed.
    # The count itself is never hardcoded on either side -- both check lists are
    # expected to change, so the rule is "all of them", not "eight of them".
    run["status"] = "complete" if passed == len(checks) else "failed"
    run["finished_at"] = now_iso()
    write_json(run_dir / "run.json", run)
    return checks


def _load_missions(run_dir: Path) -> dict[str, Any]:
    """Load the mission files, keyed by roster name.

    Looks for exactly `missions/<slug(name)>.json` for each of the fourteen
    names, so a file the agent named something else simply does not appear -- and
    check 3 reports the shortfall.

    A file that exists but will not parse is stored as `None` rather than raising,
    so one malformed mission is reported as a failed check instead of crashing the
    report and leaving the run with no record at all. Checks 4, 5 and 8 all guard
    for `isinstance(value, dict)` because of this.
    """
    missions: dict[str, Any] = {}
    for name in AGENT_NAMES:
        path = run_dir / "missions" / f"{slug(name)}.json"
        if path.is_file():
            try:
                missions[name] = load_json(path)
            except (OSError, ValueError):
                missions[name] = None
    return missions


def _build_checks(
    fact_copy: Path,
    planner_copy: Path,
    missions: dict[str, Any],
    run: dict[str, Any],
) -> tuple[list[Check], dict[str, int]]:
    """Run the eight checks and return them with the fact counts.

    Returns:
        `(checks, facts)` -- the check list for the report, and the three numbers
        stamped into `run.json` under `facts`.

    The checks, and what each one protects:

    1. **Inputs match their hashes** -- proves the run was checked against the
       same bytes it was given, and that nothing edited an input mid-run.
    2. **The planner copy holds the frozen roster** -- the copy, not the
       repository file, because that copy is what Layer 3 will read.
    3. **Fourteen mission files exist** -- one per roster name, by slug.
    4. **Each mission parses and has exactly the three top-level keys.**
    5. **Each mission names its own agent** -- catches content written into the
       wrong file, which a filename check alone cannot see.
    6. **Each context entry has the four keys and a non-empty `where`** -- the
       locator is what Layer 3 traces a fact back through, so an empty one makes
       the fact unusable downstream.
    7. **Fact counts** -- reported, never judged. Always passes.
    8. **Each mission carries prose** -- an empty `mission` string would leave a
       Layer 3 researcher with nothing to establish. A mission saying the sheet is
       silent on its subject is a normal, passing outcome.
    """
    checks: list[Check] = []

    def add(number: int, label: str, ok: bool, detail: str = "") -> None:
        """Append one check. `detail` is the numbers a human reads after it."""
        checks.append((number, label, bool(ok), detail))

    add(
        1,
        "Both inputs are present and match their recorded hashes",
        fact_copy.is_file()
        and planner_copy.is_file()
        and sha256(fact_copy) == run.get("fact_sheet", {}).get("sha256")
        and sha256(planner_copy) == run.get("planner_prompt", {}).get("sha256"),
    )

    try:
        _, definitions = load_planner(planner_copy)
        roster_ok = [item["name"] for item in definitions] == AGENT_NAMES
    except (OSError, ValueError):
        roster_ok = False
    add(2, "The planner copy holds the frozen roster", roster_ok)

    add(
        3,
        "One mission file exists per roster agent",
        len(missions) == len(AGENT_NAMES),
        f"found={len(missions)} of {len(AGENT_NAMES)}",
    )
    add(
        4,
        "Every mission parses and has exactly the three top-level keys",
        bool(missions)
        and all(
            isinstance(value, dict) and set(value) == MISSION_KEYS
            for value in missions.values()
        ),
    )
    add(
        5,
        "Every mission names its own agent",
        bool(missions)
        and all(
            isinstance(value, dict) and value.get("agent") == name
            for name, value in missions.items()
        ),
    )

    entries = [
        item
        for value in missions.values()
        if isinstance(value, dict)
        for item in value.get("context", [])
    ]
    add(
        6,
        "Every context entry has the four keys and a non-empty locator",
        all(
            isinstance(item, dict)
            and set(item) == CONTEXT_KEYS
            and str(item.get("where", "")).strip()
            for item in entries
        ),
        f"entries={len(entries)}",
    )

    # Reported, never judged -- passed=True unconditionally. A fact belonging to
    # three subjects appears three times, so `context_entries` exceeding
    # `sheet` is normal and `distinct_facts` is the closer comparison. Numbers
    # far apart are worth a human's attention; no number here is worth a gate.
    sheet_blocks = len(fact_blocks(read_text(fact_copy))) if fact_copy.is_file() else 0
    distinct = len({str(item.get("fact", "")) for item in entries})
    add(
        7,
        "Fact counts, for reading",
        True,
        f"sheet={sheet_blocks} context_entries={len(entries)} distinct_facts={distinct}",
    )

    add(
        8,
        "Every mission carries prose",
        bool(missions)
        and all(
            isinstance(value, dict) and str(value.get("mission", "")).strip()
            for value in missions.values()
        ),
    )

    facts = {
        "sheet_blocks": sheet_blocks,
        "context_entries": len(entries),
        "distinct_facts": distinct,
    }
    return checks, facts


def _write_report(run_dir: Path, run: dict[str, Any], checks: list[Check]) -> None:
    """Write `check_report.md`: the tally, then one ticked line per check.

    A Markdown task list, so a failed check is visible at a glance in any viewer
    and the file diffs line by line between runs. `detail` carries the numbers --
    check 7's counts, check 3's shortfall -- after an em dash.

    Written atomically, and written before `run.json` is stamped, so an
    interruption leaves a readable report rather than nothing.
    """
    passed = sum(ok for _, _, ok, _ in checks)
    lines = [
        f"# Run {run.get('run_id', run_dir.name)} — report",
        "",
        f"{len(checks)} checks · {passed} passed · {len(checks) - passed} failed",
        "",
        "## Checks",
        "",
    ]
    lines.extend(
        f"- [{'x' if ok else ' '}] {number}. {label}" + (f" — {detail}" if detail else "")
        for number, label, ok, detail in checks
    )
    atomic_write_text(run_dir / "check_report.md", "\n".join(lines) + "\n")

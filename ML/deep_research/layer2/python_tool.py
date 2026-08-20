"""The `run_python` tool: the agent's calculator and its own auditor.

Why the agent needs this at all. Two jobs in a Layer 2 run are exact rather than
judgemental, and a language model is the wrong instrument for both:

* **Measuring the sheet before reading it** — how long is it, how many `###`
  blocks, where does each heading start. A few hundred tokens of Python answers
  that whether the sheet is 16,000 tokens or three million, so the agent knows
  which shape of work it is in before it has spent any attention.
* **Proving nothing was lost afterwards** — counting context entries across the
  fourteen mission files and naming any heading that reached none of them. Exact,
  repeatable, and it costs the agent's context nothing however large the sheet.

The division of labour the prompt states: Python counts, finds, diffs and checks;
the agent decides what belongs where.

**No limits, by design.** No timeout, no output cap, no import denylist, no
sandbox. Anything of that kind would be a Python-side rule about what the agent
is allowed to compute, and Layer 2 has none. A subprocess is used so that a crash
in the agent's snippet ends the snippet rather than the run — that is isolation
for robustness, not restriction.

Duplicated deliberately rather than imported from `layer3`: Layer 2 must not
depend on Layer 3. Sixty lines beats an inverted dependency between the layers.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass

from langchain.tools import tool


@dataclass(frozen=True)
class PythonResult:
    """One snippet's outcome, kept structured for tests.

    Attributes:
        ok: True when the interpreter exited 0.
        stdout: Everything the snippet printed. Never truncated.
        stderr: Traceback or warnings. Never truncated.
    """

    ok: bool
    stdout: str
    stderr: str

    def render(self) -> str:
        """Format the result as the string the model sees.

        Empty streams are omitted so a successful snippet does not spend the
        agent's context on a blank `stderr:` heading. A snippet that printed
        nothing says so explicitly rather than returning an empty string, which
        would read as a tool failure.
        """
        parts = []
        if self.stdout.strip():
            parts.append(f"stdout:\n{self.stdout.rstrip()}")
        if self.stderr.strip():
            parts.append(f"stderr:\n{self.stderr.rstrip()}")
        return "\n\n".join(parts) if parts else "The code produced no output."


def run_python_code(code: str) -> PythonResult:
    """Execute one snippet in a fresh interpreter and capture both streams.

    `sys.executable` is used so the snippet runs under the same interpreter as
    the run, with the same installed packages. `check=False` because a non-zero
    exit is information to hand back, not an exception to raise — the agent reads
    the traceback and fixes its own code.

    `errors="replace"` on decoding: a snippet that prints bytes in an unexpected
    encoding returns mangled characters rather than raising a `UnicodeDecodeError`
    that would tell the agent nothing about what its code did.

    An `OSError` — the interpreter itself failing to start — is returned as a
    failed result rather than propagating, so a spawn problem cannot end the run.

    This is the function tests call; `run_python` is the thin tool wrapper.
    """
    try:
        completed = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as error:
        return PythonResult(False, "", f"{type(error).__name__}: {error}")
    return PythonResult(
        completed.returncode == 0,
        completed.stdout or "",
        completed.stderr or "",
    )


@tool(parse_docstring=True)
def run_python(code: str) -> str:
    """Run Python and return what it prints.

    The run folder is on the real filesystem, so this can read the fact sheet and
    the mission files directly.

    Args:
        code: Python to execute. Print what you want back.
    """
    # This docstring is the tool description the model reads, which is why it is
    # written for the model and not for a maintainer. `parse_docstring=True`
    # turns the Args block into the argument schema. The absolute path to the run
    # folder is supplied separately, in the system prompt.
    return run_python_code(code).render()

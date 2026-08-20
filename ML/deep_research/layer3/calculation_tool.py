"""The `run_python` tool.

One general capability rather than a tool per calculation: the researcher writes
whatever arithmetic it needs. The code and its output are kept so a derived
figure can be traced later, but nothing requires the researcher to use this, and
nothing checks what it computes.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass

from langchain.tools import ToolRuntime, tool
from langgraph.types import Command

from .contracts import ResearchContext, ResearchState
from .research_tools import tool_command
from .sources import SourceStore


@dataclass(frozen=True)
class PythonResult:
    ok: bool
    stdout: str
    stderr: str

    def render(self) -> str:
        parts = []
        if self.stdout.strip():
            parts.append(f"stdout:\n{self.stdout.rstrip()}")
        if self.stderr.strip():
            parts.append(f"stderr:\n{self.stderr.rstrip()}")
        return "\n\n".join(parts) if parts else "The code produced no output."


def run_python_code(code: str) -> PythonResult:
    """Execute one snippet and return whatever it printed."""
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
def run_python(
    code: str,
    purpose: str,
    runtime: ToolRuntime[ResearchContext, ResearchState],
) -> Command:
    """Run Python and return what it prints.

    Args:
        code: Python to execute. Print what you want back.
        purpose: What this computes. May be empty.
    """
    result = run_python_code(code)
    SourceStore(runtime.context.run_dir).record_calculation(
        session_id=runtime.context.session_id,
        agent=runtime.context.agent,
        lens=runtime.context.lens,
        purpose=purpose,
        code=code,
        stdout=result.stdout,
        stderr=result.stderr,
        ok=result.ok,
    )
    return tool_command(runtime, result.render())

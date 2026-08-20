"""Question lists written by aggregator pass 1.

The structured `QuestionSet` is the source of truth and is persisted as JSON,
exactly as the model returned it. The Markdown file beside it is a human
rendering that is never read back.

Nothing here inspects, filters or drops a question. Attribution cannot leak
because the schema has nowhere to record it -- a question is a bare string and no
field names a lens.
"""

from __future__ import annotations

import json
from pathlib import Path

from ML.deep_research.layer2.fs import atomic_write_text, load_json


def questions_json_path(path: Path) -> Path:
    """The machine-readable sibling of a rendered question file."""
    return path.with_suffix(".json")


def write_question_file(path: Path, agent: str, lens: str, questions: list[str]) -> None:
    """Persist the list as JSON, and render a readable Markdown copy."""
    atomic_write_text(
        questions_json_path(path),
        json.dumps(
            {"agent": agent, "lens": lens, "questions": questions},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )
    header = f"<!-- questions p1 · {agent} · {lens} · {len(questions)} -->"
    body = "\n".join(f"- {question}" for question in questions)
    atomic_write_text(path, header + "\n" + (body + "\n" if body else ""))


def read_questions(path: Path) -> list[str]:
    """Read the JSON source of truth. Never parses the rendered Markdown."""
    source = questions_json_path(path)
    if not source.is_file():
        return []
    try:
        return list(load_json(source).get("questions", []))
    except (OSError, ValueError, TypeError):
        return []

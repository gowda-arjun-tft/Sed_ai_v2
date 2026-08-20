"""Offline and online retrieval providers."""

from pathlib import Path
from typing import Any


def from_run(run: dict[str, Any], run_dir: Path) -> Any:
    if run.get("provider") == "fixture":
        from .fixture import FixtureRetriever

        return FixtureRetriever(Path(str(run["fixture_root"])))
    if run.get("provider") == "online":
        from .openai_search import OpenAISearchRetriever

        return OpenAISearchRetriever(run_dir)
    raise ValueError(f"unknown Layer 3 provider: {run.get('provider')}")

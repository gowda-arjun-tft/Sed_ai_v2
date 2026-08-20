"""Layer 3 online retrieval provider."""

from pathlib import Path
from typing import Any


def from_run(run: dict[str, Any], run_dir: Path) -> Any:
    if run.get("provider") == "online":
        from .openai_search import OpenAISearchRetriever

        return OpenAISearchRetriever(run_dir)
    raise ValueError("Layer 3 runs require the online provider")

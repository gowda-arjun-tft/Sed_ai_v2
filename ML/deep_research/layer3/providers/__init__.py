"""Layer 3 online retrieval provider."""

from pathlib import Path
from typing import Any

from ..settings import (
    REASONING_EFFORT,
    WEB_SEARCH_CONTEXT_SIZE,
    WEB_SEARCH_VERBOSITY,
)


def from_run(run: dict[str, Any], run_dir: Path) -> Any:
    if run.get("provider") == "online":
        from .openai_search import OpenAISearchRetriever

        search = run.get("web_search", {})
        extraction = run.get("document_extraction")
        max_document_bytes = (
            int(extraction["max_document_bytes"])
            if isinstance(extraction, dict)
            and extraction.get("policy_version") == 1
            and "max_document_bytes" in extraction
            else None
        )
        return OpenAISearchRetriever(
            run_dir,
            reasoning_effort=run.get("reasoning_effort", REASONING_EFFORT),
            context_size=search.get("context_size", WEB_SEARCH_CONTEXT_SIZE),
            verbosity=search.get("verbosity", WEB_SEARCH_VERBOSITY),
            max_document_bytes=max_document_bytes,
        )
    raise ValueError("Layer 3 runs require the online provider")

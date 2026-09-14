"""Public async entrypoint for Layer 3 source preparation and domain research."""

from pathlib import Path


async def run_research(run_dir: Path, *, retry_failed: bool = False) -> None:
    """Dispatch the run through its frozen preparation and research capabilities."""
    from .source_runner import run_sources

    await run_sources(run_dir, retry_failed=retry_failed)

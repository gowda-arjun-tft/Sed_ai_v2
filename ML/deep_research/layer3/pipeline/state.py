from __future__ import annotations

from pathlib import Path

from ML.deep_research.layer2.fs import load_json, now_iso, write_json


def mark_phase(run_dir: Path, phase: int, status: str = "complete") -> None:
    run = load_json(run_dir / "run.json")
    run.setdefault("phases", {})[str(phase)] = status
    run["status"] = f"phase_{phase}_{status}"
    run["updated_at"] = now_iso()
    write_json(run_dir / "run.json", run)

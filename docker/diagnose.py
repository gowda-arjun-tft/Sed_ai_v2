"""Offline environment check for a container terminal or notebook kernel; no secrets or calls."""

import importlib
import platform
import sys


def main() -> None:
    """Input the active interpreter; print identity/import checks and fail if not the Docker runtime."""
    print(f"System: {platform.system()} | Python: {sys.executable}")
    if platform.system() != "Linux" or sys.executable != "/usr/local/bin/python":
        raise RuntimeError("Use Dev Containers: Reopen in Container, then select /usr/local/bin/python.")
    for name in ("aiosqlite", "uuid_utils", "deepagents", "langchain", "langgraph",
                 "ML.deep_research.layer2", "ML.deep_research.layer3", "ML.deep_research.layer4"):
        importlib.import_module(name)
        print(f"{name}: OK")
    print("Ready. No research or model calls were executed.")


if __name__ == "__main__":
    main()

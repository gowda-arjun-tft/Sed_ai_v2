"""Offline native-graph scale exercise; synthetic outputs do not measure extraction quality."""

import argparse
import ctypes
import json
import os
import time
from collections import Counter
from ctypes import wintypes
from pathlib import Path
from unittest.mock import patch

import httpx
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_openai import ChatOpenAI

from ML.deep_research.layer2 import create_run, run_all
from ML.deep_research.layer2.backend.evidence import EvidenceStore
from ML.deep_research.layer2.backend.fs import load_json
from ML.deep_research.layer2.backend.windows import encoding
from ML.deep_research.layer2.ML.evidence_backend import EvidenceBackend


class Memory(ctypes.Structure):
    """Windows working-set counters from the current process."""

    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
        (name, ctypes.c_size_t) for name in (
            "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
            "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]


class IO(ctypes.Structure):
    """Windows process-level logical I/O counters, not physical disk measurements."""

    _fields_ = [(name, ctypes.c_ulonglong) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


def metrics():
    """Input none; return OS process peak RAM and logical bytes read/written."""
    memory, io = Memory(), IO()
    memory.cb = ctypes.sizeof(memory)
    process = ctypes.windll.kernel32.GetCurrentProcess
    process.restype = wintypes.HANDLE
    memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
    memory_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(Memory), wintypes.DWORD]
    io_info = ctypes.windll.kernel32.GetProcessIoCounters
    io_info.argtypes = [wintypes.HANDLE, ctypes.POINTER(IO)]
    assert memory_info(process(), ctypes.byref(memory), memory.cb)
    assert io_info(process(), ctypes.byref(io))
    return {"peak_working_set_bytes": memory.PeakWorkingSetSize,
            "working_set_bytes": memory.WorkingSetSize,
            "logical_read_bytes": io.ReadTransferCount, "logical_write_bytes": io.WriteTransferCount}


async def generate(model, messages, **kwargs):
    """Input a native model dispatch; return compact synthetic JSON without using a provider."""
    data = json.loads(next(m.content for m in reversed(messages) if m.type == "human"))
    if "source" in data and "mode" not in data:
        value = {"profile": "Operating subject; original source available by pointer.",
                 "evidence": [{"fact": "Synthetic navigation entry", "source": data["source"]["source_id"]}]}
    elif "subject" in data:
        value = {"domains": [{"name": "Operations", "responsibilities": ["Recorded conditions"]}]
                 if not data["domain_definitions"] else []}
    elif "source" in data:
        value = {"facts": [{"body": {"section": "Recorded conditions", "fact": "Synthetic source-window fact",
                                      "source": data["source"]["source_id"]}, "domain_ids": ["d0001"]}]}
    elif "observations" in data:
        value = {"domains": [], "dispositions": []}
    elif "domain_plugin" in data:
        value = {"observations": []}
    else:
        value = {"assignments": [{"fact_id": f["fact_id"], "domain_ids": ["d0001"]} for f in data["facts"]]}
    return ChatResult(generations=[ChatGeneration(message=AIMessage(content=json.dumps(value)))])


def main():
    """Input command flags; measure preparation or native fake execution in a separate process."""
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "execute"])
    parser.add_argument("root", type=Path)
    parser.add_argument("--tokens", type=int, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    if args.phase == "prepare":
        assert len(encoding().encode(" property")) == len(encoding().encode(" insurance")) == 1
        with (root / "facts.md").open("w", encoding="utf-8") as handle:
            remaining = args.tokens - 1
            while remaining:
                size = min(remaining, 100_000)
                handle.write(" property" * size)
                remaining -= size
            handle.write(" insurance")
        (root / "plugin.md").write_text("## Operations\nPreserve original subject conditions.", encoding="utf-8")
        (root / "requirements.md").write_text("Offline operational fixture only.", encoding="utf-8")
    before, start = metrics(), time.perf_counter()
    if args.phase == "prepare":
        run = create_run(root / "facts.md", root / "plugin.md", root / "requirements.md", root / "runs")
        manifest = load_json(run / "_internal/trace/source/manifest.json")
        assert manifest[-1]["end_token"] == args.tokens
        assert len(manifest) == 1 + max(0, (args.tokens - 60_000 + 49_999) // 50_000)
        assert all("new_content" not in row and "overlap_context" not in row for row in manifest)
        (root / "run-path.txt").write_text(str(run), encoding="utf-8")
    else:
        run = Path((root / "run-path.txt").read_text(encoding="utf-8"))
        with patch.dict(os.environ, {"OPENAI_API_KEY": "offline-scale"}), patch.object(
            ChatOpenAI, "_agenerate", generate,
        ), patch.object(httpx.AsyncClient, "send", side_effect=AssertionError("No network allowed")), patch.object(
            httpx.Client, "send", side_effect=AssertionError("No network allowed"),
        ):
            run_all(run)
        store = EvidenceStore(run)
        backend = EvidenceBackend(run, version=store.snapshot())
        matches = backend.grep(" insurance", "/source/")
        assert len(matches.matches) == 1, "Distant original source must remain retrievable"
        assert "insurance" in backend.read(matches.matches[0]["path"]).file_data["content"]
        assert load_json(run / "run.json")["status"] == "complete"
    after = metrics()
    record = load_json(run / "run.json")
    result = {"phase": args.phase, "source_tokens": args.tokens, "run": str(run),
              "seconds": round(time.perf_counter() - start, 3), **after,
              "baseline_working_set_bytes": before["working_set_bytes"],
              "logical_read_bytes": after["logical_read_bytes"] - before["logical_read_bytes"],
              "logical_write_bytes": after["logical_write_bytes"] - before["logical_write_bytes"],
              "jobs": dict(Counter(j["stage"] for j in record["jobs"].values())),
              "database_bytes": {p.name: p.stat().st_size for p in (run / "_internal/trace").glob("*.sqlite3*")}}
    (root / f"{args.phase}-metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()

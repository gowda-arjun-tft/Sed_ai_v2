"""Subprocess supervision for durable Docling extraction jobs."""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from ML.deep_research.layer2.fs import now_iso, write_json

from .document_extraction import (
    MAX_DOCUMENT_ATTEMPTS,
    ExtractionPolicy,
    extraction_policy,
    load_manifest,
    manifest_path,
)


def _heartbeat_is_fresh(manifest: dict[str, Any], stale_seconds: int) -> bool:
    try:
        heartbeat = datetime.fromisoformat(
            str(manifest.get("heartbeat_at", "")).replace("Z", "+00:00")
        )
    except ValueError:
        return False
    return (datetime.now(UTC) - heartbeat).total_seconds() < stale_seconds


def _worker_process(*args: str) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        [sys.executable, "-m", "ML.deep_research.layer3.document_worker", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


async def _run_worker(run_dir: Path, source_id: str, policy: ExtractionPolicy) -> None:
    process = _worker_process("--run-dir", str(run_dir), "--source-id", source_id)
    communication = asyncio.create_task(asyncio.to_thread(process.communicate))
    try:
        while not communication.done():
            await asyncio.wait({communication}, timeout=policy.worker_heartbeat_seconds)
            manifest = load_manifest(run_dir, source_id)
            if (
                not communication.done()
                and manifest is not None
                and manifest.get("status") == "running"
                and manifest.get("worker_pid") == process.pid
                and not _heartbeat_is_fresh(manifest, policy.worker_stale_seconds)
            ):
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass
                await asyncio.shield(communication)
                raise ChildProcessError("document worker heartbeat expired")
        stdout, stderr = await communication
    except asyncio.CancelledError:
        if process.returncode is None:
            try:
                process.terminate()
            except ProcessLookupError:
                pass
            await asyncio.shield(communication)
        raise
    if process.returncode:
        manifest = load_manifest(run_dir, source_id) or {}
        message = (stderr or stdout).decode("utf-8", errors="replace").strip()
        if not message and manifest.get("error"):
            message = f"{manifest.get('error_type')}: {manifest['error']}"
        raise ChildProcessError(message or f"document worker exited {process.returncode}")


async def preflight_document_worker(run_dir: Path) -> None:
    """Prove the configured Docling child can start before any paid request."""
    policy = extraction_policy(run_dir)
    if policy is None:
        return
    process = _worker_process("--check", "--ocr-languages", ",".join(policy.ocr_languages))
    stdout, stderr = await asyncio.to_thread(process.communicate)
    if process.returncode:
        detail = (stderr or stdout).decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"Docling worker preflight failed: {detail or f'exit {process.returncode}'}")


def _pid_is_alive(value: Any) -> bool:
    try:
        pid = int(value)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetExitCodeProcess.argtypes = (
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.DWORD),
        )
        kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
        process = kernel32.OpenProcess(0x1000, False, pid)
        if not process:
            return False
        code = wintypes.DWORD()
        try:
            return (
                bool(kernel32.GetExitCodeProcess(process, ctypes.byref(code)))
                and code.value == 259
            )
        finally:
            kernel32.CloseHandle(process)
    try:
        os.kill(pid, 0)
    except (OSError, PermissionError):
        return False
    return True


def _terminate_pid(value: Any) -> bool:
    try:
        pid = int(value)
        if pid <= 0 or pid == os.getpid():
            return False
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except (OSError, TypeError, ValueError):
        return False
    return True


async def _wait_for_live_worker(
    run_dir: Path,
    source_id: str,
    policy: ExtractionPolicy,
) -> dict[str, Any] | None:
    manifest = load_manifest(run_dir, source_id)
    while manifest is not None and manifest.get("status") == "running":
        pid = manifest.get("worker_pid")
        if not _pid_is_alive(pid):
            break
        if not _heartbeat_is_fresh(manifest, policy.worker_stale_seconds):
            if not _terminate_pid(pid):
                raise ChildProcessError(f"stale document worker {pid} could not be terminated")
            await asyncio.sleep(min(1, policy.worker_heartbeat_seconds))
            if _pid_is_alive(pid):
                raise ChildProcessError(f"stale document worker {pid} did not stop")
            manifest.update(status="pending", worker_pid=None, updated_at=now_iso())
            write_json(manifest_path(run_dir, source_id), manifest)
            return manifest
        await asyncio.sleep(policy.worker_heartbeat_seconds)
        manifest = load_manifest(run_dir, source_id)
    return manifest


def _mark_failed(
    run_dir: Path,
    source_id: str,
    error: Exception,
    *,
    retryable: bool = True,
) -> dict[str, Any]:
    manifest = load_manifest(run_dir, source_id) or {"source_id": source_id}
    manifest.update(
        status="failed",
        error_type=type(error).__name__,
        error=str(error) or repr(error),
        retryable=retryable,
        updated_at=now_iso(),
        heartbeat_at=now_iso(),
    )
    write_json(manifest_path(run_dir, source_id), manifest)
    return manifest


async def process_document_interrupts(run_dir: Path, interrupts: Iterable[Any]) -> dict[str, Any]:
    """Process serialized/real LangGraph document interrupts serially."""
    results: dict[str, Any] = {}
    for item in interrupts:
        interrupt_id = item.get("id") if isinstance(item, dict) else getattr(item, "id", None)
        value = item.get("value") if isinstance(item, dict) else getattr(item, "value", None)
        if (
            not interrupt_id
            or not isinstance(value, dict)
            or value.get("type") != "document_extraction"
            or not value.get("source_id")
        ):
            raise ValueError("Layer 3 received an unsupported LangGraph interrupt")
        source_id = str(value["source_id"])
        manifest = load_manifest(run_dir, source_id)
        if manifest is None:
            raise RuntimeError(f"document job {source_id} is missing")
        policy = extraction_policy(run_dir)
        if policy is None:
            raise RuntimeError("document extraction policy is missing")
        try:
            manifest = await _wait_for_live_worker(run_dir, source_id, policy)
        except ChildProcessError as error:
            manifest = _mark_failed(run_dir, source_id, error, retryable=False)
        if manifest is None:
            raise RuntimeError(f"document job {source_id} disappeared")
        while (
            manifest.get("status") != "complete"
            and manifest.get("retryable", True)
            and int(manifest.get("attempt", 0)) < MAX_DOCUMENT_ATTEMPTS
        ):
            attempt_before = int(manifest.get("attempt", 0))
            manifest.update(status="pending", worker_pid=None, updated_at=now_iso())
            write_json(manifest_path(run_dir, source_id), manifest)
            try:
                await _run_worker(run_dir, source_id, policy)
            except ChildProcessError as error:
                latest = load_manifest(run_dir, source_id)
                if latest is None or latest.get("status") != "failed":
                    _mark_failed(run_dir, source_id, error)
            except Exception as error:
                _mark_failed(run_dir, source_id, error)
            manifest = load_manifest(run_dir, source_id)
            if manifest is None:
                break
            if (
                manifest.get("status") != "complete"
                and int(manifest.get("attempt", 0)) <= attempt_before
            ):
                manifest["attempt"] = attempt_before + 1
                write_json(manifest_path(run_dir, source_id), manifest)
        if manifest is None or manifest.get("status") not in {"complete", "failed"}:
            raise RuntimeError(f"document job {source_id} did not reach a terminal state")
        results[str(interrupt_id)] = {
            "type": "document_extraction",
            "source_id": source_id,
            "status": manifest["status"],
            "error": str(manifest.get("error", "")),
        }
    return results

"""Run-local document authorization, existing upload reuse and exact-question file reading."""

import asyncio
import json
from pathlib import Path
from openai.types.responses import Response

from ML.deep_research.layer2.backend.fs import atomic_write_text, load_json, now_iso, text_hash, write_json
from ML.deep_research.layer2.backend.publication import ObjectMembers
from .document_files import failure, verify_existing
from .document_records import REGISTRY_PATH, UPLOAD_POLICY, candidate
from .document_uploads import _process
from .research_memory import check_input


class DocumentLimitation(ValueError):
    """A payload-free, application-authored reason a document cannot be consulted."""


def save_provider(root, response, *, phase):
    """Save complete SDK responses and available usage before returning any tool interpretation."""
    root.mkdir(parents=True, exist_ok=True)
    payload = response.model_dump(mode="json")
    write_json(root / "provider_message.json", payload)
    atomic_write_text(root / "response.md", response.output_text)
    write_json(root / "usage.json", {"phase": phase, "response_id": response.id,
                                     "usage": payload.get("usage"), "timestamp": now_iso()})
    if payload.get("status") not in {None, "completed"}:
        raise RuntimeError("Provider did not complete the tool request; response retained")


def recovered_provider(root, *, phase):
    """Recover a completed saved SDK response after interruption, without repeating the request."""
    path = root / "provider_message.json"
    if not path.exists():
        return None
    payload = load_json(path)
    if payload.get("status") != "completed":
        return None
    response = Response.model_construct(**payload)  # Match the SDK's permissive transport decoding.
    text = response.output_text
    target = root / "response.md"
    if target.exists() and target.read_text(encoding="utf-8") != text:
            raise OSError("Saved provider text changed")
    if not target.exists():
        atomic_write_text(target, text)
    if not (root / "usage.json").exists():
        write_json(root / "usage.json", {"phase": phase, "response_id": response.id,
                                         "usage": payload.get("usage"), "recovered_at": now_iso()})
    return response


class ResearchDocuments:
    """One shared registry and async lock for all domain upload/receipt operations in a run."""

    def __init__(self, run, record, client, logger):
        """Load existing receipts without performing uploads or changing frozen preparation."""
        self.run, self.record, self.client, self.logger = run, record, client, logger
        self.lock = asyncio.Lock()
        self.path = run / REGISTRY_PATH
        self.registry = load_json(self.path) if self.path.exists() else {
            "version": 1, "run_identity": text_hash(str(run.resolve()))[:16],
            "policy": dict(UPLOAD_POLICY), "urls": {}, "files": {}, "source_versions": {}}
        self.policy = self.registry["policy"]
        if self.policy != UPLOAD_POLICY:
            raise ValueError("Unsupported research upload policy")
        self.allowed = {}

    def authorize(self, domain, sources):
        """Authorize only trusted starting IDs and this domain's previously discovered receipts."""
        self.allowed[domain] = {dict(item)["file_id"] for item in sources
                                if isinstance(item, ObjectMembers) and dict(item).get("upload_status") == "uploaded"}

    def persist(self):
        """Atomically retain discoveries, intents, receipts and failed alternatives."""
        self.registry["updated_at"] = now_iso()
        write_json(self.path, self.registry)

    async def prepare(self, domain, reference, *, budget=None):
        """Authorize a file ID or safely prepare an alternative URL; never retry failed prepared URLs."""
        async with self.lock:
            if budget:
                budget.require_research()
            url = None
            if reference.startswith("file-"):
                matches = [(digest, entry) for digest, entry in self.registry["files"].items()
                           if entry.get("file_id") == reference]
                known = reference in self.allowed.get(domain, set()) or any(
                    domain in item.get("research_domains", []) and item.get("sha256") in {m[0] for m in matches}
                    for item in self.registry["urls"].values())
                if len(matches) != 1 or not known:
                    raise DocumentLimitation("Document ID is not authorized for this domain")
                digest, entry = matches[0]
            else:
                url, reason = candidate(ObjectMembers([("document", True), ("url", reference)]))
                if not url or reason:
                    raise DocumentLimitation("Invalid public document URL")
                item = self.registry["urls"].setdefault(url, {"status": "pending"})
                prior = self.registry["files"].get(item.get("sha256"), {})
                if ((item.get("status") == "failed" and prior.get("status") not in {"intent", "uncertain"})
                        or prior.get("status") in {"rejected", "unavailable"}):
                    raise DocumentLimitation("This document previously failed; investigate an alternative URL")
                users = item.setdefault("research_domains", [])
                if domain not in users:
                    users.append(domain)
                self.persist()
                try:
                    await _process(url, self.registry, self.client, self.policy, self.logger,
                                   self.persist, set(), False)
                except Exception as error:
                    item.update(status="failed", error=failure(error))
                    self.persist()
                    raise
                digest = item.get("sha256")
                entry = self.registry["files"].get(digest, {})
            if entry.get("status") != "complete" or not entry.get("file_id"):
                raise DocumentLimitation("Document upload is not verified; no file input sent")
            try:
                await verify_existing(self.client, entry)
            except Exception as error:
                entry.update(status="unavailable", error=failure(error))
                self.persist()
                raise
            self.persist()
            if entry["bytes"] > self.record["research"]["file_input_max_bytes"]:
                raise DocumentLimitation("Document exceeds the file-input size allowance")
            extension = Path(entry["filename"]).suffix.lower()
            if extension not in {".pdf", ".txt", ".md", ".csv", ".tsv", ".json", ".docx", ".pptx", ".xlsx"}:
                raise DocumentLimitation("Document format is unsupported for this file-input workflow")
            urls = [u for u, item in self.registry["urls"].items() if item.get("sha256") == digest]
            return digest, entry["file_id"], urls

    async def read(self, domain, reference, questions, evidence, *, budget=None):
        """Ask exact questions with an actual file input; cache completed answers, not file-ID text."""
        if budget:
            budget.require_research()
        digest, file_id, urls = await self.prepare(domain, reference, budget=budget)
        prompt = (self.run / "_internal/inputs/prompts/read_document.md").read_text(encoding="utf-8")
        options = {"model": self.record["model"], "reasoning": {"effort": self.record["research"]["reasoning_effort"]},
                   "store": False, "text": {"verbosity": self.record["web_search"]["verbosity"]}}
        cache_id = text_hash(json.dumps([digest, questions, prompt, options], sort_keys=True))
        cache = evidence / "documents" / cache_id
        # Cache stays domain-private; receipts/uploads are shared across domains.
        if not (cache / "complete.json").exists():
            content = [{"type": "input_text", "text": questions}, {"type": "input_file", "file_id": file_id}]
            request = [{"role": "user", "content": content}]

            def prepare(note, final):
                """Account for document task instructions and the ephemeral call counter."""
                instructions = prompt + ("\n\n" + note if note else "")
                check_input(request, self.record, options={**options, "instructions": instructions})
                write_json(cache / "request.json", {"instructions": instructions, "input": request,
                           "options": options, "document_tokens": "unknown_until_provider_response"})
                return instructions

            async def invoke(instructions):
                """Send the verified file as an actual provider file input."""
                return await self.client.responses.create(instructions=instructions, input=request, **options)

            response = recovered_provider(cache, phase="document_read")
            if response is None:
                response = (await budget.call("document", prepare, invoke) if budget
                            else await invoke(prepare("", False)))
                save_provider(cache, response, phase="document_read")
            write_json(cache / "complete.json", {"sha256": text_hash(response.output_text),
                                                "file_id": file_id, "content_sha256": digest, "urls": urls})
            self.logger.info("document_read_completed domain=%s content_id=%s response_id=%s",
                             domain, digest[:12], cache_id[:12])
        text = (cache / "response.md").read_text(encoding="utf-8")
        if text_hash(text) != load_json(cache / "complete.json")["sha256"]:
            raise OSError("Saved document answer changed")
        return f"Document: {file_id}\nSources: {json.dumps(urls)}\nSaved: /evidence/documents/{cache_id}/response.md\n\n{text}"

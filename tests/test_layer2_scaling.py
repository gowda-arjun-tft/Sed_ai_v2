import asyncio
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ML.deep_research.layer2.backend.evidence import EvidenceStore
from ML.deep_research.layer2.ML.evidence_backend import EvidenceBackend
from ML.deep_research.layer2.backend.fs import load_json, write_json, storage_path
from ML.deep_research.layer2.backend.jobs import iter_jobs
from ML.deep_research.layer2.backend.packing import record_pages
from ML.deep_research.layer2.backend.projections import apply_domains, apply_owners, ingest_facts
from ML.deep_research.layer2.backend.run_log import operational_logger
from ML.deep_research.layer2.backend.stages import plan_domains
from tests.layer2_fixtures import FakeStages, new_run, read_ledger


class ScalingTests(unittest.TestCase):
    def test_long_versioned_windows_paths_save_and_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / ("p" * 170)
            root.mkdir()
            try:
                run = new_run(root)
                fake = FakeStages()
                fake.run(run)
                self.assertEqual(load_json(run / "run.json")["status"], "complete")
                fake.calls.clear()
                fake.run(run)
                self.assertEqual(fake.calls, [])
            finally:
                self.assertEqual(root.resolve().parent, Path(tmp).resolve())
                shutil.rmtree(storage_path(root))

    def test_index_versions_literal_search_and_session_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            store = EvidenceStore(run)
            for i in range(105):
                store.add_text(f"facts/{i // 100:04d}/{i:06d}", f"Exact [a.b] entity {i}\nline two")
            version = store.snapshot()
            backend = EvidenceBackend(run, version=version)
            self.assertEqual(len(backend.ls("/facts/").entries), 2)
            result = backend.grep("[a.b]", "/facts/", max_count=2)
            self.assertTrue(result.truncated)
            self.assertEqual(len(result.matches), 2)
            self.assertEqual(len(backend.grep("[a.b]", "/facts/").matches), 105)
            self.assertFalse(backend.grep("a.*b", "/facts/").matches)
            found = backend.grep("entity 104", "/facts/0001/").matches[0]
            self.assertIn("entity 104", backend.read(found["path"], offset=0, limit=1).file_data["content"])
            self.assertEqual(backend.read(found["path"], offset=1, limit=1).file_data["content"], "line two")
            for path in ["/../.env", "C:/secret", "/secrets/.env", "/other-run/source"]:
                self.assertTrue(backend.read(path).error)
            store.add_text("facts/0001/000104", "Updated entity")
            changed = store.snapshot()
            self.assertNotEqual(version, changed)
            self.assertTrue(backend.grep("entity 104", "/facts/").matches)
            self.assertFalse(EvidenceBackend(run, version=changed).grep("entity 104", "/facts/").matches)
            with store.connect() as db:
                blobs = db.execute("SELECT count(*) FROM blobs").fetchone()[0]
            for i in range(20):
                EvidenceBackend(run, version=version, thread=f"thread-{i}").read(found["path"])
            with store.connect() as db:
                self.assertEqual(db.execute("SELECT count(*) FROM blobs").fetchone()[0], blobs)

    def test_large_values_are_linked_fragments_not_truncated_or_output_retried(self):
        original = {"fact": {"fact_id": "f1", "body": "αβ😀 " * 1000}, "initial_assignment": {"domain_ids": []}}
        pages = list(record_pages([original], budget=300))
        self.assertGreater(len(pages), 10)
        self.assertEqual({p[0]["parent_record_id"] for p in pages}, {"f1"})
        self.assertEqual(json.loads("".join(p[0]["record_fragment"] for p in pages)), original)
        domain = {"domain_id": "d0001", "definition": "duty " * 1000}
        self.assertEqual({p[0]["domain_id"] for p in record_pages([domain], 300)}, {"d0001"})

    def test_completed_objects_survive_deleted_or_damaged_rebuildable_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeStages()
            fake.run(run)
            before = read_ledger(run / "_internal/facts.jsonl")
            path = run / "_internal/trace/evidence.sqlite3"
            path.unlink()
            fake.calls.clear()
            fake.run(run)
            self.assertEqual(fake.calls, [])
            self.assertEqual(read_ledger(run / "_internal/facts.jsonl"), before)
            path.write_bytes(b"INTERRUPTED_INDEX")
            fake.run(run)
            self.assertEqual(fake.calls, [])
            self.assertTrue(list(path.parent.glob("evidence.sqlite3.damaged-*")))

    def test_bounded_native_batches_never_load_entire_job_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            record = load_json(run / "run.json")
            record["chunking"]["max_concurrency"] = 2
            write_json(run / "run.json", record)
            seen = []

            def payloads():
                for i in range(17):
                    seen.append(i)
                    yield {"number": i}

            async def batch(run, stage, payloads, version, saver, logger, **kwargs):
                self.assertLessEqual(len(payloads), 4)
                self.assertEqual(len(seen), kwargs["offset"] + len(payloads))
                return [{"value": p} for p in payloads]

            async def scenario():
                return [r async for r in iter_jobs(run, "understanding", payloads(), "manifest-only", None, None)]

            with patch("ML.deep_research.layer2.backend.jobs.run_jobs", side_effect=batch):
                result = asyncio.run(scenario())
            self.assertEqual([r["value"]["number"] for r in result], list(range(17)))

    def test_finite_planning_visits_every_subject_and_definition_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EvidenceStore(new_run(Path(tmp)))
            initial = {"job": "seed", "response_path": "raw.json", "value": {"domains": [
                {"name": "First", "responsibilities": ["Retain this duty"]}, {"name": "Second"}]}}
            apply_domains(store, initial)
            seen = []

            async def batch(run, stage, payloads, version, saver, logger, **kwargs):
                replies = []
                for p in payloads:
                    seen.append(p)
                    if p["mode"] == "compare":
                        value = {"comparisons": [{"record_id": p["subject"][0]["evidence_id"], "domain_id": p["domain_definitions"][0]["domain_id"]}]}
                    else:
                        value = {"domains": [{"domain_id": "d0001", "name": "Updated"}]}
                    replies.append({"job": f"fake/{len(seen)}", "value": value,
                                    "payload": p, "response_path": "raw.json"})
                return replies

            definitions = [[d] for d in store.rows("domains")]
            with patch("ML.deep_research.layer2.backend.stages.complete_definitions", return_value=None), patch(
                "ML.deep_research.layer2.backend.stages.definition_pages", side_effect=lambda *a, **kw: iter(definitions),
            ), patch("ML.deep_research.layer2.backend.stages.page_budget", return_value=500), patch(
                "ML.deep_research.layer2.backend.jobs.run_jobs", side_effect=batch,
            ), patch("ML.deep_research.layer2.backend.stages.run_jobs", side_effect=batch):
                asyncio.run(plan_domains(store, "design", (
                    {"evidence_id": str(i), "value": "entity " * 200} for i in range(3)
                ), {"domain_plugin": "baseline", "requirements": "Keep facts"}, None, None))
            compared = [(p["subject"][0]["evidence_id"], p["domain_definitions"][0]["domain_id"])
                        for p in seen if p["mode"] == "compare"]
            self.assertEqual(compared, [(str(i), d) for i in range(3) for d in ["d0001", "d0002"]])
            for payload in seen:
                self.assertNotIn("evidence_files", payload)
                self.assertTrue(payload["domain_definitions"])
                if payload["mode"] == "reconcile":
                    ids = {d["domain_id"] for d in payload["domain_definitions"]}
                    for comparison in payload["comparisons"]:
                        self.assertTrue(all(c["domain_id"] in ids for c in comparison["comparisons"]))
            self.assertEqual(store.get("domains", "d0001")["definition"]["responsibilities"], ["Retain this duty"])

    def test_oversized_roster_extracts_once_and_audits_missing_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeStages()
            from ML.deep_research.layer2.backend.stages import complete_definitions

            def scoped(store, stage, payload):
                if stage in {"distribution", "observations", "assignments"}:
                    return None
                return complete_definitions(store, stage, payload)

            def pages(store, **kwargs):
                return ([d] for d in store.rows("domains"))

            with patch("ML.deep_research.layer2.backend.stages.complete_definitions", side_effect=scoped), patch(
                "ML.deep_research.layer2.backend.stages.definition_pages", side_effect=pages,
            ):
                fake.run(run)
            distribution = [p for s, p, _ in fake.calls if s == "distribution"]
            self.assertEqual(sum("source" in p for p in distribution), 1)
            self.assertEqual(sum(p["mode"] == "ownership" for p in distribution), 2)
            for stage, count in [("observations", 2), ("assignments", 3)]:
                self.assertEqual(sum(s == stage for s, *_ in fake.calls), count)
            facts = read_ledger(run / "_internal/facts.jsonl")
            self.assertEqual(len(facts), 2)
            store = EvidenceStore(run)
            response = {"value": {"assignments": []}, "job": "missing", "fingerprint": "f",
                        "response_path": "raw.json", "payload": {"facts": facts, "domain_page": 9}}
            apply_owners(store, response)
            self.assertTrue(any(a["kind"] == "unresolved_comparison" for a in store.rows("audit")))
            self.assertEqual(load_json(run / "run.json")["status"], "complete")


if __name__ == "__main__":
    unittest.main()

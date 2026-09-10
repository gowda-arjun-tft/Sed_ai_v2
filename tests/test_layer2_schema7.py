import asyncio
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from ML.deep_research.layer2.backend.evidence import EvidenceStore
from ML.deep_research.layer2.backend.evidence_text import evidence_pages, evidence_text, message_text
from ML.deep_research.layer2.backend.fs import load_json
from ML.deep_research.layer2.backend.ownership import (
    apply_corrections, apply_owners, commit_replacements, expect_replacements, owners, set_owners,
)
from ML.deep_research.layer2.backend.packing import input_tokens
from ML.deep_research.layer2.backend.projections import apply_domains, ingest_facts, load_ledger, save_ledger
from ML.deep_research.layer2.backend.stages import assign, ownership_payloads
from ML.deep_research.layer2.backend.windows import source_windows
from ML.deep_research.layer2.ML.agent import Layer2Response
from ML.deep_research.layer2.ML.context import estimate
from tests.layer2_fixtures import FakeStages, new_run, read_ledger


class ExtractOnceTests(unittest.TestCase):
    def setUp(self):
        self.network = [patch.object(kind, "send", side_effect=AssertionError("network forbidden"))
                        for kind in (httpx.Client, httpx.AsyncClient)]
        for guard in self.network:
            guard.start()
            self.addCleanup(guard.stop)

    def seed(self, root):
        store = EvidenceStore(new_run(root))
        response = {"job": "understanding/000001", "fingerprint": "a" * 64, "response_path": "raw.json",
                    "payload": {"source": {"source_id": "s000001", "start_byte": 0}},
                    "value": {"profile": "Navigation", "evidence": [
                        {"fact": "Historic A: 17 m²; proposed B: 19 m². 原文 "
                                 "Operator pays for repairs except supplier manufacturing defects.", "source": ["91cb80fc"],
                         "relationships": ["B depends on A"], "contradictions": ["Area remains disputed"]},
                        {"fact": "Same text"}, {"fact": "Same text"}, None]}}
        ingest_facts(store, response)
        apply_domains(store, {"job": "seed", "response_path": "domains.json", "value": {"domains": [
            {"name": "A", "responsibilities": ["A"]}, {"name": "B", "responsibilities": ["B"]}]}})
        for fact in store.rows("facts"):
            set_owners(store, fact["fact_id"], ["d0001"], initial=True)
            set_owners(store, fact["fact_id"], ["d0001"])
        return store, response, list(store.rows("facts"))

    def test_stable_ids_content_versions_and_active_source_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, response, facts = self.seed(Path(tmp))
            self.assertEqual(len({f["fact_id"] for f in facts}), 4)
            self.assertEqual([f["body"] for f in facts], response["value"]["evidence"])
            save_ledger(store)
            before = (store.run / "_internal/facts.jsonl").read_bytes()
            load_ledger(store)
            ingest_facts(store, response)
            save_ledger(store)
            self.assertEqual(before, (store.run / "_internal/facts.jsonl").read_bytes())
            changed = copy.deepcopy(response)
            changed["value"]["evidence"][0]["fact"] += " Clarification"
            store.clear("facts")
            ingest_facts(store, changed)
            newest = list(store.rows("facts"))
            self.assertTrue({f["fact_id"] for f in facts}.isdisjoint(f["fact_id"] for f in newest))
            save_ledger(store)
            self.assertEqual(read_ledger(store.run / "_internal/facts.jsonl")[:4], facts)
            self.assertEqual([f["body"] for f in newest], changed["value"]["evidence"])
            store.clear("facts")
            ingest_facts(store, changed)
            ingest_facts(store, response)
            self.assertEqual([f["fact_id"] for f in store.rows("facts")],
                             [f["fact_id"] for f in newest + facts])

    def test_compact_input_is_exact_paged_text_not_an_escaped_json_dump(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, response, facts = self.seed(Path(tmp))
            facts[0]["body"]["fact"] *= 400
            original = copy.deepcopy(facts)
            pages = list(evidence_pages(facts, 500))
            matching = [r for page in pages for r in page if r["fact_id"] == facts[0]["fact_id"]]
            self.assertGreater(len(matching), 1)
            self.assertEqual("".join(r["text"] for r in matching), evidence_text(facts[0]))
            self.assertEqual({r["parent_record_id"] for r in matching}, {facts[0]["fact_id"]})
            for page in pages:
                payload = {"subject": page, "domain_plugin": "Plugin", "requirements": "Priorities"}
                text = message_text(payload)
                self.assertNotIn("91cb80fc", text)
                self.assertNotIn("start_byte", text)
                for row in page:
                    self.assertIn(row["text"], text)
                prompt = (store.run / "_internal/inputs/prompts/design.md").read_text(encoding="utf-8")
                expected = estimate([{"role": "user", "content": text}], prompt, (),
                                    Layer2Response.model_json_schema(), 8000)
                self.assertEqual(input_tokens(store.run, "design", payload), expected)
                self.assertLess(expected, 300_000)
            self.assertEqual(facts, original)
            simple = {"fact_id": "f1", "body": {"fact": "Exact\nUnicode 原文", "relationships": [], "source": []}}
            compact = message_text({"facts": list(evidence_pages([simple], 1000))[0]})
            self.assertIn("Exact\nUnicode 原文", compact)
            self.assertNotIn("Relationships:", compact)

    def test_corrections_can_move_remove_and_preserve_on_conflict(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, _, facts = self.seed(Path(tmp))
            identity = facts[0]["fact_id"]
            response = {"job": "observations/1", "fingerprint": "b", "response_path": "review.json",
                        "payload": {"facts": facts}, "value": {"corrections": [
                            {"fact_id": identity, "add_domain_ids": ["d0002"], "remove_domain_ids": ["d0001"]}]}}
            apply_corrections(store, response)
            self.assertEqual(owners(store, identity), ["d0002"])
            apply_corrections(store, response)
            self.assertEqual(owners(store, identity), ["d0002"])
            self.assertEqual(owners(store, facts[1]["fact_id"]), ["d0001"])
            response["value"]["corrections"] = [{"fact_id": identity, "add_domain_ids": ["d0001", "unknown"]}]
            apply_corrections(store, response)
            self.assertEqual(set(owners(store, identity)), {"d0001", "d0002"})
            self.assertEqual(store.get("facts", identity)["body"], facts[0]["body"])
            self.assertTrue({"conflicting_corrections", "unknown_correction_domain"}.issubset(
                {a["kind"] for a in store.rows("audit")}))

    def test_scoped_updates_do_not_clear_others_or_mistake_missing_rows_for_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, _, facts = self.seed(Path(tmp))
            identities = [f["fact_id"] for f in facts]
            for identity in identities:
                set_owners(store, identity, ["d0001", "d0002"])
            payload = {"facts": facts, "final_domain_ids": ["d0002"], "fact_page": 1, "domain_page": 1}
            expect_replacements(store, payload)
            response = {"job": "assignments/1", "fingerprint": "c", "response_path": "update.json",
                        "payload": payload, "value": {"assignments": [
                            {"fact_id": identities[0], "domain_ids": []},
                            {"fact_id": identities[2], "domain_ids": ["d0002"]},
                            {"fact_id": identities[2], "domain_ids": []}]}}
            apply_owners(store, response)
            commit_replacements(store)
            self.assertEqual(owners(store, identities[0]), ["d0001"])
            for identity in identities[1:]:
                self.assertEqual(owners(store, identity), ["d0001", "d0002"])
            self.assertTrue(any(a["kind"] == "incomplete_or_conflicting_scope" for a in store.rows("audit")))

    def test_new_scope_keeps_positive_partial_results_and_audits_unfinished_comparisons(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, _, facts = self.seed(Path(tmp))
            payload = {"facts": [facts[0]], "final_domain_ids": ["d0002"], "fact_page": 1}
            expect_replacements(store, payload)
            expect_replacements(store, {**payload, "fact_page": 2})
            apply_owners(store, {"job": "assignments/1", "fingerprint": "c", "response_path": "update.json",
                "payload": payload, "value": {"assignments": [{"fact_id": facts[0]["fact_id"], "domain_ids": ["d0002"]}]}})
            commit_replacements(store)
            self.assertEqual(owners(store, facts[0]["fact_id"]), ["d0001", "d0002"])
            self.assertTrue(any(a["kind"] == "incomplete_or_conflicting_scope" for a in store.rows("audit")))

    def test_source_extracted_once_late_domain_gets_earlier_facts_and_ids_stay_internal(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("ML.deep_research.layer2.backend.create_run.source_windows",
                       side_effect=lambda text, **kw: source_windows(text, 12, 2, **kw)):
                run = new_run(Path(tmp), text=" property" * 35)
            fake = FakeStages()
            fake.run(run)
            manifest = load_json(run / "_internal/trace/source/manifest.json")
            self.assertEqual(sum(s == "understanding" for s, *_ in fake.calls), len(manifest))
            self.assertTrue(all("source" not in p for s, p, _ in fake.calls if s != "understanding"))
            facts = read_ledger(run / "_internal/facts.jsonl")
            for stage in ("design", "distribution", "observations", "assignments"):
                messages = "\n".join(m for s, m in fake.messages if s == stage)
                for fact in facts:
                    self.assertIn(fact["fact_id"], messages)
            final = load_json(run / "_internal/domains.json")["final"]
            self.assertEqual(final[-1]["fact_ids"], [f["fact_id"] for f in facts])
            self.assertTrue(all("body" not in d for d in final))
            markdown = "\n".join(p.read_text(encoding="utf-8") for p in (run / "domains").glob("*.md"))
            self.assertTrue(all(f["fact_id"] not in markdown for f in facts))
            self.assertIn("## Supplied facts", markdown)
            fake.calls.clear()
            fake.run(run)
            self.assertEqual(fake.calls, [])

    def test_empty_review_skips_later_calls_and_failure_preserves_initial_owners(self):
        for failed in (False, True):
            with self.subTest(failed=failed), tempfile.TemporaryDirectory() as tmp:
                run, fake = new_run(Path(tmp)), FakeStages()
                original = fake.factory

                def factory(path, stage, saver=None):
                    graph = original(path, stage, saver)
                    if stage == "observations":
                        invoke = graph.afunc

                        async def empty(value, config):
                            await invoke(value, config)
                            return {"structured_response": {"observations": [], "corrections": [], "issues": []}}

                        graph.afunc = empty
                    return graph

                if failed:
                    fake.fail.add("observations")
                with patch.object(fake, "factory", side_effect=factory):
                    fake.run(run)
                record = load_json(run / "run.json")
                self.assertEqual(record["status"], "partial" if failed else "complete")
                self.assertEqual([s for s, *_ in fake.calls], ["understanding", "design", "distribution", "observations"])
                mapping = load_json(run / "_internal/assignments.json")
                self.assertEqual(mapping["final"][0]["domain_ids"], ["d0001"])
                if failed:
                    self.assertIn("operational_failure", (run / "unresolved.md").read_text())

    def test_only_changed_responsibilities_schedule_all_fact_updates_not_a_rename(self):
        with tempfile.TemporaryDirectory() as tmp:
            store, _, facts = self.seed(Path(tmp))
            for domain in store.rows("domains"):
                store.put("initial_domains", domain["domain_id"], domain)
            response = {"job": "change", "response_path": "change.json", "value": {"domains": [
                {"domain_id": "d0001", "name": "Renamed A"}]}}
            apply_domains(store, response)
            received = []

            async def replies(run, stage, payloads, *args):
                for payload in payloads:
                    received.append(payload)
                    yield {"job": "assignments/1", "fingerprint": "changed", "response_path": "scope.json",
                           "payload": payload, "value": {"assignments": [
                               {"fact_id": row["fact_id"], "domain_ids": ["d0002"]} for row in payload["facts"]]}}

            with patch("ML.deep_research.layer2.backend.stages.iter_jobs", side_effect=replies):
                store.put("observations", "p1", {"proposal_id": "p1", "body": "Unresolved", "response_path": "raw.json"})
                with patch.object(store, "add_records", side_effect=AssertionError("idle indexing")), patch.object(
                    store, "snapshot", side_effect=AssertionError("idle snapshot"),
                ):
                    asyncio.run(assign(store, None, None))
                self.assertEqual(received, [])
                self.assertTrue(any(a["kind"] == "unresolved_proposal" for a in store.rows("audit")))
                response["value"] = {"domains": [{"domain_id": "d0002", "responsibilities": ["B", "New duty"]}]}
                apply_domains(store, response)
                asyncio.run(assign(store, None, None))
            self.assertTrue(all(p["final_domain_ids"] == ["d0002"] for p in received))
            self.assertEqual([r["fact_id"] for p in received for r in p["facts"]], [f["fact_id"] for f in facts])
            for fact in facts:
                self.assertEqual(owners(store, fact["fact_id"]), ["d0001", "d0002"])

    def test_interrupted_review_retains_completed_patch_and_resumes_only_failed_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            run, fake = new_run(Path(tmp)), FakeStages()
            original, fail = fake.factory, [True]

            def pages(store, stage, records, *args, **kwargs):
                for payload in ownership_payloads(store, stage, records, *args, **kwargs):
                    if stage != "observations":
                        yield payload
                    else:
                        for i, row in enumerate(payload["facts"], 1):
                            yield {**payload, "facts": [row], "fact_page": i}

            def factory(path, stage, saver=None):
                graph = original(path, stage, saver)
                if stage == "observations":
                    invoke = graph.afunc

                    async def correction(value, config):
                        await invoke(value, config)
                        payload = fake.calls[-1][1]
                        if payload["fact_page"] == 2 and fail[0]:
                            raise ConnectionError("offline interruption")
                        rows = [{"fact_id": payload["facts"][0]["fact_id"], "add_domain_ids": ["d0002"],
                                 "remove_domain_ids": ["d0001"]}] if payload["fact_page"] == 1 else []
                        return {"structured_response": {"observations": [], "corrections": rows, "issues": []}}

                    graph.afunc = correction
                return graph

            with patch("ML.deep_research.layer2.backend.stages.ownership_payloads", side_effect=pages), patch.object(
                fake, "factory", side_effect=factory,
            ):
                fake.run(run)
                before = load_json(run / "run.json")
                self.assertEqual(before["status"], "partial")
                self.assertEqual(load_json(run / "_internal/assignments.json")["final"][0]["domain_ids"], ["d0002"])
                fail[0], fake.calls = False, []
                fake.run(run)
            after = load_json(run / "run.json")
            self.assertEqual(after["status"], "complete")
            self.assertEqual([(s, p["fact_page"]) for s, p, _ in fake.calls], [("observations", 2)])
            self.assertEqual(before["jobs"]["observations/000002"]["thread_id"],
                             after["jobs"]["observations/000002"]["thread_id"])
            self.assertEqual(load_json(run / "_internal/assignments.json")["final"][0]["domain_ids"], ["d0002"])

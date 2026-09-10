import json
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ML.deep_research.layer2.backend.fs import load_json, write_json
from ML.deep_research.layer2.backend.publication import domain_names, readable
from ML.deep_research.layer2.backend.publish import publish, write_domain
from ML.deep_research.layer2.backend.evidence import EvidenceStore
from ML.deep_research.layer2.backend.projections import ingest_facts, save_ledger, apply_domains
from ML.deep_research.layer2.backend.ownership import apply_owners, expect_replacements, commit_replacements
from tests.layer2_fixtures import read_ledger
from tests.layer2_fixtures import FakeStages, new_run, published


class PublicationTests(unittest.TestCase):
    def render_domain(self, definition, facts):
        """Exercise the production streaming publisher using disposable immutable records."""
        with tempfile.TemporaryDirectory() as tmp:
            store = EvidenceStore(Path(tmp))
            for i, fact in enumerate(facts):
                identity = f"f{i}"
                store.put("ledger", identity, {**fact, "fact_id": identity})
                store.put("facts", identity, fact)
                with store.connect() as db:
                    db.execute("INSERT INTO owners VALUES(?,?)", (identity, "d0001"))
            path = Path(tmp) / "domain.md"
            write_domain(store, path, {"domain_id": "d0001", "definition": definition})
            return path.read_text(encoding="utf-8")

    def test_unconventional_domains_do_not_hide_usable_dispositions(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = EvidenceStore(new_run(Path(tmp)))
            store.put("observations", "p1", {"proposal_id": "p1", "body": "Keep this issue"})
            disposition = {"proposal_id": "p1", "disposition": "unresolved", "reason": "Evidence insufficient"}
            apply_domains(store, {"job": "catalogue/1", "response_path": "raw.json",
                                  "value": {"domains": "Unconventional but preserved", "dispositions": [disposition]}})
            self.assertEqual(store.get("dispositions", "p1"), disposition)
            self.assertTrue(any(a.get("value", {}).get("domains") == "Unconventional but preserved"
                                for a in store.rows("audit")))

    def test_root_layout_raw_preservation_and_rebuild_without_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeStages()
            fake.run(run)
            self.assertEqual({p.name for p in run.iterdir()}, {
                "README.md", "domain_plan.md", "domains", "run.json", "run.log", "_internal"})
            self.assertTrue((run / "_internal/trace/checkpoints.sqlite3").exists())
            facts = read_ledger(run / "_internal/facts.jsonl")
            raw = load_json(run / facts[0]["response_path"])
            self.assertEqual([r["body"] for r in facts], raw["evidence"])
            self.assertFalse((run / "facts").exists())
            self.assertFalse(list(run.glob("domains/**/*.json")))
            report = run / "domains/additional-use.md"
            expected = report.read_bytes()
            report.unlink()
            fake.calls.clear()
            fake.run(run)
            self.assertEqual(fake.calls, [])
            self.assertEqual(report.read_bytes(), expected)
            self.assertEqual(read_ledger(run / "_internal/facts.jsonl"), facts)
            self.assertIn("## Research responsibilities", expected.decode())
            for metadata in ("Source window", "Record:", "Saved response", "### Fact", "Ownership note"):
                self.assertNotIn(metadata, expected.decode())

    def test_ledger_retains_generations_and_rejects_conflict_without_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            row = {"job": "understanding/000001", "fingerprint": "a" * 64,
                   "payload": {"source": {"source_id": "s1", "start_byte": 0}},
                   "value": {"evidence": [{"fact": "ä\n原文", "unknown": [None, False, 3]}]}}
            store = EvidenceStore(run)
            row["response_path"] = "raw.json"
            ingest_facts(store, row)
            save_ledger(store)
            original = list(store.rows("facts"))
            before = (run / "_internal/facts.jsonl").read_bytes()
            ingest_facts(store, row)
            save_ledger(store)
            self.assertEqual((run / "_internal/facts.jsonl").read_bytes(), before)
            with patch("ML.deep_research.layer2.backend.projections.atomic_text", side_effect=OSError):
                with self.assertRaises(OSError):
                    ingest_facts(store, {**row, "job": "understanding/000002"})
                    save_ledger(store)
            self.assertEqual((run / "_internal/facts.jsonl").read_bytes(), before)
            ingest_facts(store, {**row, "job": "understanding/000002"})
            save_ledger(store)
            ledger = read_ledger(run / "_internal/facts.jsonl")
            self.assertEqual(ledger[0], original[0])
            self.assertEqual(len(ledger), 2)
            before = (run / "_internal/facts.jsonl").read_bytes()
            # Same saved content identity cannot overwrite a conflicting ledger body.
            store.put("ledger", original[0]["fact_id"], {**original[0], "body": "corrupt"})
            with self.assertRaisesRegex(OSError, "immutable"):
                ingest_facts(store, row)
            self.assertEqual((run / "_internal/facts.jsonl").read_bytes(), before)

    def test_unknown_values_and_references_are_fully_visible_without_repair(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeStages()
            fake.run(run)
            record = load_json(run / "run.json")
            # Modify saved fake responses, not real research. Valid objects remain reusable.
            for stage in ("understanding", "design", "distribution", "observations", "catalogue", "assignments"):
                path = run / record["jobs"][stage + "/000001"]["response_path"]
                value = load_json(path)
                value["unexpected"] = {"marker": stage + "-EXTRA", "nested": [False, None, []]}
                write_json(path, value)
            # Changed upstream objects cause legitimate dependent fingerprints; return
            # extras in fresh fake jobs too, not a content retry on the changed object.
            from ML.deep_research.layer2.ML.agent import Layer2Response
            factory = fake.factory

            def with_extras(run, stage, saver=None):
                graph = factory(run, stage, saver)
                invoke = graph.afunc

                async def wrapped(value, config):
                    result = await invoke(value, config)
                    body = result["structured_response"].root
                    body["unexpected"] = {"marker": stage + "-EXTRA", "nested": [False, None, []]}
                    result["structured_response"] = Layer2Response(root=body)
                    return result

                graph.afunc = wrapped
                return graph

            with patch.object(fake, "factory", side_effect=with_extras):
                fake.run(run)
            report = (run / "unresolved.md").read_text(encoding="utf-8")
            for stage in ("understanding", "design", "distribution", "observations", "catalogue", "assignments"):
                self.assertIn(stage + "-EXTRA", report)
            self.assertIn("[Preserved response]", report)
            self.assertIn("false", report)
            self.assertEqual(load_json(run / "run.json")["status"], "complete")
            fake.calls.clear()
            fake.run(run)
            self.assertEqual(fake.calls, [])

    def test_multidomain_publication_and_unresolved_reasons(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeStages()
            fake.run(run)
            domains = load_json(run / "_internal/domains.json")["final"]
            facts = read_ledger(run / "_internal/facts.jsonl")
            response = {"job": "assignments/000001", "fingerprint": "c" * 64,
                        "value": {"assignments": [
                            {"fact_id": facts[0]["fact_id"], "domain_ids": ["d0001", "d0002"],
                             "reason": "Two relevant owners", "extra": {"keep": "nested"}},
                            {"fact_id": facts[1]["fact_id"], "domain_ids": [], "reason": "OWNER_UNKNOWN"},
                            {"fact_id": "unknown", "domain_ids": ["d0001"], "reason": "KEEP_UNKNOWN"},
                            {"fact_id": facts[0]["fact_id"], "domain_ids": ["../../outside"], "why": 9}]}}
            store = EvidenceStore(run)
            store.clear("final_owners", "decisions", "replacement_votes")
            with store.connect() as db:
                db.execute("DELETE FROM owners")
            response["response_path"] = "raw.json"
            response["payload"] = {"facts": facts, "final_domain_ids": ["d0001", "d0002"]}
            expect_replacements(store, response["payload"])
            apply_owners(store, response)
            commit_replacements(store)
            counts = publish(store)
            self.assertEqual(counts["unresolved_facts"], 1)
            for name in ("operations", "ownership"):
                text = (run / f"domains/{name}.md").read_text(encoding="utf-8")
                self.assertIn("17.5 m²", text)
                self.assertNotIn("Two relevant owners", text)
            self.assertEqual(load_json(run / "_internal/assignments.json")["decisions"],
                             response["value"]["assignments"])
            audit = (run / "unresolved.md").read_text(encoding="utf-8")
            for value in ("OWNER_UNKNOWN", "KEEP_UNKNOWN", "nested", "../../outside"):
                self.assertIn(value, audit)

    def test_publication_failure_preserves_previous_commit_and_user_view(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeStages()
            fake.run(run)
            old = published(run)
            original = (run / "domains/additional-use.md").read_bytes()
            (run / "domains/additional-use.md").write_bytes(b"USER_EDIT\r\n")
            fake.calls.clear()
            with patch("ML.deep_research.layer2.backend.publish.atomic_text", side_effect=OSError):
                with self.assertRaises(OSError):
                    fake.run(run)
            self.assertEqual(published(run), old)
            self.assertEqual((old / "domains/additional-use.md").read_bytes(), original)
            self.assertEqual((run / "domains/additional-use.md").read_bytes(), b"USER_EDIT\r\n")
            fake.run(run)
            self.assertEqual(fake.calls, [])
            self.assertEqual((run / "domains/additional-use.md").read_bytes(), original)
            archives = list((run / "_internal/trace/presentation_history").rglob("additional-use.md"))
            self.assertTrue(any(p.read_bytes() == b"USER_EDIT\r\n" for p in archives))

    def test_filenames_and_unconventional_rendering(self):
        definitions = [{"domain_id": f"d{i:04d}", "definition": {"name": name}}
                       for i, name in enumerate(["CON", "Same", "same", "same-d0003", "../.env", "漢字"], 1)]
        names = list(domain_names(definitions).values())
        self.assertEqual(len(set(n.casefold() for n in names)), len(names))
        self.assertNotIn("domains/con.md", names)
        self.assertTrue(all(Path(n).parts[0] == "domains" and len(Path(n).parts) == 2 for n in names))
        text = readable({"other": [{"fact": "KEEP\nEXACT", "value": False}, None, 5], "empty": {}})
        for value in ("KEEP", "EXACT", "false", "null", "5", "{}"):
            self.assertIn(value, text)

    def test_research_projection_groups_without_rewriting_or_mutating_records(self):
        definition = {"name": "Energy", "responsibilities": ["Research supply; preserve exclusions."],
                      "domain_id": "d1234", "reason": "PRIVATE_REASON", "evidence_refs": ["PRIVATE_REF"]}
        bodies = [
            {"section": "Supply", "fact": "2021 certificate: 17.5 m²; §71a GEG. source ID is a meter label. Proposed, not installed.",
             "means": "Capacity unknown—not a breach.", "applicability": "Proposed, not installed",
             "source": "PRIVATE_SOURCE", "additional": {"source": "Nested substantive source", "unit": "kWh"}},
            {"section": "Areas", "fact": "6,047 m²", "means": ""},
            {"section": "Supply", "fact": "Contradictory: electricity vs gas", "means": ""},
            {"section": "Areas", "fact": "7,704.08 m²", "means": ""},
            {"section": {"unusual": [False, None]}, "fact": "ä 原文\nsecond line", "quantity": 0},
            {}, [], None, False,
            {"section": "", "means": 0, "applicability": False},
        ]
        facts = [{"body": body, "source": {"input_bom_bytes": 3, "start_byte": 42},
                  "fact_id": "PRIVATE_ID", "response_path": "PRIVATE_PATH"} for body in bodies]
        original = copy.deepcopy((definition, facts))
        text = self.render_domain(definition, facts)
        self.assertEqual((definition, facts), original)
        for marker in ("d1234", "PRIVATE_", "input bom", "start byte", "### Fact"):
            self.assertNotIn(marker, text)
        for marker in ("17.5 m²", "§71a GEG", "source ID is a meter label",
                       "Proposed, not installed", "Nested substantive source", "kWh", "6,047 m²", "7,704.08 m²",
                       "ä 原文\n  second line", "false", "null", "{}", "[]", "**quantity:** 0"):
            self.assertIn(marker, text)
        for heading in ("Supply", "Areas", "Supplied facts"):
            self.assertEqual(text.count("## " + heading), 1)
        self.assertLess(text.index("Contradictory:"), text.index("## Areas"))
        self.assertLess(text.index("6,047"), text.index("7,704.08"))
        self.assertNotIn("**means:**", text)
        self.assertNotIn("**applicability:**", text)
        self.assertNotIn("Capacity unknown—not a breach.", text)
        self.assertIn("No recorded facts assigned", self.render_domain(definition, []))
        self.assertIn("null", self.render_domain({"responsibilities": None}, []))

    def test_streaming_view_hides_only_exact_top_level_fields(self):
        body = {"section": "Supply", "fact": "Proposed: applicability means unconfirmed—not installed.",
                "means": "OMIT_MEANING", "applicability": "OMIT_STATUS", "source": "OMIT_SOURCE",
                "extra": {"means": "KEEP_NESTED", "applicability": "KEEP_NESTED_STATUS"}}
        original = copy.deepcopy(body)
        domain = {"domain_id": "d0001", "definition": {"name": "Energy", "responsibilities": ["Check supply."]}}
        with tempfile.TemporaryDirectory() as tmp:
            store = EvidenceStore(Path(tmp))
            fact = {"fact_id": "f1", "body": body}
            store.put("ledger", "f1", fact)
            store.put("facts", "f1", fact)
            with store.connect() as db:
                db.execute("INSERT INTO owners VALUES('f1','d0001')")
            path = Path(tmp) / "energy.md"
            write_domain(store, path, domain)
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("OMIT_", text)
            self.assertIn(body["fact"], text)
            self.assertIn("KEEP_NESTED", text)
            self.assertIn("KEEP_NESTED_STATUS", text)
            self.assertEqual(store.get("ledger", "f1")["body"], original)
            self.assertEqual(body, original)


if __name__ == "__main__":
    unittest.main()

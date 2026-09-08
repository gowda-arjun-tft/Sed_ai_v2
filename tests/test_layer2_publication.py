import json
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ML.deep_research.layer2.backend.fs import load_json, write_json
from ML.deep_research.layer2.backend.publication import domain_markdown, domain_names, publish, readable
from ML.deep_research.layer2.backend.records import extract_records, read_ledger
from tests.layer2_fixtures import FakeStages, new_run, published


class PublicationTests(unittest.TestCase):
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
            self.assertEqual([r["body"] for r in facts], [r["body"] for r in raw["facts"]])
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
            row = {"job": "distribution/000001", "fingerprint": "a" * 64,
                   "payload": {"source": {"source_id": "s1", "start_byte": 0}},
                   "value": {"facts": [{"body": {"fact": "ä\n原文", "unknown": [None, False, 3]},
                                         "domain_ids": []}]}}
            original, _, _ = extract_records(run, [row])
            before = (run / "_internal/facts.jsonl").read_bytes()
            extract_records(run, [row])
            self.assertEqual((run / "_internal/facts.jsonl").read_bytes(), before)
            with patch("ML.deep_research.layer2.backend.records.atomic_write_text", side_effect=OSError):
                with self.assertRaises(OSError):
                    extract_records(run, [{**row, "fingerprint": "b" * 64}])
            self.assertEqual((run / "_internal/facts.jsonl").read_bytes(), before)
            extract_records(run, [{**row, "fingerprint": "b" * 64}])
            ledger = read_ledger(run / "_internal/facts.jsonl")
            self.assertEqual(ledger[0], original[0])
            self.assertEqual(len(ledger), 2)
            before = (run / "_internal/facts.jsonl").read_bytes()
            row["value"]["facts"][0]["body"] = "changed"
            with self.assertRaisesRegex(OSError, "immutable"):
                extract_records(run, [row])
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
            counts = publish(run, domains, facts, [response], [])
            self.assertEqual(counts["unresolved_facts"], 1)
            for name in ("operations", "ownership"):
                text = (run / f"domains/{name}.md").read_text(encoding="utf-8")
                self.assertIn("17.5 m²", text)
                self.assertNotIn("Two relevant owners", text)
            self.assertEqual(load_json(run / "_internal/assignments.json")["final"],
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
            with patch("ML.deep_research.layer2.backend.publication.atomic_write_text", side_effect=OSError):
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
            {"section": "Supply", "fact": "2021 certificate: 17.5 m²; §71a GEG. source ID is a meter label.",
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
        text = domain_markdown(definition, facts)
        self.assertEqual((definition, facts), original)
        for marker in ("d1234", "PRIVATE_", "input bom", "start byte", "### Fact"):
            self.assertNotIn(marker, text)
        for marker in ("17.5 m²", "§71a GEG", "source ID is a meter label", "Capacity unknown—not a breach.",
                       "Proposed, not installed", "Nested substantive source", "kWh", "6,047 m²", "7,704.08 m²",
                       "ä 原文\n  second line", "false", "null", "{}", "[]", "**quantity:** 0", "**means:** 0"):
            self.assertIn(marker, text)
        for heading in ("Supply", "Areas", "Other supplied facts"):
            self.assertEqual(text.count("## " + heading), 1)
        self.assertLess(text.index("Contradictory:"), text.index("## Areas"))
        self.assertLess(text.index("6,047"), text.index("7,704.08"))
        self.assertEqual(text.count("**means:**"), 2)
        self.assertIn("No recorded facts assigned", domain_markdown(definition, []))
        self.assertIn("null", domain_markdown({"responsibilities": None}, []))


if __name__ == "__main__":
    unittest.main()

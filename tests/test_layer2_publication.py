import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ML.deep_research.layer2.backend.fs import load_json
from ML.deep_research.layer2.backend.jobs import saved_text
from ML.deep_research.layer2.backend.publication import domain_definitions, domain_names, materialize
from tests.layer2_fixtures import FakeStages, domain_plan, new_run


class MarkdownTests(unittest.TestCase):
    def test_complete_qualified_meanings_survive_raw_storage_and_shared_domain_routing(self):
        from tests.layer2_fixtures import section

        rule = ("## Delivery\n- If supplier S misses the agreed date, buyer B may cancel without a fee "
                "and recover the advance, except for buyer-caused delay; notify within 14 days.\n")
        costs = ("## Estimates\n- Indicative 2027 programme: EUR 900,000 net; proposed control unit: "
                 "EUR 80,000 net. 医院: not approved spend.\n"
                 "- A separate 2026 gross estimate is EUR 850,000; comparability unresolved.\n")
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp), text=rule + costs, plugin="# Operations\n# Finance")
            fake = FakeStages()
            fake.outputs["metadata"] = "# Subject\nShared identity: 医院 programme.\n"
            raw = json.dumps({"D01": rule + costs, "D02": rule + costs}, ensure_ascii=False)
            fake.outputs["distribution"] = raw
            fake.run(run)
            request = next(req for stage, req, _ in fake.calls if stage == "distribution")
            self.assertEqual(section(request, "new_content"), rule + costs)
            self.assertEqual(section(request, "asset_metadata"), fake.outputs["metadata"])
            record = load_json(run / "run.json")
            response = run / record["jobs"]["distribution/000001"]["response_path"]
            self.assertEqual(saved_text(response), raw)
            for name in ("operations", "finance"):
                self.assertEqual(saved_text(run / f"domains/{name}.md"),
                                 f"# {name.title()}\n\n## Research responsibilities\n"
                                 f"- Research {name.title()}.\n\n\n" + rule + costs)
            fake.run(run)
            self.assertEqual(len(fake.calls), 3)

    def test_ids_ignore_body_headings_and_preserve_exact_unicode_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp), plugin="# Energy\n# Finance")
            fake = FakeStages()
            body = "## Heating\r\n- Proposed, not installed; 医院 4 MW in 2024.\r\n"
            body += "```md\n# Not a routing heading\n```\n# Energy  TYPO\n- Scope matters."
            fake.outputs["distribution"] = json.dumps({"D01": body, "D02": "- 500 EUR; exceptions retained."})
            fake.run(run)
            energy = saved_text(run / "domains/energy.md")
            self.assertIn("Research Energy.", energy)
            self.assertIn(body, energy)
            self.assertIn("500 EUR", (run / "domains/finance.md").read_text())
            self.assertNotIn("D01", energy)
            self.assertNotIn("domain_id", energy)
            self.assertFalse((run / "unresolved.md").exists())
            overview = (run / "domain_plan.md").read_text()
            self.assertIn("## Energy\n\n- Research Energy.", overview)
            self.assertIn("## Finance\n\n- Research Finance.", overview)
            self.assertNotIn("D01", overview)
            self.assertFalse((run / "domain_plan.json").exists())
            self.assertEqual(load_json(run / "_internal/trace/routing_issues.json")["issues"], [])
            design = load_json(run / "run.json")["jobs"]["design/000001"]["response_path"]
            self.assertEqual(saved_text(run / design), domain_plan("Energy", "Finance"))
            self.assertIn(f"({design})", overview)
            self.assertIn("[Domain plan](domain_plan.md)", (run / "README.md").read_text())

    def test_duplicate_contributions_unknown_ids_and_unconventional_values_remain_visible(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp), plugin="# Energy\n# Finance")
            fake = FakeStages()
            raw = '{"D01":"First 4 MW","D01":"Second 5 MW","D99":"Unmatched 医院","D02":{"x":1,"x":2}}'
            fake.outputs["distribution"] = raw
            fake.run(run)
            record = load_json(run / "run.json")
            energy = (run / "domains/energy.md").read_text()
            self.assertLess(energy.index("First 4 MW"), energy.index("Second 5 MW"))
            self.assertEqual(saved_text(run / record["jobs"]["distribution/000001"]["response_path"]), raw)
            audit = load_json(run / "_internal/trace/routing_issues.json")
            self.assertTrue(audit["object_values_are_member_pairs"])
            self.assertEqual([item["value"] for item in audit["issues"]], ["Unmatched 医院", [["x", 1], ["x", 2]]])
            self.assertIn("Warning: 2", (run / "README.md").read_text())
            self.assertEqual(record["status"], "complete")
            fake.run(run)
            self.assertEqual(len(fake.calls), 3)

    def test_ambiguous_plan_ids_and_duplicate_fields_are_not_guessed(self):
        raw = '{"domains":[{"domain_id":"D01","name":"First"},{"domain_id":"D01","name":"Second"},'
        raw += '{"domain_id":"D02","name":"Useful","responsibilities":["Investigate"]},'
        raw += '{"domain_id":"D03","name":"One","name":"Two"},{"domain_id":"D03","name":"Three"}],'
        raw += '"unexpected":{"a":1,"a":2}}'
        definitions, issues = domain_definitions(raw, "raw-response.json")
        self.assertEqual(list(definitions), ["D02"])
        self.assertTrue(any(item["kind"] == "duplicate_domain_id" for item in issues))
        self.assertTrue(any(item["kind"] == "ambiguous_definition" for item in issues))
        self.assertEqual(issues[-1]["value"], ["unexpected", [("a", 1), ("a", 2)]])
        for item in issues:
            self.assertEqual(item["response_path"], "raw-response.json")

    def test_missing_or_unconventional_responsibilities_do_not_reject_other_content(self):
        raw = '{"domains":[{"domain_id":"D01","name":"A","responsibilities":["Duty",{"other":5}],"extra":"keep"},'
        raw += '{"domain_id":"D02","name":"B"}],"domains":[{"domain_id":"D03","name":"C","responsibilities":"Duty C"}]}'
        definitions, issues = domain_definitions(raw, "saved.json")
        self.assertEqual(list(definitions), ["D01", "D02", "D03"])
        self.assertEqual(definitions["D01"]["responsibilities"], ["Duty"])
        self.assertEqual(definitions["D02"]["responsibilities"], [])
        self.assertEqual(definitions["D03"]["responsibilities"], ["Duty C"])
        self.assertEqual(len(issues), 2)

    def test_only_unambiguous_definitions_reach_distribution_and_fact_qualifications_survive(self):
        from tests.layer2_fixtures import section
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeStages()
            fake.outputs["design"] = '{"domains":[{"domain_id":"D01","name":"Wrong A"},'
            fake.outputs["design"] += '{"domain_id":"D01","name":"Wrong B"},'
            fake.outputs["design"] += '{"domain_id":"D02","name":"Useful","responsibilities":["Duty"]}]}'
            body = "## Contract\n- Area/parking differences: no claim or rent change.\n"
            body += "- Landlord changes fire plans for future authority requirements unrelated to tenant works/use.\n"
            body += "- 30 years; three-year extensions unless terminated 12 months before term-end.\n"
            body += "- January 2026 payments under reservation pending signed addendum.\n"
            body += "## Scope\n- Indicative 1,888,100 across repair categories; not garage-only.\n"
            body += "- Access over neighboring parcel benefits this asset; no burden against it.\n"
            body += "- 医院: alternative approved, not installed; different periods are not a contradiction.\n"
            fake.outputs["distribution"] = json.dumps({"D02": body}, ensure_ascii=False)
            fake.run(run)
            request = next(req for stage, req, _ in fake.calls if stage == "distribution")
            definitions = json.loads(section(request, "domain_plan"))["domains"]
            self.assertEqual([row["domain_id"] for row in definitions], ["D02"])
            self.assertTrue(saved_text(run / "domains/useful.md").endswith(body))
            design = load_json(run / "run.json")["jobs"]["design/000001"]["response_path"]
            self.assertEqual(saved_text(run / design), fake.outputs["design"])
            self.assertNotIn("Wrong A", (run / "domain_plan.md").read_text())

    def test_collision_reserved_unicode_and_untrusted_names_or_ids(self):
        names = ["CON", "con", "NUL", "COM1", "LPT9", "Energy & Carbon", "Energy and Carbon",
                 "../escape/C:/foo", "保险", "A" * 120, "A" * 119 + "B", "保险"]
        definitions = {f"../../D{i}": {"name": name} for i, name in enumerate(names)}
        paths = domain_names(definitions)
        self.assertEqual(len({p.casefold() for p in paths.values()}), len(names))
        self.assertEqual(paths, domain_names(definitions))
        for path in paths.values():
            self.assertEqual(Path(path).parent, Path("domains"))
            self.assertLess(len(Path(path).name), 140)
            self.assertNotIn(Path(path).stem.casefold(), {"con", "nul", "com1", "lpt9"})

    def test_empty_distribution_and_missing_members_are_not_failures_or_retry_triggers(self):
        for response in ("{}", '{"D01":"Only relevant domain"}'):
            with self.subTest(response=response), tempfile.TemporaryDirectory() as tmp:
                run = new_run(Path(tmp))
                fake = FakeStages()
                fake.outputs["distribution"] = response
                fake.run(run)
                fake.run(run)
                self.assertEqual(len(fake.calls), 3)
                record = load_json(run / "run.json")
                self.assertEqual(record["status"], "complete")
                self.assertEqual(record["publication"]["routing_issues"], 0)
                self.assertNotIn("Warning:", (run / "README.md").read_text())

    def test_failed_publication_can_rebuild_without_model_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeStages()
            original = (run / "README.md").read_bytes()
            with patch("ML.deep_research.layer2.backend.publication.materialize", side_effect=OSError("offline write failure")):
                with self.assertRaises(OSError):
                    fake.run(run)
            self.assertEqual((run / "README.md").read_bytes(), original)
            self.assertEqual(len(fake.calls), 3)
            fake.run(run)
            self.assertEqual(len(fake.calls), 3)
            self.assertTrue((run / "domains/operations.md").is_file())

    def test_previous_view_bytes_survive_atomic_replace_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeStages()
            fake.run(run)
            before = (run / "domains/operations.md").read_bytes()
            revision = Path(tmp) / "revision"
            (revision / "domains").mkdir(parents=True)
            (revision / "domains/operations.md").write_text("New view")
            with patch.object(Path, "replace", side_effect=OSError("interrupted replace")):
                with self.assertRaises(OSError):
                    materialize(run, revision)
            self.assertEqual((run / "domains/operations.md").read_bytes(), before)
            self.assertTrue(any(p.read_bytes() == before for p in (run / "_internal/trace/presentation_history").rglob("operations.md")))

    def test_republication_removes_only_archived_obsolete_views(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            fake = FakeStages()
            fake.run(run)
            old_plan = (run / "domain_plan.md").read_bytes()
            (run / "domain_plan.json").write_bytes(b'OLD RAW JSON\r\n')
            old = (run / "domains/ownership.md").read_bytes()
            row = load_json(run / "run.json")["jobs"]["design/000001"]
            (run / row["response_path"]).unlink()
            fake.outputs["design"] = domain_plan("Operations")
            fake.run(run)
            self.assertFalse((run / "domains/ownership.md").exists())
            self.assertFalse((run / "domain_plan.json").exists())
            history = run / "_internal/trace/presentation_history"
            self.assertTrue(any(p.read_bytes() == b'OLD RAW JSON\r\n' for p in history.rglob("domain_plan.json")))
            self.assertTrue(any(p.read_bytes() == old_plan for p in history.rglob("domain_plan.md")))
            self.assertTrue(any(p.read_bytes() == old for p in (run / "_internal/trace/presentation_history").rglob("ownership.md")))

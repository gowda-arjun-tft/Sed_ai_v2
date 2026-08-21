"""Layer 3 handoff and CLI contract checks."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from ML.deep_research.layer2.fs import load_json, write_json
from ML.deep_research.layer3.cli import _parser, main
from ML.deep_research.layer3.pipeline.create_run import create_run as create_l3_run
from ML.deep_research.layer3.pipeline.run_checks import run_checks

from tests.common import create_complete_l3_run, create_complete_run


class HandoffProvenanceTests(unittest.TestCase):
    """What Layer 3 records about its Layer 2 source must be what Layer 2 said.

    `create_run` used to write a literal `{"passed": 19, "failed": 0}` into
    `source_l2.checks`, and check 1 then compared that field against the same
    literal — a tautology that always passed and proved nothing, while stating a
    count Layer 2 can no longer produce. Both sides are now derived.
    """

    def test_the_recorded_l2_result_is_copied_not_asserted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            l3_run = create_complete_l3_run(root)
            l3 = load_json(l3_run / "run.json")
            source = l3["source_l2"]
            l2_run = Path(source["path"])
            l2 = load_json(l2_run / "run.json")

        self.assertEqual(source["checks"], l2["checks"])
        self.assertEqual(source["status"], l2["status"])
        self.assertEqual(source["facts"], l2["facts"])
        # The count is whatever the current Layer 2 contract produced.
        self.assertNotEqual(source["checks"].get("passed"), 19)
        self.assertGreater(source["checks"]["run"], 0)

    def test_no_layer3_module_restates_a_layer2_check_count(self):
        """A literal count here is what made check 1 vacuous."""
        layer3 = Path(__file__).resolve().parents[1] / "ML" / "deep_research" / "layer3"
        for path in layer3.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn('"passed": 19', text, path.name)
            self.assertNotIn("19/19", text, path.name)

    def test_an_incomplete_recorded_handoff_fails_check_one(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            l3_run = create_complete_l3_run(root)
            record = load_json(l3_run / "run.json")
            record["source_l2"]["checks"] = {"run": 8, "passed": 7, "failed": 1}
            write_json(l3_run / "run.json", record)
            checks = run_checks(l3_run)
        first = [ok for number, _, ok, _ in checks if number == 1]
        self.assertEqual(first, [False])

    def test_new_run_requires_public_input_confirmation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            l2_run = create_complete_run(root)
            destination = root / "l3-runs"
            with self.assertRaisesRegex(ValueError, "public-input confirmation"):
                create_l3_run(l2_run, destination)
            self.assertFalse(destination.exists())

    def test_legacy_or_relabelled_mission_rosters_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            l2_run = create_complete_run(root)
            first = next((l2_run / "missions").glob("*.json"))
            mission = load_json(first)
            mission["agent"] = "User-defined domain label"
            write_json(first, mission)
            write_json(
                l2_run / "missions" / "legacy-fourteenth-domain.json",
                {"agent": "Legacy domain", "mission": "Do not migrate.", "context": []},
            )
            with self.assertRaisesRegex(ValueError, "exact current eight-domain"):
                create_l3_run(
                    l2_run,
                    root / "l3-runs",
                    public_input_confirmed=True,
                )


class Layer3CliContractTests(unittest.TestCase):
    def test_public_fixtures_option_is_removed(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as caught:
                _parser().parse_args(
                    ["--research", "runs/L2_example", "--fixtures", "fixtures"]
                )
        self.assertEqual(caught.exception.code, 2)

    def test_cli_rejects_online_research_without_confirmation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            l2_run = create_complete_run(root)
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    main(["--research", str(l2_run), "--online"])
        self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()

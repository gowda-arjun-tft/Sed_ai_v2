"""The report must always produce a record, whatever the agent wrote.

The agent authors the mission files, so `context` can arrive as anything JSON
allows. Before these tests existed, four of the shapes below raised out of
`run_checks` — and because the exception happened before `check_report.md` was
written and before `run.json` was stamped, the run was left with no report at all
and `status` stuck at `"started"`. That reads as a run that never finished rather
than one that produced malformed output, which is the worst available outcome.

The rule these tests pin: **a wrong shape is a failed check, never a crash.**
Coverage is still never gated — an empty context list passes, by design.
"""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from ML.deep_research.layer2.cli import _save_account, final_message, usage_summary
from ML.deep_research.layer2.fs import load_json, slug
from ML.deep_research.layer2.report import run_checks
from ML.deep_research.layer2.settings import AGENT_NAMES

from tests.common import create_complete_run


def _write(path: Path, value) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


class ReportNeverCrashesTests(unittest.TestCase):
    """Every one of these used to raise, or still needs to keep passing."""

    def _run_with(self, mutate) -> tuple[int, int, str, bool]:
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = create_complete_run(Path(temporary))
            mutate(run_dir, run_dir / "missions" / f"{slug(AGENT_NAMES[0])}.json")
            checks = run_checks(run_dir)
            passed = sum(ok for _, _, ok, _ in checks)
            status = load_json(run_dir / "run.json").get("status")
            report_written = (run_dir / "check_report.md").is_file()
        return passed, len(checks), status, report_written

    def test_a_malformed_context_fails_a_check_instead_of_raising(self):
        shapes = {
            "null": None,
            "string": "a string",
            "object": {},
            "list of null": [None],
            "list of numbers": [42],
        }
        for label, value in shapes.items():
            with self.subTest(context=label):
                passed, total, status, report = self._run_with(
                    lambda run, path, value=value: _write(
                        path, {**load_json(path), "context": value}
                    )
                )
                self.assertLess(passed, total, label)
                self.assertEqual(status, "failed", label)
                # The point of the fix: a record exists either way.
                self.assertTrue(report, label)

    def test_an_empty_context_still_passes(self):
        """Coverage is never gated. This is the human's explicit decision."""
        passed, total, status, report = self._run_with(
            lambda run, path: _write(path, {**load_json(path), "context": []})
        )
        self.assertEqual(passed, total)
        self.assertEqual(status, "complete")
        self.assertTrue(report)

    def test_unparseable_json_fails_cleanly(self):
        passed, total, status, report = self._run_with(
            lambda run, path: path.write_text("not json at all", encoding="utf-8")
        )
        self.assertLess(passed, total)
        self.assertTrue(report)

    def test_a_mission_file_that_is_a_list_fails_cleanly(self):
        passed, total, status, report = self._run_with(
            lambda run, path: _write(path, [1, 2, 3])
        )
        self.assertLess(passed, total)
        self.assertTrue(report)

    def test_a_corrupt_run_json_is_reported_not_fatal(self):
        """The agent can write inside /run/, so this is reachable."""
        passed, total, status, report = self._run_with(
            lambda run, path: (run / "run.json").write_text("{", encoding="utf-8")
        )
        self.assertLess(passed, total)
        self.assertTrue(report)

    def test_a_deleted_fact_sheet_is_reported_not_fatal(self):
        passed, total, status, report = self._run_with(
            lambda run, path: (run / "inputs" / "fact_sheet.md").unlink()
        )
        self.assertLess(passed, total)
        self.assertTrue(report)

    def test_a_missing_run_json_still_raises(self):
        """Operator error, not agent output — naming it beats writing a report."""
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(FileNotFoundError):
                run_checks(Path(temporary))


class AgentAccountTests(unittest.TestCase):
    """The agent is asked how it checked itself; the answer must survive.

    `cli.write_missions` used to discard the result of `ainvoke` entirely, which
    threw away the only record of the self-verification — the report counts files
    and keys and cannot see reasoning.
    """

    def test_every_provider_content_shape_is_read_or_yields_empty(self):
        cases = {
            "plain string": ({"messages": [SimpleNamespace(content="wrote 14")]}, "wrote 14"),
            "responses blocks": (
                {"messages": [SimpleNamespace(content=[
                    {"type": "reasoning", "summary": "hidden"},
                    {"type": "output_text", "text": "checked with Python"}])]},
                "checked with Python",
            ),
            "two text blocks": (
                {"messages": [SimpleNamespace(content=[
                    {"type": "text", "text": "one"},
                    {"type": "text", "text": "two"}])]},
                "one\ntwo",
            ),
            "no messages": ({"messages": []}, ""),
            "no key": ({}, ""),
            "none": (None, ""),
            "content none": ({"messages": [SimpleNamespace(content=None)]}, ""),
            "content dict": ({"messages": [SimpleNamespace(content={"text": "x"})]}, ""),
            "reasoning only": (
                {"messages": [SimpleNamespace(content=[
                    {"type": "reasoning", "summary": "hidden"}])]},
                "",
            ),
        }
        for label, (result, expected) in cases.items():
            with self.subTest(shape=label):
                self.assertEqual(final_message(result), expected)

    def test_an_account_is_written_verbatim_and_an_empty_one_is_not(self):
        account = "Read the sheet in one pass; Python counted 41 blocks."
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            _save_account(run_dir, "   \n  ")
            self.assertFalse((run_dir / "agent_report.md").exists())
            _save_account(run_dir, account)
            written = (run_dir / "agent_report.md").read_text(encoding="utf-8")
        self.assertIn(account, written)


class UsageRecordTests(unittest.TestCase):
    """Layer 2 recorded nothing about its own cost. Recording is not limiting.

    Nothing reads these numbers to stop or shape a run. They exist so that "how
    many model requests does a run take" stops being a guess.
    """

    def test_turns_tokens_and_tool_calls_are_summed(self):
        result = {
            "messages": [
                _message({"input_tokens": 1200, "output_tokens": 300}, [{"name": "run_python"}]),
                _message(None, None),  # a tool result carries no usage
                _message({"input_tokens": 1800, "output_tokens": 900},
                         [{"name": "write_file"}, {"name": "write_file"}]),
            ]
        }
        self.assertEqual(
            usage_summary(result),
            {
                "top_level_model_calls": 2,
                "top_level_tool_calls": 3,
                "input_tokens": 3000,
                "output_tokens": 1200,
            },
        )

    def test_a_missing_or_empty_result_yields_zeros_rather_than_raising(self):
        for result in (None, {}, {"messages": []}, {"messages": [_message(None, None)]}):
            with self.subTest(result=result):
                self.assertEqual(usage_summary(result)["top_level_model_calls"], 0)

    def test_the_field_names_admit_that_subagents_are_not_counted(self):
        """The undercount is stated in the name, not hidden behind it."""
        for key in usage_summary(None):
            if "model_calls" in key or "tool_calls" in key:
                self.assertTrue(key.startswith("top_level_"), key)


def _message(usage, tool_calls):
    from types import SimpleNamespace

    message = SimpleNamespace()
    if usage is not None:
        message.usage_metadata = usage
    if tool_calls is not None:
        message.tool_calls = tool_calls
    return message


if __name__ == "__main__":
    unittest.main()

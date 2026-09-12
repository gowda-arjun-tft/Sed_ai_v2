"""Dynamic Markdown handoff, consent, immutable snapshots and CLI boundaries."""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ML.deep_research.layer2.backend.fs import atomic_write_text, load_json, write_json
from ML.deep_research.layer3.cli import _parser, main
from ML.deep_research.layer3.pipeline.create_run import create_run, local_path
from tests.layer3_fixtures import layer2_input, new_run, snapshot


class HandoffTests(unittest.TestCase):
    def test_sources_are_frozen_byte_for_byte_beside_layer2(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            l2 = layer2_input(root)
            metadata = b"\xef\xbb\xbf# Identity\r\nUnicode: " + "医院".encode()
            (l2 / "asset_metadata.md").write_bytes(metadata)
            guide = root / "suggestion.md"
            guide.write_bytes(b"# Official records\r\n")
            before = snapshot(l2)
            run = create_run(l2, root / "different-root", source_suggestion=guide,
                             public_input_confirmed=True)
            self.assertTrue(run.parent.samefile(l2.parent))
            self.assertEqual((run / "_internal/inputs/asset_metadata.md").read_bytes(), metadata)
            self.assertEqual((run / "_internal/inputs/source_suggestion.md").read_bytes(), guide.read_bytes())
            self.assertEqual(before, snapshot(l2))
            self.assertRegex(run.name, r"^L3_\d{8}_\d{6}_[0-9a-f]{4}$")

    def test_invalid_inputs_fail_before_directory_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            l2 = layer2_input(root)
            guide = root / "missing.md"
            for options in ({}, {"public_input_confirmed": True, "source_suggestion": guide},
                            {"public_input_confirmed": True, "reasoning_effort": "invalid"}):
                with self.assertRaises((ValueError, OSError)):
                    create_run(l2, root, **options)
                self.assertFalse(list(l2.parent.glob("L3_*")))
            write_json(l2 / "run.json", {"schema_version": 6, "status": "complete"})
            with self.assertRaisesRegex(ValueError, "schema-9"):
                create_run(l2, root, public_input_confirmed=True)

    def test_missing_metadata_and_empty_roster_fail_before_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            l2 = layer2_input(root)
            (l2 / "asset_metadata.md").unlink()
            with self.assertRaises(OSError):
                create_run(l2, root, public_input_confirmed=True)
            for path in (l2 / "domains").glob("*.md"):
                path.unlink()
            with self.assertRaisesRegex(ValueError, "no domain"):
                create_run(l2, root, public_input_confirmed=True)
            self.assertFalse(list(l2.parent.glob("L3_*")))

    def test_new_snapshots_change_without_rewriting_previous_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = new_run(root)
            before = snapshot(first)
            l2 = Path(load_json(first / "run.json")["source_l2"]["path"])
            guide = root / "source_suggestion.md"
            atomic_write_text(guide, "# Revised source preferences\n")
            second = create_run(l2, root, source_suggestion=guide, public_input_confirmed=True)
            self.assertEqual(before, snapshot(first))
            self.assertNotEqual((first / "_internal/inputs/source_suggestion.md").read_bytes(),
                                (second / "_internal/inputs/source_suggestion.md").read_bytes())

    def test_output_names_are_safe_and_not_model_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp), ["café", "cafe", "CON-report", "医院"])
            paths = [d["output_path"] for d in load_json(run / "run.json")["domains"]]
            self.assertEqual(len(paths), len(set(paths)))
            for path in paths:
                self.assertTrue(path.startswith("sources/"))
                self.assertTrue(path.endswith(".json"))
            with self.assertRaisesRegex(ValueError, "escapes"):
                local_path(run, "../other-run/secret")


class CliTests(unittest.TestCase):
    def test_source_guidance_flag_and_frozen_resume_options(self):
        args = _parser().parse_args(["--research", "L2", "--source-suggestion", "guidance.md"])
        self.assertEqual(args.source_suggestion, Path("guidance.md"))
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(["--resume-l3", "L3", "--source-suggestion", "different.md"])

    def test_new_run_requires_explicit_online_confirmation(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            main(["--research", "L2", "--online"])
        self.assertEqual(caught.exception.code, 2)

    def test_checks_only_make_no_changes_or_api_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            before = snapshot(run)
            with contextlib.redirect_stdout(io.StringIO()), patch(
                "ML.deep_research.layer3.cli.run_research", side_effect=AssertionError("No calls")
            ):
                main(["--check-only", str(run)])
            self.assertEqual(before, snapshot(run))

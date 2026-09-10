import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ML.deep_research.layer2 import create_run
from ML.deep_research.layer2.backend.fs import load_json, sha256
from ML.deep_research.layer2.backend.runner import source_sections
from ML.deep_research.layer2.backend.settings import PROMPTS_DIR, PROMPT_FILES
from ML.deep_research.layer2.backend.windows import encoding, source_windows, token_count
from tests.layer2_fixtures import new_run


class InputTests(unittest.TestCase):
    def test_public_input_confirmation_required_before_creation_and_resume_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for confirmation in (False, None, "true", 1):
                with self.assertRaisesRegex(ValueError, "public-input confirmation"):
                    create_run(root / "missing", root / "missing", root / "missing", root / "runs",
                               public_input_confirmed=confirmation)
                self.assertFalse((root / "runs").exists())
            run = new_run(root)
            from ML.deep_research.layer2.backend.fs import write_json
            from ML.deep_research.layer2.backend.runner import run_all
            record = load_json(run / "run.json")
            record["public_input_confirmed"] = False
            write_json(run / "run.json", record)
            before = {p: p.read_bytes() for p in run.rglob("*") if p.is_file()}
            with self.assertRaisesRegex(ValueError, "frozen public-input confirmation"):
                run_all(run)
            self.assertEqual(before, {p: p.read_bytes() for p in run.rglob("*") if p.is_file()})

    def test_cli_passes_explicit_confirmation_and_has_no_implicit_opt_in(self):
        from ML.deep_research.layer2.backend.cli import main
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            with patch("ML.deep_research.layer2.backend.cli.create_run", return_value=run) as create, patch(
                "ML.deep_research.layer2.backend.cli.run_all"
            ), patch("ML.deep_research.layer2.backend.cli.load_dotenv_key"):
                args = ["facts.md", "--domain-plugin", "plugin.md", "--requirements", "requirements.md"]
                main(args)
                self.assertIs(create.call_args.kwargs["public_input_confirmed"], False)
                self.assertEqual(create.call_args.kwargs["web_search_context_size"], "medium")
                self.assertEqual(create.call_args.kwargs["web_search_verbosity"], "medium")
                main(args + ["--public-input-confirmed", "--web-search-depth", "high",
                             "--web-search-verbosity", "low"])
                self.assertIs(create.call_args.kwargs["public_input_confirmed"], True)
                self.assertEqual(create.call_args.kwargs["web_search_context_size"], "high")
                self.assertEqual(create.call_args.kwargs["web_search_verbosity"], "low")

    def test_fixed_source_token_windows_and_no_tail(self):
        for count, lengths in [(50_000, [50_000]), (95_000, [50_000, 50_000]),
                               (159_316, [50_000, 50_000, 50_000, 24_316]),
                               (701_133, [50_000] * 15 + [26_133])]:
            text = " x" * count
            ids = encoding().encode(text)
            windows = source_windows(text)
            self.assertEqual([w["tokens"] for w in windows], lengths)
            self.assertEqual("".join(w["new_content"] for w in windows), text)
            for index, w in enumerate(windows):
                self.assertEqual(encoding().encode(w["overlap_context"] + w["new_content"]),
                                 ids[w["start_token"]:w["end_token"]])
                self.assertEqual(token_count(w["overlap_context"]), 5_000 if index else 0)
                if index:
                    previous = windows[index - 1]
                    self.assertEqual(encoding().encode(w["overlap_context"]),
                                     ids[previous["end_token"] - 5_000:previous["end_token"]])

    def test_unicode_bom_line_endings_and_seek_preserve_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = "\ufeff# Subject\r\n🏥 医院 é 😀\nCondition: approved, not installed.\r\n" * 9
            run = new_run(Path(tmp), text=text, size=23)
            self.assertEqual((run / "_internal/inputs/fact_sheet.md").read_bytes(), text.encode())
            manifest = load_json(run / "_internal/trace/source/manifest.json")
            pieces = [source_sections(run, window) for window in manifest]
            self.assertEqual("".join(p["new_content"] for p in pieces), text.removeprefix("\ufeff"))
            for window, piece in zip(manifest, pieces):
                raw = text.removeprefix("\ufeff").encode()
                self.assertEqual(piece["overlap_context"] + piece["new_content"],
                                 raw[window["start_byte"]:window["end_byte"]].decode())

    def test_creation_freezes_three_prompts_and_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            record = load_json(run / "run.json")
            self.assertEqual(record["schema_version"], 9)
            self.assertTrue(record["public_input_confirmed"])
            self.assertEqual(record["web_search"], {"context_size": "medium", "verbosity": "medium",
                                                     "tool_choice": "auto", "input_token_limit": 128_000})
            self.assertEqual(record["chunking"]["stride_tokens"], 45_000)
            self.assertEqual(record["chunking"]["max_concurrency"], 5)
            self.assertEqual(record["context_policy"]["maximum_tokens"], 350_000)
            self.assertEqual(record["context_policy"]["target_tokens"], 300_000)
            for stage, filename in PROMPT_FILES.items():
                path = run / "_internal/inputs/prompts" / f"{stage}.md"
                self.assertEqual(path.read_bytes(), (PROMPTS_DIR / filename).read_bytes())
                self.assertEqual(sha256(path), record["inputs"][f"prompts/{stage}.md"]["sha256"])
            self.assertFalse(list(run.rglob("*.sqlite*")))

    def test_bad_inputs_fail_before_creating_run(self):
        for bad in ["missing", "empty", "encoding", "reasoning", "depth", "verbosity"]:
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                paths = [root / name for name in ("facts", "plugin", "requirements")]
                for p in paths:
                    p.write_text("Supplied content")
                if bad == "missing":
                    paths[2].unlink()
                elif bad == "empty":
                    paths[1].write_text("  ")
                elif bad == "encoding":
                    paths[0].write_bytes(b"\xff")
                with self.assertRaises((OSError, ValueError)):
                    create_run(*paths, root / "runs",
                               reasoning_effort="invalid" if bad == "reasoning" else "high",
                               web_search_context_size="invalid" if bad == "depth" else "medium",
                               web_search_verbosity="invalid" if bad == "verbosity" else "medium",
                               public_input_confirmed=True)
                self.assertFalse((root / "runs").exists())

    def test_new_prompt_snapshots_do_not_refresh_old_ones(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prompts = root / "old_prompts"
            prompts.mkdir()
            for stage, name in PROMPT_FILES.items():
                content = (PROMPTS_DIR / name).read_bytes()
                if stage == "distribution":
                    content = b"# Goal\nPrevious distribution instructions.\n"
                (prompts / name).write_bytes(content)
            with patch("ML.deep_research.layer2.backend.create_run.PROMPTS_DIR", prompts):
                old = new_run(root)
            before = {p: p.read_bytes() for p in old.rglob("*") if p.is_file()}
            new = new_run(root)
            snapshot = new / "_internal/inputs/prompts/distribution.md"
            self.assertEqual(snapshot.read_bytes(), (PROMPTS_DIR / PROMPT_FILES["distribution"]).read_bytes())
            self.assertIn("separate consequences", snapshot.read_text())
            record = load_json(new / "run.json")
            self.assertEqual(sha256(snapshot), record["inputs"]["prompts/distribution.md"]["sha256"])
            for stage in ("metadata", "design"):
                self.assertEqual((new / f"_internal/inputs/prompts/{stage}.md").read_bytes(),
                                 (old / f"_internal/inputs/prompts/{stage}.md").read_bytes())
            self.assertEqual(before, {p: p.read_bytes() for p in old.rglob("*") if p.is_file()})

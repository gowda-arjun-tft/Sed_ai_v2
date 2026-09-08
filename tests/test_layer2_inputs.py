import tempfile
import unittest
from pathlib import Path

from ML.deep_research.layer2.backend.create_run import create_run
from ML.deep_research.layer2.ML.context import dump, estimate
from ML.deep_research.layer2.backend.fs import load_json, sha256, write_json, read_text
from ML.deep_research.layer2.ML.agent import Layer2Response, read_only_filesystem
from ML.deep_research.layer2.backend.runner import source_payloads, review_payloads
from ML.deep_research.layer2.backend.settings import PROMPTS_DIR, PROMPT_FILES, STAGES
from ML.deep_research.layer2.backend.windows import encoding, source_windows, text_pages, token_count
from tests.layer2_fixtures import new_run


class InputTests(unittest.TestCase):
    def test_source_windows_and_exact_overlap(self):
        codec = encoding()
        text = codec.decode([codec.encode(" property")[0]] * 701_133)
        windows = source_windows(text)
        self.assertEqual([w["tokens"] for w in windows], [60_000] * 13 + [51_133])
        self.assertEqual(sum(w["tokens"] for w in windows), 831_133)
        self.assertEqual("".join(w["new_content"] for w in windows), text)
        for previous, current in zip(windows, windows[1:]):
            self.assertEqual(codec.encode(current["overlap_context"]),
                             codec.encode(previous["overlap_context"] + previous["new_content"])[-10_000:])

    def test_small_exact_end_and_headings(self):
        for text in ["hello", " property" * 60_000, " property" * 100_000,
                     "## first\n" + "alpha " * 30_000 + "\n## second\n" + "beta " * 30_000]:
            windows = source_windows(text)
            self.assertEqual("".join(w["new_content"] for w in windows), text)
            self.assertEqual(windows[-1]["end_token"], token_count(text))
        self.assertEqual(len(source_windows(" property" * 60_000)), 1)
        self.assertEqual([w["tokens"] for w in source_windows(" property" * 100_000)],
                         [60_000, 50_000])

    def test_unicode_and_original_byte_boundaries(self):
        text = "😀漢字 café\r\n🏥𝄞 नमस्ते " * 400
        windows = source_windows(text, 61, 11)
        self.assertEqual("".join(w["new_content"] for w in windows), text)
        for w in windows:
            self.assertEqual(text.encode()[w["start_byte"]:w["end_byte"]].decode(),
                             w["overlap_context"] + w["new_content"])
            self.assertNotIn("\ufffd", w["new_content"])
        pages = text_pages(text, 29)
        self.assertEqual("".join(pages), text)
        self.assertTrue(all(token_count(p) <= 29 for p in pages))

    def test_preflight_and_frozen_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run = new_run(root, text="\ufeffLine 1\r\nLine 2")
            meta = load_json(run / "run.json")
            self.assertEqual(meta["schema_version"], 5)
            self.assertFalse(meta["downstream_integrated"])
            self.assertEqual(meta["context_policy"]["maximum_tokens"], 250_000)
            self.assertEqual(meta["chunking"]["stride_tokens"], 50_000)
            self.assertFalse((run / "missions").exists())
            for name, info in meta["inputs"].items():
                self.assertEqual(sha256(run / "_internal/inputs" / name), info["sha256"])
                self.assertTrue(Path(info["source_path"]).is_file())
            for stage in STAGES:
                name = f"prompts/{stage}.md"
                self.assertEqual(Path(meta["inputs"][name]["source_path"]), PROMPTS_DIR / PROMPT_FILES[stage])
                self.assertEqual((run / "_internal/inputs" / name).read_bytes(),
                                 (PROMPTS_DIR / PROMPT_FILES[stage]).read_bytes())
            self.assertEqual((root / "facts.md").read_bytes(), (run / "_internal/inputs/fact_sheet.md").read_bytes())
            with self.assertRaises((OSError, ValueError)):
                create_run(root / "missing", root / "plugin.md", root / "requirements.md", root / "bad")
            self.assertFalse((root / "bad").exists())
            (root / "requirements.md").write_text("")
            with self.assertRaises(ValueError):
                create_run(root / "facts.md", root / "plugin.md", root / "requirements.md", root / "empty")
            self.assertFalse((root / "empty").exists())

    def test_plain_markdown_plugins_and_grouping(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = new_run(root, plugin="An ordinary plugin, no embedded JSON required")
            second = new_run(root)
            self.assertEqual(first.parent, second.parent)
            self.assertNotEqual(first, second)

    def test_complete_catalogue_inline_or_paged_never_truncated(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            facts = [{"fact_id": "f1", "body": {"fact": "Unchanged source"},
                      "initial_assignment": {"fact_id": "f1", "domain_ids": []}}]
            context = {"requirements": "Preserve evidence", "evidence_files": ["/evidence/final_catalogue/1.txt"]}
            catalogue = {"final_catalogue": [{"domain_id": "d0001", "definition": {"name": "All duties"}}]}
            pages = review_payloads(run, "assignments", context, facts, catalogue)
            self.assertEqual(pages[0]["final_catalogue"], catalogue["final_catalogue"])
            self.assertEqual(pages[0]["facts"], facts)
            meta = load_json(run / "run.json")
            # Force a whole-catalogue fallback without any provider call.
            meta["context_policy"].update(target_tokens=20_000, maximum_tokens=25_000)
            write_json(run / "run.json", meta)
            large = {"final_catalogue": [{"responsibilities": " unique" * 30_000}]}
            pages = review_payloads(run, "assignments", context, facts, large)
            self.assertNotIn("final_catalogue", pages[0])
            self.assertEqual(pages[0]["evidence_files"], context["evidence_files"])
            self.assertEqual(pages[0]["facts"], facts)
            self.assertEqual(large["final_catalogue"][0]["responsibilities"], " unique" * 30_000)
            prompt = read_text(run / "_internal/inputs/prompts/assignments.md")
            for page in pages:
                self.assertLessEqual(estimate([{"role": "user", "content": dump(page)}], prompt,
                                             read_only_filesystem().tools, Layer2Response.model_json_schema()), 20_000)

    def test_repacking_preserves_source_and_fits_assembled_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = " property" * 60_000
            run = new_run(Path(tmp), text=text)
            record = load_json(run / "run.json")
            record["context_policy"].update(target_tokens=35_000, maximum_tokens=50_000)
            write_json(run / "run.json", record)
            # A generated window cannot replace the authoritative frozen original.
            (run / "_internal/trace/source/s000001.json").write_text('{}')
            payloads = source_payloads(run, {"requirements": " property" * 4_000}, "understanding")
            self.assertGreater(len(payloads), 1)
            self.assertEqual("".join(p["new_content"] for p in payloads), text)
            prompt = read_text(run / "_internal/inputs/prompts/understanding.md")
            for payload in payloads:
                self.assertLessEqual(estimate([{"role": "user", "content": dump(payload)}], prompt,
                                             response_schema=Layer2Response.model_json_schema()), 35_000)
                source = payload["source"]
                self.assertEqual(text.encode()[source["start_byte"]:source["end_byte"]].decode(),
                                 payload["overlap_context"] + payload["new_content"])
            facts = [{"fact_id": f"f{i}", "body": " property" * 5_000} for i in range(6)]
            pages = review_payloads(run, "assignments", {"requirements": " property" * 12_000}, facts)
            self.assertGreater(len(pages), 1)
            self.assertEqual([f for p in pages for f in p["facts"]], facts)
            prompt = read_text(run / "_internal/inputs/prompts/assignments.md")
            for page in pages:
                self.assertLessEqual(estimate([{"role": "user", "content": dump(page)}], prompt,
                                             response_schema=Layer2Response.model_json_schema()), 35_000)

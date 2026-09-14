"""User-owned call settings freeze once; historical runs never read new defaults."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ML.deep_research.domain_decider.backend.fs import load_json, write_json
from ML.deep_research.research_module import run_all
from ML.deep_research.research_module.backend.create_run import verify_inputs
from ML.deep_research.research_module.backend.research_run import create_research_run, read_research_config
from tests.layer3_fixtures import FakeFinder, new_run, snapshot
from tests.research_fixtures import ResearchModel, linked_run


class ResearchConfigTests(unittest.IsolatedAsyncioTestCase):
    async def test_exact_full_and_linked_snapshots_override_parent_without_rereading(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = root / "config.json"
            raw = b'\xef\xbb\xbf{\r\n "maximum_calls":8, "wrap_up_after":3, "finalize_after":5\r\n}\r\n'
            config.write_bytes(raw)
            reader = Path.read_bytes
            reads = []

            def counted(path):
                """Observe only the selected configuration, not preserved evidence copies."""
                if path.samefile(config):
                    reads.append(path)
                return reader(path)

            with patch.object(Path, "read_bytes", counted):
                parent = new_run(root, research_config=config)
            self.assertEqual(len(reads), 1)
            self.assertTrue(reads[0].samefile(config))
            relative = "_internal/inputs/research_config.json"
            record = load_json(parent / "run.json")
            self.assertEqual(record["research"]["version"], 3)
            self.assertEqual(record["research"]["maximum_calls"], 8)
            self.assertEqual((parent / relative).read_bytes(), raw)
            self.assertEqual(record["inputs"][relative]["sha256"], hashlib.sha256(raw).hexdigest())
            await FakeFinder().run(parent)
            before = snapshot(parent)
            config.write_text('{"maximum_calls":null,"wrap_up_after":null,"finalize_after":null}', encoding="utf-8")
            reads.clear()
            with patch.object(Path, "read_bytes", counted):
                child = create_research_run(parent, root, public_input_confirmed=True, research_config=config)
            self.assertEqual(len(reads), 1)
            self.assertTrue(reads[0].samefile(config))
            child_record = load_json(child / "run.json")
            self.assertIsNone(child_record["research"]["maximum_calls"])
            self.assertEqual((child / relative).read_bytes(), config.read_bytes())
            self.assertNotEqual(record["research"]["identity"], child_record["research"]["identity"])
            config.unlink()
            verify_inputs(parent, load_json(parent / "run.json"))
            verify_inputs(child, child_record)
            self.assertEqual(snapshot(parent), before)
            (child / relative).write_text("{}")
            with self.assertRaisesRegex(ValueError, "Frozen Layer 3 input changed"):
                verify_inputs(child, child_record)

    async def test_invalid_or_missing_config_never_creates_a_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            parent = new_run(root)
            await FakeFinder().run(parent)
            before = snapshot(root / "runs")
            config = root / "bad.json"
            valid = {"maximum_calls": 8, "wrap_up_after": 3, "finalize_after": 5}
            invalid = ["", "[]", "null", "{}", "{",
                       '{"maximum_calls":8,"maximum_calls":9,"wrap_up_after":3,"finalize_after":5}']
            for key in valid:
                invalid.append(json.dumps({k: v for k, v in valid.items() if k != key}))
                for value in (None, True, "8", 1.5, -1):
                    invalid.append(json.dumps({**valid, key: value}))
            invalid += [json.dumps({**valid, "extra": 1}),
                        json.dumps({**valid, "wrap_up_after": 5}),
                        json.dumps({**valid, "finalize_after": 8})]
            for raw in invalid:
                with self.subTest(raw=raw):
                    config.write_text(raw, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        new_run(root, research_config=config)
                    with self.assertRaises(ValueError):
                        create_research_run(parent, root, public_input_confirmed=True, research_config=config)
                    self.assertEqual(snapshot(root / "runs"), before)
            config.unlink()
            with self.assertRaises(OSError):
                new_run(root, research_config=config)
            with self.assertRaises(OSError):
                create_research_run(parent, root, public_input_confirmed=True, research_config=config)
            self.assertEqual(snapshot(root / "runs"), before)
            config.write_text('{"maximum_calls":2,"wrap_up_after":0,"finalize_after":1}', encoding="utf-8")
            self.assertEqual(read_research_config(config)[1]["wrap_up_after"], 0)

    async def test_version_two_uses_frozen_limits_without_current_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, run = await linked_run(root, ["energy"])
            record = load_json(run / "run.json")
            record["research"].update(version=2, maximum_calls=80, wrap_up_after=60, finalize_after=70)
            relative = "_internal/inputs/research_config.json"
            record["inputs"].pop(relative)
            (run / relative).unlink()
            write_json(run / "run.json", record)
            before = snapshot(run / "_internal/inputs")
            model = ResearchModel()
            with model.offline(root / "checkpoints"), patch(
                "ML.deep_research.research_module.backend.research_run.read_research_config",
                side_effect=AssertionError("Historical resume must not read configuration")
            ):
                await run_all(run)
                calls = len(model.calls)
                await run_all(run)
            self.assertEqual(len(model.calls), calls)
            self.assertEqual(load_json(run / "run.json")["status"], "complete")
            self.assertTrue(all("of 80" in group[0].text for _, group, _ in model.calls))
            self.assertEqual(snapshot(run / "_internal/inputs"), before)

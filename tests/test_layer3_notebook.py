"""Exercise the single notebook workflow with no provider or research activity."""

import ast
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from ML.deep_research.domain_decider.backend.fs import load_json, write_json
from ML.deep_research.domain_decider.backend.settings import REPO_ROOT
from tests.layer3_fixtures import FakeFinder, layer2_input, new_run


def code_cells():
    """Read the actual UI, not a duplicate implementation."""
    book = json.loads((REPO_ROOT / "CDI_Layer2_Layer3.ipynb").read_text(encoding="utf-8"))
    return ["".join(cell["source"]) for cell in book["cells"] if cell["cell_type"] == "code"]


def cell_code(**overrides):
    """Change only controls to exercise the saved cell's real action branches."""
    tree = ast.parse(code_cells()[0])
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in overrides:
                node.value = ast.copy_location(ast.Constant(overrides[node.targets[0].id]), node.value)
    return compile(ast.fix_missing_locations(tree), "Notebook", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)


class SourceNotebookTests(unittest.IsolatedAsyncioTestCase):
    async def test_fresh_handoff_once_and_domain_failure_stops_chain(self):
        for status in ("complete", "partial", "failed", "exception"):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                domain = layer2_input(root)
                record = load_json(domain / "run.json")
                record["status"] = "created"
                write_json(domain / "run.json", record)
                calls = []

                def finish(path):
                    """Represent saved domain completion without an LLM."""
                    calls.append("domain")
                    record["status"] = "failed" if status == "exception" else status
                    write_json(path / "run.json", record)
                    if status == "exception":
                        raise TimeoutError("offline")

                from ML.deep_research.research_module import create_run
                with patch("ML.deep_research.domain_decider.create_run", return_value=domain) as create, patch(
                    "ML.deep_research.domain_decider.run_all", side_effect=finish
                ), patch("ML.deep_research.research_module.create_run", wraps=create_run) as research_create, patch(
                    "ML.deep_research.research_module.run_all", side_effect=FakeFinder().run
                ) as execute, patch("ML.deep_research.research_module.backend.research_run.checkpoint_root") as storage, patch(
                    "ML.deep_research.domain_decider.backend.cli.load_dotenv_key"
                ), patch.dict("os.environ", {"OPENAI_API_KEY": "offline"}), patch(
                    "socket.socket.connect", side_effect=AssertionError("Network blocked")
                ), contextlib.redirect_stdout(io.StringIO()):
                    ns = {}
                    await eval(cell_code(FACT_SHEET_PATH=str(domain / "asset_metadata.md")), ns)
                    storage.assert_called_once()
                    create.assert_called_once()
                    self.assertEqual(calls, ["domain"])
                    if status == "complete":
                        research_create.assert_called_once()
                        self.assertEqual(research_create.call_args.args[0], domain)
                        execute.assert_awaited_once_with(ns["L3_SOURCE_RUN"], retry_failed=True)
                        self.assertEqual(len(list((ns["L3_SOURCE_RUN"] / "sources").glob("*.json"))), 2)
                    else:
                        research_create.assert_not_called()
                        execute.assert_not_awaited()

    async def test_existing_domain_reused_or_resumed_without_new_preparation(self):
        for status in ("complete", "partial"):
            with tempfile.TemporaryDirectory() as tmp:
                run = layer2_input(Path(tmp))
                record = load_json(run / "run.json")
                record["status"] = status
                write_json(run / "run.json", record)

                def finish(path):
                    """Resume a saved operationally incomplete domain fixture."""
                    record["status"] = "complete"
                    write_json(path / "run.json", record)

                with patch("ML.deep_research.domain_decider.create_run", side_effect=AssertionError("No creation")), patch(
                    "ML.deep_research.domain_decider.run_all", side_effect=finish
                ) as domain_execute, patch("ML.deep_research.domain_decider.backend.runner.verify_inputs"), patch(
                    "ML.deep_research.research_module.run_all", new_callable=AsyncMock
                ) as execute, patch("ML.deep_research.research_module.backend.research_run.checkpoint_root"), patch(
                    "ML.deep_research.domain_decider.backend.cli.load_dotenv_key"
                ), patch.dict("os.environ", {"OPENAI_API_KEY": "offline"}), contextlib.redirect_stdout(io.StringIO()):
                    await eval(cell_code(LAYER3_SOURCE_RUN_PATH=str(run)), {})
                    self.assertEqual(domain_execute.call_count, int(status != "complete"))
                    execute.assert_awaited_once()

    async def test_resume_and_upload_only_do_not_create_or_rediscover(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            for upload_only in (False, True):
                with patch("ML.deep_research.domain_decider.create_run", side_effect=AssertionError("No domain")), patch(
                    "ML.deep_research.research_module.create_run", side_effect=AssertionError("No research creation")
                ), patch("ML.deep_research.research_module.upload_documents", new_callable=AsyncMock) as upload, patch(
                    "ML.deep_research.research_module.run_all", new_callable=AsyncMock
                ) as research, patch("ML.deep_research.research_module.backend.research_run.checkpoint_root") as storage, patch(
                    "ML.deep_research.domain_decider.backend.cli.load_dotenv_key"
                ), patch.dict("os.environ", {"OPENAI_API_KEY": "offline"}), contextlib.redirect_stdout(io.StringIO()):
                    await eval(cell_code(LAYER3_RESUME_RUN_PATH=str(run), LAYER3_UPLOAD_ONLY=upload_only,
                                         LAYER3_RESEARCH_CONFIG_PATH="missing", PUBLIC_INPUT_CONFIRMED=False), {})
                    self.assertEqual(upload.await_count, int(upload_only))
                    self.assertEqual(research.await_count, int(not upload_only))
                    self.assertEqual(storage.call_count, int(not upload_only))

    async def test_invalid_selections_and_preflight_never_create_runs(self):
        cases = [({"LAYER3_UPLOAD_ONLY": True}, RuntimeError),
                 ({"LAYER3_SOURCE_RUN_PATH": "one", "LAYER3_RESUME_RUN_PATH": "two"}, RuntimeError),
                 ({"PUBLIC_INPUT_CONFIRMED": False}, ValueError),
                 ({"LAYER3_RESEARCH_CONFIG_PATH": "missing.json"}, OSError),
                 ({"LAYER3_SOURCE_SUGGESTION_PATH": "missing.md"}, OSError)]
        with patch("ML.deep_research.domain_decider.create_run") as domain, patch(
            "ML.deep_research.research_module.create_run"
        ) as research, patch("ML.deep_research.domain_decider.backend.cli.load_dotenv_key"), patch.dict(
            "os.environ", {"OPENAI_API_KEY": "offline"}
        ):
            for overrides, error in cases:
                with self.subTest(overrides=overrides), self.assertRaises(error):
                    await eval(cell_code(**overrides), {})
            with patch("ML.deep_research.research_module.backend.research_run.checkpoint_root", side_effect=RuntimeError("volume")):
                with self.assertRaisesRegex(RuntimeError, "volume"):
                    await eval(cell_code(), {})
            domain.assert_not_called()
            research.assert_not_called()

    def test_one_cell_defaults_and_clean_output(self):
        book = json.loads((REPO_ROOT / "CDI_Layer2_Layer3.ipynb").read_text(encoding="utf-8"))
        self.assertEqual(len(code_cells()), 1)
        cell = next(c for c in book["cells"] if c["cell_type"] == "code")
        self.assertEqual(cell["outputs"], [])
        self.assertIsNone(cell["execution_count"])
        tree = ast.parse(code_cells()[0])
        values = {n.targets[0].id: n.value.value for n in tree.body
                  if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)}
        for name in ("LAYER3_SOURCE_RUN_PATH", "LAYER3_RESUME_RUN_PATH", "LAYER3_PREPARED_RUN_PATH"):
            self.assertEqual(values[name], "")
        self.assertIs(values["LAYER3_UPLOAD_ONLY"], False)
        self.assertNotIn("LAYER4_", code_cells()[0])

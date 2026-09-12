"""Exercise notebook controls offline without allowing downstream research."""

import ast
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ML.deep_research.layer2.backend.settings import REPO_ROOT
from tests.layer3_fixtures import FakeFinder, layer2_input


def code_cells():
    """Read the actual UI cells, not a separate copy of their logic."""
    book = json.loads((REPO_ROOT / "CDI_Layer2_Layer3.ipynb").read_text(encoding="utf-8"))
    return ["".join(cell["source"]) for cell in book["cells"] if cell["cell_type"] == "code"]


class SourceNotebookTests(unittest.IsolatedAsyncioTestCase):
    async def test_layer3_uses_dynamic_input_and_stops_after_sources(self):
        source = code_cells()[1]
        tree = ast.parse(source)
        values = {n.targets[0].id: n.value.value for n in tree.body
                  if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                  and isinstance(n.value, ast.Constant)}
        for name, value in {"WEB_SEARCH_DEPTH": "medium", "WEB_SEARCH_VERBOSITY": "low",
                            "LAYER3_RESUME_RUN_PATH": ""}.items():
            self.assertEqual(values[name], value)
        self.assertIn(values["LAYER3_MODEL_REASONING_EFFORT"], {"low", "medium", "high", "max"})
        self.assertIsInstance(values["LAYER3_SOURCE_RUN_PATH"], str)
        self.assertIsInstance(values["PUBLIC_INPUT_CONFIRMED"], bool)
        self.assertNotIn('globals().get("L2_RUN")', source)
        self.assertNotIn("rglob", source)
        self.assertIs(values["LAYER3_UPLOAD_ONLY"], False)
        # Exercise the dynamic-input path independently of the user's saved controls.
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id == "PUBLIC_INPUT_CONFIRMED":
                    node.value = ast.copy_location(ast.Constant(True), node.value)
                elif node.targets[0].id == "LAYER3_SOURCE_RUN_PATH":
                    node.value = ast.copy_location(ast.Constant(""), node.value)
        code = compile(ast.fix_missing_locations(tree), "Layer 3 notebook", "exec",
                       flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
        with tempfile.TemporaryDirectory() as tmp:
            namespace = {"L2_DYNAMIC_RUN": layer2_input(Path(tmp))}
            fake = FakeFinder()
            with patch("ML.deep_research.layer3.run_all", side_effect=fake.run), patch(
                "ML.deep_research.layer2.backend.cli.load_dotenv_key"
            ), patch.dict("os.environ", {"OPENAI_API_KEY": "offline-test"}), contextlib.redirect_stdout(io.StringIO()):
                await eval(code, namespace)
            self.assertEqual(len(fake.calls), 2)
            self.assertEqual(len(list((namespace["L3_SOURCE_RUN"] / "sources").glob("*.json"))), 2)
            self.assertNotIn("L3_RUN", namespace)

    async def test_upload_only_uses_explicit_existing_run_without_discovery(self):
        from unittest.mock import AsyncMock
        from tests.layer3_fixtures import new_run

        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp))
            for path in (str(run), ""):
                tree = ast.parse(code_cells()[1])
                for node in tree.body:
                    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                        if node.targets[0].id in {"LAYER3_UPLOAD_ONLY", "LAYER3_RESUME_RUN_PATH"}:
                            value = True if node.targets[0].id == "LAYER3_UPLOAD_ONLY" else path
                            node.value = ast.copy_location(ast.Constant(value), node.value)
                code = compile(ast.fix_missing_locations(tree), "Layer 3 upload UI", "exec",
                               flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
                with patch("ML.deep_research.layer3.upload_documents", new_callable=AsyncMock) as upload, patch(
                    "ML.deep_research.layer3.run_all", side_effect=AssertionError("No source calls")
                ), patch("ML.deep_research.layer3.create_run", side_effect=AssertionError("No new run")), patch(
                    "ML.deep_research.layer2.backend.cli.load_dotenv_key"
                ), patch.dict("os.environ", {"OPENAI_API_KEY": "offline-test"}), contextlib.redirect_stdout(io.StringIO()):
                    if path:
                        await eval(code, {})
                        upload.assert_awaited_once()
                    else:
                        with self.assertRaisesRegex(RuntimeError, "Upload-only requires"):
                            await eval(code, {})
                        upload.assert_not_awaited()

    async def test_default_layer4_cell_does_not_even_import_research_execution(self):
        source = code_cells()[2]
        self.assertIn("LAYER4_ENABLED = False", source)
        code = compile(source, "Layer 4 notebook", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
        namespace = {}
        with patch("socket.socket.connect", side_effect=AssertionError("No network")), contextlib.redirect_stdout(io.StringIO()):
            await eval(code, namespace)
        self.assertFalse(namespace["LAYER4_ENABLED"])
        self.assertNotIn("create_layer4_run", namespace)
        self.assertNotIn("run_layer4", namespace)

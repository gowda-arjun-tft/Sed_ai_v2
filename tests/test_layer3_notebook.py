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
    async def test_notebook_full_or_resume_only(self):
        """Execute the actual cell with a fake coordinator, never the model pipeline."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "run.json", {"status": "complete", "phases": {}})
            for resume in ("", str(root)):
                with patch("ML.deep_research.workflow.create_run", return_value=root) as create, patch(
                    "ML.deep_research.workflow.run_all", new_callable=AsyncMock
                ) as execute, contextlib.redirect_stdout(io.StringIO()):
                    await eval(cell_code(RESUME_RUN_PATH=resume, PUBLIC_INPUT_CONFIRMED=True), {})
                    self.assertEqual(create.call_count, int(not resume))
                    execute.assert_awaited_once_with(root, retry_failed=False)
                    if not resume:
                        self.assertTrue(create.call_args.kwargs["stage_settings"]["reasoning_summaries"])

    async def test_retry_requires_explicit_resume(self):
        """No run is created for contradictory retry controls."""
        with patch("ML.deep_research.workflow.create_run") as create:
            with self.assertRaises(ValueError):
                await eval(cell_code(RETRY_FAILED=True), {})
            create.assert_not_called()

    def test_one_cell_defaults_and_clean_output(self):
        """Check the simplified controls while retaining the Docker kernel."""
        book = json.loads((REPO_ROOT / "CDI_Layer2_Layer3.ipynb").read_text(encoding="utf-8"))
        self.assertEqual(len(code_cells()), 1)
        cell = next(c for c in book["cells"] if c["cell_type"] == "code")
        self.assertEqual(cell["outputs"], [])
        self.assertIsNone(cell["execution_count"])
        tree = ast.parse(code_cells()[0])
        values = {n.targets[0].id: n.value.value for n in tree.body
                  if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)}
        self.assertEqual(values["RESUME_RUN_PATH"], "")
        self.assertIs(values["PUBLIC_INPUT_CONFIRMED"], False)
        self.assertIs(values["REASONING_SUMMARIES"], True)
        self.assertNotIn("LAYER3_PREPARED_RUN_PATH", code_cells()[0])
        self.assertNotIn("LAYER3_UPLOAD_ONLY", code_cells()[0])

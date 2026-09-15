"""Exercise the single notebook workflow with no provider or research activity."""

import ast
import asyncio
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from ML.deep_research.domain_decider.backend.fs import write_json
from ML.deep_research.domain_decider.backend.settings import REPO_ROOT


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
                value = ast.Constant(overrides[node.targets[0].id])
                if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id == "Path":
                    value = ast.Call(func=ast.Name(id="Path", ctx=ast.Load()), args=[value], keywords=[])
                node.value = ast.copy_location(value, node.value)
    return compile(ast.fix_missing_locations(tree), "Notebook", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)


class SourceNotebookTests(unittest.IsolatedAsyncioTestCase):
    async def test_five_files_sequential_with_failures_and_fresh_rerun(self):
        """Each file maps to one fresh workflow; local failures never duplicate or stop siblings."""
        for failures in (False, True):
            with self.subTest(failures=failures), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                facts = root / "facts"
                facts.mkdir()
                names = [f"{i}.md" for i in range(1, 6)]
                for name in reversed(names):
                    (facts / name).write_text(name)
                (facts / "ignore.txt").write_text("not a factsheet")
                (facts / "nested.md").mkdir()
                (facts / "nested.md/hidden.md").write_text("not top-level")
                starts, finished, events, settings = [], [], [], []
                mapping, active = {}, 0

                def create(source, **kwargs):
                    """Allocate distinct fixture outputs, with one optional creation failure."""
                    self.assertEqual(active, 0)
                    starts.append(source.name)
                    settings.append(kwargs)
                    events.append(("create", source.name))
                    if failures and source.name == "4.md":
                        raise ValueError("private error must not be printed")
                    run = root / "runs" / str(len(starts))
                    mapping[run] = source.name
                    write_json(run / "run.json", {"status": "created", "phases": {"research_module": "research_module"}})
                    return run

                async def execute(run, **kwargs):
                    """Yield once so overlapping executions would be observable."""
                    nonlocal active
                    active += 1
                    self.assertEqual(active, 1)
                    name = mapping[run]
                    events.append(("start", name))
                    try:
                        await asyncio.sleep(0)
                        status = ("failed" if name == "2.md" else "partial" if name == "3.md" else "complete") if failures else "complete"
                        write_json(run / "run.json", {"status": status, "phases": {"research_module": "research_module"}})
                        write_json(run / "research_module/run.json", {"status": status, "domains": [],
                                   "research": {"factsheet": {"status": "disabled"}}})
                        if status == "failed":
                            raise RuntimeError("private error must not be printed")
                    finally:
                        active -= 1
                        finished.append(name)
                        events.append(("finish", name))

                namespace = {}
                with patch("ML.deep_research.workflow.create_run", side_effect=create), patch(
                    "ML.deep_research.workflow.run_all", side_effect=execute), contextlib.redirect_stdout(io.StringIO()) as output:
                    for _ in range(1 if failures else 2):
                        await eval(cell_code(FACT_SHEETS_DIR=str(facts), RESEARCH_FACTSHEET_ACCESS=False), namespace)
                self.assertEqual(starts, names * (1 if failures else 2))
                self.assertEqual(finished, [n for n in starts if not (failures and n == "4.md")])
                self.assertEqual([r["status"] for r in namespace["BATCH_RESULTS"]],
                                 ["complete", "failed", "partial", "failed", "complete"] if failures else ["complete"] * 5)
                self.assertTrue(all(s == settings[0] for s in settings))
                self.assertFalse(settings[0]["research_factsheet_access"])
                self.assertIn("Factsheet 5/5: 5.md", output.getvalue())
                self.assertIn("RESUME_RUN_PATH:", output.getvalue())
                self.assertNotIn("private error", output.getvalue())
                for i, event in enumerate(events):
                    if event[0] == "start":
                        self.assertEqual(events[i + 1], ("finish", event[1]))

    async def test_cancel_stops_queue_and_empty_selection_creates_nothing(self):
        """Do not swallow cancellation, recurse, or begin paid work for an empty selection."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for directory in (root / "missing", root):
                with patch("ML.deep_research.workflow.create_run") as create:
                    with self.assertRaises(ValueError):
                        await eval(cell_code(FACT_SHEETS_DIR=str(directory)), {})
                    create.assert_not_called()
            for name in ("a.md", "b.md"):
                (root / name).write_text(name)
            for error in (asyncio.CancelledError, KeyboardInterrupt):
                namespace = {}
                with patch("ML.deep_research.workflow.create_run", return_value=root / "run") as create, patch(
                    "ML.deep_research.workflow.run_all", side_effect=error) as execute, contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(error):
                        await eval(cell_code(FACT_SHEETS_DIR=str(root)), namespace)
                    self.assertEqual(create.call_count, 1)
                    self.assertEqual(execute.call_count, 1)
                    self.assertEqual(namespace["BATCH_RESULTS"][0]["status"], "interrupted")

    async def test_notebook_full_or_resume_only(self):
        """Execute the actual cell with a fake coordinator, never the model pipeline."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "run.json", {"status": "complete", "phases": {"research_module": "research_module"}})
            write_json(root / "research_module/run.json", {"status": "complete", "domains": [],
                       "research": {"factsheet": {"status": "disabled"}}})
            facts = root / "facts"
            facts.mkdir()
            (facts / "one.md").write_text("One subject")
            for resume, access in (("", True), ("", False), (str(root), True)):
                with patch("ML.deep_research.workflow.create_run", return_value=root) as create, patch(
                    "ML.deep_research.workflow.run_all", new_callable=AsyncMock
                ) as execute, contextlib.redirect_stdout(io.StringIO()) as output:
                    await eval(cell_code(RESUME_RUN_PATH=resume, PUBLIC_INPUT_CONFIRMED=True,
                                         FACT_SHEETS_DIR=str(facts if not resume else root / "missing"),
                                         RESEARCH_FACTSHEET_ACCESS=access), {})
                    self.assertEqual(create.call_count, int(not resume))
                    execute.assert_awaited_once_with(root, retry_failed=False)
                    self.assertIn("Original factsheet access: disabled (saved)", output.getvalue())
                    if resume:
                        self.assertIn("toggle applies only to new runs", output.getvalue())
                    if not resume:
                        self.assertIs(create.call_args.kwargs["research_factsheet_access"], access)
                        self.assertTrue(create.call_args.kwargs["stage_settings"]["reasoning_summaries"])

    async def test_retry_requires_explicit_resume(self):
        """No run is created for contradictory retry controls."""
        with patch("ML.deep_research.workflow.create_run") as create:
            with self.assertRaises(ValueError):
                await eval(cell_code(RETRY_FAILED=True), {})
            create.assert_not_called()

    def test_one_cell_editable_controls_and_preserved_output(self):
        """Validate editable controls without requiring deletion of saved user output."""
        book = json.loads((REPO_ROOT / "CDI_Layer2_Layer3.ipynb").read_text(encoding="utf-8"))
        self.assertEqual(len(code_cells()), 1)
        cell = next(c for c in book["cells"] if c["cell_type"] == "code")
        self.assertIsInstance(cell["outputs"], list)
        tree = ast.parse(code_cells()[0])
        values = {n.targets[0].id: n.value.value for n in tree.body
                  if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)}
        self.assertIsInstance(values["RESUME_RUN_PATH"], str)
        self.assertIsInstance(values["PUBLIC_INPUT_CONFIRMED"], bool)
        self.assertIsInstance(values["REASONING_SUMMARIES"], bool)
        self.assertIsInstance(values["RESEARCH_FACTSHEET_ACCESS"], bool)
        self.assertNotIn("LAYER3_PREPARED_RUN_PATH", code_cells()[0])
        self.assertNotIn("LAYER3_UPLOAD_ONLY", code_cells()[0])

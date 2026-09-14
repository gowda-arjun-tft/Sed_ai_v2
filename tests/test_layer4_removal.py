"""Removal boundaries without executing research or changing historical artifacts."""

import ast
import importlib.util
import json
import unittest

from ML.deep_research.domain_decider.backend.settings import REPO_ROOT


class Layer4RemovalTests(unittest.TestCase):
    def test_removed_package_and_entrypoints_are_absent(self):
        """Neither Python, notebook nor PowerShell can dispatch the removed workflow."""
        self.assertIsNone(importlib.util.find_spec("ML.deep_research.layer4"))
        script = (REPO_ROOT / "run.ps1").read_text(encoding="utf-8-sig")
        self.assertTrue(script.startswith("[CmdletBinding()]"))
        for retired in ("ExternalResearch", "ResumeL4", "ML.deep_research.layer4"):
            self.assertNotIn(retired, script)
        notebook = json.loads((REPO_ROOT / "CDI_Layer2_Layer3.ipynb").read_text(encoding="utf-8"))
        cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
        self.assertEqual(len(cells), 1)
        for cell in cells:
            code = "".join(cell["source"])
            self.assertNotIn("LAYER4_", code)
            compile(code, "notebook", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)

    def test_retained_modules_do_not_import_deleted_modules(self):
        """Import discovery also covers helpers formerly located outside Layer 4."""
        retired = {"llm", "memory", "mission", "prompts", "research_tools", "usage", "legacy_input"}
        for name in retired:
            self.assertFalse((REPO_ROOT / "ML/deep_research/research_module" / f"{name}.py").exists())
        for path in (REPO_ROOT / "ML").rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    self.assertNotIn("layer4", (node.module or "").split("."), str(path))
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertNotIn("layer4", alias.name.split("."), str(path))

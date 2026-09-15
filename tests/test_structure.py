import ast
import importlib
import json
import pkgutil
import unittest

import ML.deep_research.domain_decider as layer2
import ML.deep_research.research_module as layer3
from ML.deep_research.domain_decider.backend.settings import REPO_ROOT


class StructureTests(unittest.TestCase):
    def test_demo_notebook_has_one_compilable_cell(self):
        notebook_path = REPO_ROOT / "CDI_Layer2_Layer3.ipynb"
        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
        cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
        self.assertEqual(len(cells), 1)
        self.assertEqual(notebook["metadata"]["kernelspec"]["display_name"], "SedAI Docker — Python 3.12")
        source = "".join(cells[0]["source"])
        for control in ("FACT_SHEET_PATH", "STAGE_SETTINGS", "REASONING_SUMMARIES",
                        "RESUME_RUN_PATH", "PUBLIC_INPUT_CONFIRMED"):
            self.assertIn(control, source)
        self.assertIn("await run_all(FULL_RUN", source)
        self.assertIn("ML.deep_research.workflow", source)
        compile(source, str(notebook_path), "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)

    def test_development_uses_original_workspace_without_hidden_run_volumes(self):
        import yaml

        compose_path = REPO_ROOT / "compose.yaml"
        if not compose_path.exists():
            self.skipTest("Compose is outside the runtime-only image")
        compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
        dev = compose["services"]["dev"]
        self.assertEqual(dev["volumes"], [".:/app", "sedai-research-checkpoints:/var/lib/sedai/research-checkpoints"])
        self.assertEqual(dev["environment"]["SEDAI_RESEARCH_CHECKPOINT_DIR"], "/var/lib/sedai/research-checkpoints")
        self.assertEqual(dev["command"], ["sleep", "infinity"])
        config = json.loads((REPO_ROOT / ".devcontainer/devcontainer.json").read_text())
        self.assertEqual(config["service"], "dev")
        self.assertEqual(config["runServices"], ["dev"])
        self.assertEqual(config["workspaceFolder"], "/app")
        self.assertEqual(config["remoteUser"], "appuser")
        self.assertEqual(config["customizations"]["vscode"]["settings"]["python.defaultInterpreterPath"],
                         "/usr/local/bin/python")
        self.assertNotIn(".:/app", compose["services"]["notebook"]["volumes"])
        self.assertFalse((REPO_ROOT / "docker/prepare_notebook.py").exists())

    def test_layer2_layout_public_exports_and_industry_neutral_code(self):
        from ML.deep_research.domain_decider.backend import settings
        from ML.deep_research.domain_decider.backend.create_run import create_run
        from ML.deep_research.domain_decider.backend.runner import run_all
        domain_names = ("Asset Integrity, Systems & Operational Resilience",
                        "Finance, Debt & Macro Transmission")

        root = settings.MODULE_DIR
        self.assertEqual(root, REPO_ROOT / "ML" / "deep_research" / "domain_decider")
        self.assertEqual(settings.PROMPTS_DIR, root / "ML" / "prompts")
        self.assertEqual(settings.DOMAIN_PLUGIN_PATH, REPO_ROOT / "inputs/plugins/real_estate.md")
        self.assertTrue(settings.DOMAIN_PLUGIN_PATH.is_file())
        self.assertEqual({p.name for p in root.glob("*.py")}, {"__init__.py", "__main__.py"})
        self.assertEqual({p.name for p in settings.PROMPTS_DIR.glob("*.md")}, set(settings.PROMPT_FILES.values()))
        self.assertEqual(tuple(settings.PROMPT_FILES), settings.STAGES)
        self.assertEqual(len(set(settings.PROMPT_FILES.values())), len(settings.STAGES))
        self.assertIs(layer2.create_run, create_run)
        self.assertIs(layer2.run_all, run_all)
        active = list(root.rglob("*.py")) + list(settings.PROMPTS_DIR.glob("*.md"))
        for path in active:
            text = path.read_text(encoding="utf-8")
            for name in domain_names:
                self.assertNotIn(name, text, str(path))
        self.assertFalse(hasattr(settings, "AGENT_NAMES"))
        self.assertFalse(hasattr(settings, "PLANNER_PATH"))
        self.assertFalse((root / "prompts" / "chunk_router.md").exists())
        self.assertFalse((root / "prompts" / "planner_prompt.md").exists())
        template = (REPO_ROOT / "inputs" / "requirement.md").read_text(encoding="utf-8")
        for heading in ("Objectives", "Priorities", "Expanded research responsibilities", "Geography", "Time horizon"):
            self.assertIn("## " + heading, template)

    def test_all_package_modules_import_without_model_calls(self):
        for retired in ("layer2", "layer3"):
            self.assertIsNone(importlib.util.find_spec("ML.deep_research." + retired))
        for package in (layer2, layer3):
            prefix = f"{package.__name__}."
            for module in pkgutil.walk_packages(package.__path__, prefix):
                importlib.import_module(module.name)

    def test_layer2_production_functions_have_docstrings(self):
        root = REPO_ROOT / "ML" / "deep_research" / "domain_decider"
        missing = []
        total_lines = 0
        for path in sorted(root.rglob("*.py")):
            source = path.read_text(encoding="utf-8-sig")
            total_lines += len(source.splitlines())
            tree = ast.parse(source, filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if ast.get_docstring(node) is None:
                        missing.append(f"{path.name}:{node.lineno}:{node.name}")
        self.assertEqual(missing, [])
        self.assertGreater(total_lines, 0)
        self.assertLess(total_lines, 2177)  # inspected pre-schema-8 production baseline

    def test_retired_layer3_phase_controller_is_gone(self):
        root = REPO_ROOT / "ML" / "deep_research" / "research_module"
        retired = [
            "aggregator_runner.py",
            "calculation_tool.py",
            "question_files.py",
            "register.py",
            "sessions.py",
            "providers/fixture.py",
            "pipeline/run_researchers.py",
            "pipeline/run_second_round.py",
            "pipeline/state.py",
            "pipeline/write_answers.py",
            "pipeline/write_questions.py",
        ]
        self.assertEqual([name for name in retired if (root / name).exists()], [])

    def test_layer3_layout_and_public_exports(self):
        from ML.deep_research.research_module.backend import settings
        from ML.deep_research.research_module.backend.cli import run_all
        from ML.deep_research.research_module.backend.create_run import create_run
        from ML.deep_research.research_module.backend.document_uploads import upload_documents
        from ML.deep_research.research_module.backend.research_run import create_research_run
        from ML.deep_research.research_module.backend.run_checks import run_checks

        root = REPO_ROOT / "ML" / "deep_research" / "research_module"
        self.assertEqual({path.name for path in root.glob("*.py")}, {"__init__.py", "__main__.py"})
        self.assertEqual(settings.PROMPTS_DIR, root / "ML" / "prompts")
        self.assertEqual(
            {path.name for path in settings.PROMPTS_DIR.glob("*.md")},
            {"source_finder.md", "domain_research.md", "research_summary.md", "read_document.md"},
        )
        self.assertIs(layer3.create_run, create_run)
        self.assertIs(layer3.create_research_run, create_research_run)
        self.assertIs(layer3.run_all, run_all)
        self.assertIs(layer3.run_checks, run_checks)
        self.assertIs(layer3.upload_documents, upload_documents)
        for retired in ("pipeline", "prompts", "providers"):
            self.assertEqual(list((root / retired).glob("*.py")), [])
            self.assertEqual(list((root / retired).glob("*.md")), [])

    def test_executable_source_files_do_not_exceed_350_lines(self):
        violations = []
        for path in REPO_ROOT.rglob("*"):
            if path.suffix not in {".py", ".ps1"} or not path.is_file():
                continue
            relative = path.relative_to(REPO_ROOT)
            if any(
                part in {".venv", "runs", "outputs", "node_modules", "__pycache__"}
                for part in relative.parts
            ):
                continue
            lines = len(path.read_text(encoding="utf-8-sig").splitlines())
            if lines > 350:
                violations.append(f"{relative}: {lines}")
        self.assertEqual(violations, [], "Source files over 350 lines: " + ", ".join(violations))


if __name__ == "__main__":
    unittest.main()

import ast
import importlib
import json
import pkgutil
import unittest

import ML.deep_research.layer2 as layer2
import ML.deep_research.layer3 as layer3
import ML.deep_research.layer4 as layer4
from ML.deep_research.layer2.backend.settings import REPO_ROOT
from tests.common import PLANNER_PATH


class StructureTests(unittest.TestCase):
    def test_demo_notebook_has_three_compilable_cells(self):
        notebook_path = REPO_ROOT / "CDI_Layer2_Layer3.ipynb"
        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
        cells = [cell for cell in notebook["cells"] if cell["cell_type"] == "code"]
        notebook_text = "\n".join(
            "".join(cell.get("source", [])) for cell in notebook["cells"]
        )
        self.assertEqual(len(cells), 3)
        self.assertIn(notebook["metadata"]["kernelspec"]["display_name"],
                      {"compute", "Python 3", "SedAI Docker — Python 3.12"})
        for control in (
            "FACT_SHEET_PATH",
            "LAYER2_REASONING_EFFORT",
            "PUBLIC_INPUT_CONFIRMED",
            "LAYER3_SOURCE_RUN_PATH",
            "LAYER3_MODEL_REASONING_EFFORT",
            "WEB_SEARCH_DEPTH",
            "WEB_SEARCH_VERBOSITY",
            "LAYER4_SOURCE_RUN_PATH",
            "LAYER4_MODEL_REASONING_EFFORT",
            "LAYER4_WEB_SEARCH_DEPTH",
            "LAYER4_WEB_SEARCH_VERBOSITY",
            "LAYER4_PUBLIC_INPUT_CONFIRMED",
            "LAYER4_RETRY_FAILED",
        ):
            self.assertIn(control, notebook_text)
        self.assertRegex(
            notebook_text,
            r'LAYER4_SOURCE_RUN_PATH = r?"runs[/\\][^"\r\n]+[/\\]L3_[^"\r\n]+"',
        )
        self.assertRegex(
            notebook_text,
            r'LAYER4_MODEL_REASONING_EFFORT = "(?:low|medium|high|max)"',
        )
        for control in ("LAYER4_WEB_SEARCH_DEPTH", "LAYER4_WEB_SEARCH_VERBOSITY"):
            self.assertRegex(
                notebook_text, rf'{control} = "(?:low|medium|high)"'
            )
        self.assertIn(
            'candidate.get("reasoning_effort") == LAYER4_MODEL_REASONING_EFFORT',
            notebook_text,
        )
        self.assertIn(
            'search_options.get("context_size") == LAYER4_WEB_SEARCH_DEPTH',
            notebook_text,
        )
        self.assertIn(
            'search_options.get("verbosity") == LAYER4_WEB_SEARCH_VERBOSITY',
            notebook_text,
        )
        self.assertIn("create_layer4_run", notebook_text)
        self.assertIn("run_layer4", notebook_text)
        self.assertNotIn("Source Scout", notebook_text)
        self.assertNotIn("clarification", notebook_text.casefold())
        layer2_text = "".join(cells[0]["source"])
        self.assertRegex(
            layer2_text,
            r'FACT_SHEET_PATH = Path\("inputs"\) / "[^"\r\n]+\.md"',
        )
        self.assertIn('print("Layer 2: running")', layer2_text)
        self.assertIn("['status']", layer2_text)
        self.assertIn("asyncio.to_thread(run_layer2, L2_DYNAMIC_RUN)", layer2_text)
        self.assertIn("LAYER2_DOMAIN_PLUGIN", layer2_text)
        self.assertIn("LAYER2_REQUIREMENTS", layer2_text)
        self.assertIn("PUBLIC_INPUT_CONFIRMED = True", layer2_text)
        for control in ("WEB_SEARCH_DEPTH", "WEB_SEARCH_VERBOSITY"):
            self.assertRegex(layer2_text, rf'{control} = "(?:low|medium|high)"')
        self.assertIn("web_search_context_size=WEB_SEARCH_DEPTH", layer2_text)
        self.assertIn("web_search_verbosity=WEB_SEARCH_VERBOSITY", layer2_text)
        self.assertIn("public_input_confirmed=PUBLIC_INPUT_CONFIRMED", layer2_text)
        self.assertIn('LAYER2_REQUIREMENTS = Path("inputs") / "requirement.md"', layer2_text)
        # Only Layer 2 path controls are in scope; historical Layer 3/4 cells stay unchanged.
        self.assertNotIn("inputs\\\\", layer2_text)
        self.assertNotIn("runs\\\\", layer2_text)
        self.assertIn("from ML.deep_research.layer2 import create_run", layer2_text)
        self.assertIn("from ML.deep_research.layer2 import run_all", layer2_text)
        self.assertNotIn("L2_RUN =", layer2_text)
        self.assertIn("run.log", layer2_text)
        for retired in (
            "PREVIEW_MISSION",
            "Recorded Layer 2 usage",
            "Mission preview",
            "display(JSON",
            "display(Markdown",
            "clear_output",
            "L2_TASK",
            "while not",
            "summary =",
        ):
            self.assertNotIn(retired, layer2_text)
        for cell in cells:
            compile(
                "".join(cell["source"]),
                str(notebook_path),
                "exec",
                flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT,
            )

    def test_planner_is_only_a_historical_fixture(self):
        self.assertTrue(PLANNER_PATH.is_file())
        self.assertEqual(PLANNER_PATH.parent, REPO_ROOT / "tests" / "fixtures")
        self.assertFalse((REPO_ROOT / "planner_prompt.md").exists())

    def test_development_uses_original_workspace_without_hidden_run_volumes(self):
        import yaml

        compose_path = REPO_ROOT / "compose.yaml"
        if not compose_path.exists():
            self.skipTest("Compose is outside the runtime-only image")
        compose = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
        dev = compose["services"]["dev"]
        self.assertEqual(dev["volumes"], [".:/app"])
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
        from ML.deep_research.layer2.backend import settings
        from ML.deep_research.layer2.backend.create_run import create_run
        from ML.deep_research.layer2.backend.runner import run_all
        from ML.deep_research.layer3.settings import AGENT_NAMES

        root = settings.MODULE_DIR
        self.assertEqual(root, REPO_ROOT / "ML" / "deep_research" / "layer2")
        self.assertEqual(settings.PROMPTS_DIR, root / "ML" / "prompts")
        self.assertEqual(settings.DOMAIN_PLUGIN_PATH, root / "plugins" / "real_estate.md")
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
            for name in AGENT_NAMES:
                self.assertNotIn(name, text, str(path))
        self.assertFalse(hasattr(settings, "AGENT_NAMES"))
        self.assertFalse(hasattr(settings, "PLANNER_PATH"))
        self.assertFalse((root / "prompts" / "chunk_router.md").exists())
        self.assertFalse((root / "prompts" / "planner_prompt.md").exists())
        template = (REPO_ROOT / "inputs" / "requirement.md").read_text(encoding="utf-8")
        for heading in ("Objectives", "Priorities", "Expanded research responsibilities", "Geography", "Time horizon"):
            self.assertIn("## " + heading, template)

    def test_all_package_modules_import_without_model_calls(self):
        for package in (layer2, layer3, layer4):
            prefix = f"{package.__name__}."
            for module in pkgutil.walk_packages(package.__path__, prefix):
                importlib.import_module(module.name)

    def test_layer2_production_functions_have_docstrings(self):
        root = REPO_ROOT / "ML" / "deep_research" / "layer2"
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
        root = REPO_ROOT / "ML" / "deep_research" / "layer3"
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

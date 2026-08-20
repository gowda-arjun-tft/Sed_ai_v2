import importlib
import pkgutil
import unittest

import ML.deep_research.layer2 as layer2
import ML.deep_research.layer3 as layer3
from ML.deep_research.layer2.settings import PLANNER_PATH, REPO_ROOT


class StructureTests(unittest.TestCase):
    def test_planner_has_one_authoritative_location(self):
        self.assertTrue(PLANNER_PATH.is_file())
        self.assertFalse((REPO_ROOT / "planner_prompt.md").exists())

    def test_all_package_modules_import_without_model_calls(self):
        for package in (layer2, layer3):
            prefix = f"{package.__name__}."
            for module in pkgutil.walk_packages(package.__path__, prefix):
                importlib.import_module(module.name)

    def test_executable_source_files_do_not_exceed_350_lines(self):
        violations = []
        for path in REPO_ROOT.rglob("*"):
            if path.suffix not in {".py", ".ps1"} or not path.is_file():
                continue
            relative = path.relative_to(REPO_ROOT)
            if any(part in {".venv", "runs", "__pycache__"} for part in relative.parts):
                continue
            lines = len(path.read_text(encoding="utf-8-sig").splitlines())
            if lines > 350:
                violations.append(f"{relative}: {lines}")
        self.assertEqual(violations, [], "Source files over 350 lines: " + ", ".join(violations))


if __name__ == "__main__":
    unittest.main()

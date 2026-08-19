import tempfile
import unittest
from pathlib import Path

from ML.deep_research.layer2.cli import main
from ML.deep_research.layer2.pipeline.run_checks import run_checks

from tests.common import create_complete_run


class FinalCheckTests(unittest.TestCase):
    def test_checks_accept_a_complete_exact_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            checks = run_checks(create_complete_run(Path(temporary)))
            self.assertEqual(sum(ok for _, _, ok, _ in checks), 19)

    def test_completed_json_run_remains_checkable(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = create_complete_run(Path(temporary))
            self.assertEqual(main(["--check-only", str(run_dir)]), 0)


if __name__ == "__main__":
    unittest.main()

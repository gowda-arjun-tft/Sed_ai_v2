import tempfile
import unittest
from pathlib import Path

from tests.layer2_fixtures import FakeStages, new_run


class LoggingTests(unittest.TestCase):
    def test_one_append_only_log_no_evidence_or_duplicate_handlers(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = new_run(Path(tmp), text="PRIVATE_SOURCE_SENTINEL")
            fake = FakeStages()
            fake.run(run)
            first = (run / "run.log").read_text(encoding="utf-8")
            fake.run(run)
            second = (run / "run.log").read_text(encoding="utf-8")
            self.assertTrue(second.startswith(first))
            self.assertEqual(second.count("run_started"), 1)
            self.assertEqual(second.count("run_resumed"), 1)
            self.assertNotIn("PRIVATE_SOURCE_SENTINEL", second)
            self.assertNotIn("offline-test", second)
            self.assertIn("job_complete", second)
            self.assertIn("frozen_policy", second)

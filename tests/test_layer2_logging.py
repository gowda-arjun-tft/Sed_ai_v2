import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ML.deep_research.layer2.agent import Layer2Response
from ML.deep_research.layer2.create_run import create_run
from ML.deep_research.layer2.runner import run_all
from ML.deep_research.layer2.settings import PLANNER_PATH
from tests.common import NativeBatchGraph


class Layer2LoggingTests(unittest.TestCase):
    def test_log_records_operations_without_run_content_or_secrets(self):
        class Graph(NativeBatchGraph):
            async def ainvoke(self, _value, **_kwargs):
                return {
                    "structured_response": Layer2Response(
                        root={"private-response-marker": True}
                    )
                }

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "fact_sheet.md"
            source.write_text("private-source-marker", encoding="utf-8")
            run_dir = create_run(source, PLANNER_PATH, root / "runs")
            with (
                patch.dict("os.environ", {"OPENAI_API_KEY": "private-api-key"}),
                patch(
                    "ML.deep_research.layer2.runner.split_fact_sheet",
                    return_value=["private-source-marker"],
                ),
                patch(
                    "ML.deep_research.layer2.runner.create_chunk_agent",
                    return_value=Graph(),
                ),
            ):
                run_all(run_dir)
                run_all(run_dir)
            log = (run_dir / "run.log").read_text(encoding="utf-8")

        for expected in (
            "run_started",
            "run_resumed",
            "strategy=fixed_token_windows",
            "size_tokens=60000",
            "overlap_tokens=10000",
            "stride_tokens=50000",
            "chunk_scheduled index=1 attempt=1",
            "chunk_completed index=1 attempt=1",
            "contexts_published",
            "run_complete",
        ):
            self.assertIn(expected, log)
        for private in (
            "private-source-marker",
            "private-response-marker",
            "private-api-key",
        ):
            self.assertNotIn(private, log)


if __name__ == "__main__":
    unittest.main()

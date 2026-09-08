import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from ML.deep_research.layer2.backend.usage import UsageCallback, summarize_usage


class UsageRecordTests(unittest.TestCase):
    def test_concurrent_callback_records_and_sums_usage(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            callback = UsageCallback(run_dir, "chunk-0001")
            run_id = uuid4()
            callback.on_chat_model_start({}, [], run_id=run_id, metadata={})
            message = SimpleNamespace(
                name=None,
                usage_metadata={
                    "input_tokens": 1200,
                    "output_tokens": 300,
                    "total_tokens": 1500,
                    "input_token_details": {"cache_read": 400},
                    "output_token_details": {"reasoning": 200},
                },
            )
            callback.on_llm_end(
                SimpleNamespace(generations=[[SimpleNamespace(message=message)]]),
                run_id=run_id,
            )
            rows = [
                json.loads(line)
                for line in (run_dir / "usage.jsonl").read_text().splitlines()
            ]
            summary = summarize_usage(run_dir)
        self.assertEqual(rows[0]["thread_id"], "chunk-0001")
        self.assertEqual(summary["input_tokens"], 1200)
        self.assertEqual(summary["reasoning_output_tokens"], 200)

    def test_malformed_usage_line_is_ignored(self):
        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            (run_dir / "usage.jsonl").write_text(
                'not json\n{"input_tokens": 12, "output_tokens": 3}\n',
                encoding="utf-8",
            )
            summary = summarize_usage(run_dir)
        self.assertEqual(summary["model_calls"], 1)
        self.assertEqual(summary["input_tokens"], 12)


if __name__ == "__main__":
    unittest.main()

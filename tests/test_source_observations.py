"""Source encoding, byte boundaries and access observations with no network activity."""

import io
import json
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError

from ML.deep_research.research_module.ML.providers.openai_search import _fetch, _hits, encoded_url, access_failure, SourceSizeError
from ML.deep_research.research_module.backend.access_audit import audit_access
from ML.deep_research.research_module.backend.research_run import research_policy
from ML.deep_research.domain_decider.backend.tracing import event, private_json, reasoning_summaries, LOGICAL_CALL


class SourceObservationTests(unittest.TestCase):
    def test_unicode_components_preserve_escapes_and_queries(self):
        """Encode the actual URL rather than guessing an ASCII spelling."""
        with patch("ML.deep_research.research_module.ML.providers.openai_search.validate_public_url") as validate:
            original = "https://example.org/Straße/Prüfung%20A?q=Fläche%20B&name=日+test#part"
            expected = "https://example.org/Stra%C3%9Fe/Pr%C3%BCfung%20A?q=Fl%C3%A4che%20B&name=%E6%97%A5+test"
            self.assertEqual(encoded_url(original), expected)
            self.assertEqual(encoded_url(expected), expected)
            validate.assert_any_call(expected)
        import httpx
        # Document downloads already use HTTPX's native Unicode encoding; no second encoder needed.
        self.assertEqual(str(httpx.Request("GET", original.split("#")[0]).url), expected)

    def test_fifty_mib_policy_and_bounded_actual_reads(self):
        """Validate the exact new allowance and both header/stream rejection paths."""
        policy = research_policy(call_limits={"maximum_calls": 80, "wrap_up_after": 60, "finalize_after": 70})
        self.assertEqual(policy["webpage_max_bytes"], 52_428_800)
        for declared, body, fails in (("9", b"", True), (None, b"x" * 9, True), (None, b"x" * 8, False)):
            response = MagicMock()
            response.headers = Message()
            response.headers["Content-Type"] = "text/plain; charset=utf-8"
            if declared:
                response.headers["Content-Length"] = declared
            response.read.side_effect = io.BytesIO(body).read
            response.geturl.return_value = "https://example.org/file"
            opener = MagicMock()
            opener.open.return_value.__enter__.return_value = response
            with patch("ML.deep_research.research_module.ML.providers.openai_search.validate_public_url"), patch(
                "ML.deep_research.research_module.ML.providers.openai_search.urllib.request.build_opener", return_value=opener):
                if fails:
                    with self.assertRaises(SourceSizeError):
                        _fetch("https://example.org/file", 8)
                else:
                    self.assertEqual(_fetch("https://example.org/file", 8).body, body)
                self.assertTrue(all(call.args[0] <= 9 for call in response.read.call_args_list))

    def test_merge_enriches_without_reordering_or_inventing(self):
        """An action-only URL is enriched by later citation records, never overwritten wholesale."""
        payload = {"output": [{"action": {"sources": [{"url": "https://example.org/a"},
                    {"url": "https://example.org/b", "title": "B"}]}},
                    {"content": [{"text": "Supplied snippet", "annotations": [{"type": "url_citation",
                     "url": "https://example.org/a", "title": "Actual A"}]}]}]}
        response = SimpleNamespace(model_dump=lambda **kwargs: payload)
        hits = _hits(response)
        self.assertEqual([hit.url for hit in hits], ["https://example.org/a", "https://example.org/b"])
        self.assertEqual((hits[0].title, hits[0].snippet), ("Actual A", "Supplied snippet"))
        self.assertEqual(hits[1].snippet, "")

    def test_access_audit_preserves_duplicates_and_does_not_infer_readability(self):
        """A recorded open is evidence of an action only; hidden provider actions remain unknown."""
        raw = '{"sources":[{"url":"https://example.org/a","access":"readable"},{"url":"https://example.org/a"},{"url":"https://example.org/b"}]}'
        blocks = [{"type": "web_search_call", "id": "call1", "action": {"type": "open_page", "url": "https://example.org/a"}}]
        audit = audit_access(raw, blocks)
        self.assertEqual(len(audit["observations"]), 3)
        self.assertEqual(audit["observations"][0]["observation"], "explicit_open_recorded")
        self.assertEqual(audit["observations"][1]["open_positions"], [0])
        self.assertEqual(audit["observations"][2]["observation"], "open_evidence_unavailable")
        self.assertIn('"access":"readable"', raw)
        self.assertEqual(access_failure(HTTPError("https://example.org", 404, "private", {}, None))["kind"], "missing_endpoint")

    def test_private_timeline_correlates_calls_and_redacts_key(self):
        """Provider summaries remain separate from report text; unavailable summaries are explicit."""
        with tempfile.TemporaryDirectory() as directory, patch.dict("os.environ", {"OPENAI_API_KEY": "secret-fixture-key"}):
            root = Path(directory)
            token = LOGICAL_CALL.set({"number": 2, "thread": "fixture"})
            try:
                event(root, "tool_returned", reference="secret-fixture-key")
            finally:
                LOGICAL_CALL.reset(token)
            rows = [json.loads(line) for line in (root / "events.jsonl").read_text().splitlines()]
            self.assertEqual(rows[0]["logical_call"]["number"], 2)
            self.assertNotIn("secret-fixture-key", (root / "events.jsonl").read_text())
            reasoning_summaries(root / "summary.json", {"output": [{"type": "reasoning", "summary": [{"type": "summary_text", "text": "Observed summary"}]}]})
            self.assertTrue(json.loads((root / "summary.json").read_text())["available"])

    def test_unusual_actions_remain_observations_and_save_once(self):
        """Malformed action metadata cannot grade or resend an otherwise completed response."""
        from langchain_core.messages import AIMessage
        from ML.deep_research.research_module.ML.source_finder import save_response
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = {"response_path": "_internal/response.md", "request_id": "request-fixture"}
            message = AIMessage(content='{"sources":[]}', additional_kwargs={"tool_outputs": [
                {"type": "web_search_call", "action": {"type": ["unexpected"]}},
                {"type": "web_search_call", "action": "unconventional"}]})
            save_response(root, entry, message)
            self.assertEqual(entry["status"], "complete")
            self.assertEqual(entry["web_actions"], {"unknown": 2})
            self.assertEqual((root / entry["response_path"]).read_text(), message.text)
            events = [json.loads(line) for line in (root / "_internal/events.jsonl").read_text().splitlines()]
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["request_id"], "request-fixture")

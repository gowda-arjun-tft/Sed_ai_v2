"""Shared Deep Agents profile regression used by the active Layer 3 harness."""

import unittest


class Layer3HarnessSurfaceTests(unittest.TestCase):
    def test_implicit_summarization_and_tool_call_repair_are_disabled(self):
        """Explicit research memory must not re-enable implicit repair or compaction."""
        from deepagents.profiles.harness.harness_profiles import _get_harness_profile
        from ML.deep_research.domain_decider.ML.harness import configure_harness
        from ML.deep_research.domain_decider.backend.settings import MODEL_SPEC

        configure_harness()
        profile = _get_harness_profile(MODEL_SPEC)
        self.assertEqual(
            profile.excluded_middleware,
            frozenset({"SummarizationMiddleware", "PatchToolCallsMiddleware"}),
        )

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from ML.deep_research.layer2.planner import load_planner
from ML.deep_research.layer2.settings import PLANNER_PATH
from ML.deep_research.layer3.prompts import (
    domain_message,
    domain_system_prompt,
    review_message,
    synthesis_message,
)
from ML.deep_research.layer3.settings import DOMAIN_NAMES, MODULE_DIR


class Layer3PromptContractTests(unittest.TestCase):
    def test_domain_prompt_is_finite_outcome_first_and_append_only(self):
        shared = (MODULE_DIR / "prompts" / "shared_rules.md").read_text(encoding="utf-8")
        facets = (MODULE_DIR / "prompts" / "five_questions.md").read_text(
            encoding="utf-8"
        )
        combined = f"{shared}\n{facets}"
        for status in ("supported", "inference", "unknown", "immaterial"):
            self.assertIn(f"`{status}`", combined)
        self.assertIn("append_report(fragment_id, markdown)", combined)
        self.assertIn("snippets", combined)
        self.assertIn("Unknown is a completed finding", combined)
        self.assertIn("**Decision finding:**", facets)
        self.assertNotIn("evaluate every result", combined.lower())
        self.assertNotIn("evidence saturation", combined.lower())
        for forbidden in (
            "model turn limit",
            "search limit",
            "token limit",
            "source limit",
            "report limit",
        ):
            self.assertNotIn(forbidden, combined.lower())

    def test_assignment_boundaries_are_only_in_the_stable_system_prompt(self):
        _, definitions = load_planner(PLANNER_PATH)
        definition = definitions[0]
        assignment = {
            "name": definition["name"],
            "mission": {
                "agent": definition["name"],
                "mission": "Establish the property-specific position.",
                "context": [],
            },
            "boundaries": {
                "mandate": definition["mandate"],
                "handoffs": definition["handoffs"],
            },
        }
        message = domain_message(assignment, batch=0)

        with tempfile.TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            prompt_dir = run_dir / "inputs" / "prompts"
            prompt_dir.mkdir(parents=True)
            shutil.copy2(PLANNER_PATH, run_dir / "inputs" / "planner_prompt.md")
            for name in ("shared_rules.md", "five_questions.md"):
                shutil.copy2(MODULE_DIR / "prompts" / name, prompt_dir / name)
            system = domain_system_prompt(run_dir, definition["name"])

        self.assertIn(definition["mandate"], system)
        self.assertNotIn(definition["mandate"], message)
        for handoff in definition["handoffs"]:
            self.assertIn(handoff, system)
            self.assertNotIn(handoff, message)

    def test_review_and_synthesis_are_single_pass_with_discoverable_paths(self):
        review = review_message()
        synthesis = synthesis_message()
        for domain in DOMAIN_NAMES:
            from ML.deep_research.layer2.fs import slug

            path = f"/domains/{slug(domain)}.md"
            self.assertIn(path, review)
            self.assertIn(path, synthesis)
        self.assertIn("once", review)
        self.assertIn("one optional batch", review)
        self.assertIn("/review.md", synthesis)


if __name__ == "__main__":
    unittest.main()

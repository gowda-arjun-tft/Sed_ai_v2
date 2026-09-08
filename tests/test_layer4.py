from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ML.deep_research.layer2.backend.fs import load_json, read_text, slug, write_json
from ML.deep_research.layer3.settings import DOMAIN_NAMES
from ML.deep_research.layer4.create_run import create_run
from ML.deep_research.layer4.cli import _parser, main
from ML.deep_research.layer4.llm import (
    create_candidate_harness,
    create_external_researcher_harness,
    create_internal_harness,
    create_synthesis_harness,
)
from ML.deep_research.layer4.prompts import (
    candidate_message,
    candidate_system_prompt,
    internal_message,
    internal_system_prompt,
    researcher_message,
    researcher_system_prompt,
    synthesis_message,
    synthesis_system_prompt,
)
from ML.deep_research.layer4.settings import (
    HARNESS_NAME,
    LAYER3_HARNESS_NAME,
    LAYER3_SCHEMA_VERSION,
    MISSING_EXTERNAL_REPORT,
    MISSING_LAYER3_REPORT,
    SCHEMA_VERSION,
)
from tests.common import create_complete_l3_run


def _new_l4(root: Path) -> tuple[Path, Path]:
    l3_run = create_complete_l3_run(root)
    return l3_run, create_run(l3_run, public_input_confirmed=True)


class Layer4RunTests(unittest.TestCase):
    def test_source_layer3_contract_is_frozen_for_layer4_schema_two(self):
        self.assertEqual(SCHEMA_VERSION, 2)
        self.assertEqual(LAYER3_SCHEMA_VERSION, 8)
        self.assertEqual(LAYER3_HARNESS_NAME, "domain_plain_research_direct_output")

    def test_run_snapshots_layer3_without_mutating_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            l3_run = create_complete_l3_run(root)
            before = {
                path.relative_to(l3_run).as_posix(): path.read_bytes()
                for path in [
                    l3_run / "run.json",
                    *((l3_run / "domains").glob("*/final.md")),
                ]
            }
            l4_run = create_run(l3_run, public_input_confirmed=True)
            after = {
                path.relative_to(l3_run).as_posix(): path.read_bytes()
                for path in [
                    l3_run / "run.json",
                    *((l3_run / "domains").glob("*/final.md")),
                ]
            }
            run = load_json(l4_run / "run.json")
            artifacts_exist = all(
                path.is_file()
                for path in (
                    l4_run / "checkpoints.sqlite3",
                    l4_run / "usage.jsonl",
                    l4_run / "sources" / "index.jsonl",
                )
            )

        self.assertEqual(before, after)
        self.assertEqual(l4_run.parent, l3_run.parent)
        self.assertEqual(run["schema_version"], SCHEMA_VERSION)
        self.assertEqual(run["harness"], HARNESS_NAME)
        self.assertEqual(run["source_l3"]["path"], str(l3_run.resolve()))
        self.assertEqual(run["domains"], list(DOMAIN_NAMES))
        self.assertEqual(
            set(run["prompt_hashes"]),
            {"SKILL.md", "internal.md", "external_candidates.md", "synthesis.md"},
        )
        self.assertEqual(
            run["context_management"]["applies_to"],
            "external_researcher",
        )
        self.assertTrue(artifacts_exist)

    def test_missing_layer3_report_becomes_context_not_a_creation_gate(self):
        missing = DOMAIN_NAMES[0]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            l3_run = create_complete_l3_run(root)
            (l3_run / "domains" / slug(missing) / "final.md").unlink()
            l4_run = create_run(l3_run, public_input_confirmed=True)
            run = load_json(l4_run / "run.json")
            snapshot = read_text(l4_run / "inputs" / "domains" / f"{slug(missing)}.md")

        self.assertEqual(snapshot, MISSING_LAYER3_REPORT)
        self.assertFalse(run["source_l3"]["domain_inputs"][missing]["available"])
        self.assertTrue(
            all(
                run["source_l3"]["domain_inputs"][name]["snapshot_path"]
                for name in DOMAIN_NAMES
            )
        )

    def test_source_settings_are_frozen_and_wrong_schema_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            l3_run = create_complete_l3_run(root)
            source = load_json(l3_run / "run.json")
            source["reasoning_effort"] = "high"
            source["web_search"] = {"context_size": "high", "verbosity": "medium"}
            write_json(l3_run / "run.json", source)
            l4_run = create_run(l3_run, public_input_confirmed=True)
            frozen = load_json(l4_run / "run.json")
            source["schema_version"] = 7
            write_json(l3_run / "run.json", source)
            with self.assertRaisesRegex(ValueError, "schema 8"):
                create_run(l3_run, public_input_confirmed=True)

        self.assertEqual(frozen["reasoning_effort"], "high")
        self.assertEqual(frozen["web_search"], {"context_size": "high", "verbosity": "medium"})

    def test_notebook_controls_override_source_settings_and_validate_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            l3_run = create_complete_l3_run(root)
            l4_run = create_run(
                l3_run,
                public_input_confirmed=True,
                reasoning_effort="max",
                web_search_context_size="high",
                web_search_verbosity="medium",
            )
            frozen = load_json(l4_run / "run.json")
            for value in ("low", "medium", "high", "max"):
                with self.subTest(reasoning_effort=value):
                    accepted = create_run(
                        l3_run,
                        public_input_confirmed=True,
                        reasoning_effort=value,
                    )
                    self.assertEqual(
                        load_json(accepted / "run.json")["reasoning_effort"], value
                    )
            for value in ("low", "medium", "high"):
                with self.subTest(web_search_level=value):
                    accepted = create_run(
                        l3_run,
                        public_input_confirmed=True,
                        web_search_context_size=value,
                        web_search_verbosity=value,
                    )
                    self.assertEqual(
                        load_json(accepted / "run.json")["web_search"],
                        {"context_size": value, "verbosity": value},
                    )
            before_invalid = len(list(l3_run.parent.glob("L4_*")))
            for field, kwargs in (
                ("reasoning effort", {"reasoning_effort": "invalid"}),
                ("context size", {"web_search_context_size": "invalid"}),
                ("verbosity", {"web_search_verbosity": "invalid"}),
            ):
                with self.subTest(field=field), self.assertRaisesRegex(
                    ValueError, f"unsupported .*{field}"
                ):
                    create_run(l3_run, public_input_confirmed=True, **kwargs)
            after_invalid = len(list(l3_run.parent.glob("L4_*")))

        self.assertEqual(frozen["reasoning_effort"], "max")
        self.assertEqual(
            frozen["web_search"], {"context_size": "high", "verbosity": "medium"}
        )
        self.assertEqual(before_invalid, after_invalid)


class Layer4PromptTests(unittest.TestCase):
    def test_four_prompts_define_distinct_compact_contracts(self):
        with tempfile.TemporaryDirectory() as temporary:
            _, run_dir = _new_l4(Path(temporary))
            internal = internal_system_prompt(run_dir)
            candidates = candidate_system_prompt(run_dir)
            researcher = researcher_system_prompt(run_dir)
            synthesis = synthesis_system_prompt(run_dir)

        self.assertIn("not perform new research", internal)
        self.assertIn("Preserve `Established risk`", internal)
        self.assertIn("not input to external research", internal)
        self.assertNotIn("`## Evidence gaps`", internal)
        self.assertIn("## Prioritized external factors", candidates)
        self.assertIn("## Research brief", candidates)
        self.assertIn("Account for every material Layer 3 dependency once", candidates)
        self.assertIn("No grounded external factor", candidates)
        self.assertIn("exact Layer 3 dependency", candidates)
        self.assertIn("direct, indirect, compound and cascading pathways", candidates)
        self.assertIn("Allow a pathway to branch, converge", candidates)
        self.assertIn("without a plausible Layer 3", candidates)
        self.assertIn("geographic scales", candidates)
        self.assertIn("time horizons", candidates)
        self.assertNotIn("Status: Unresearched candidate", candidates)
        self.assertNotIn("## No candidate pathway established", candidates)
        self.assertNotIn("- `Research questions`", candidates)
        self.assertNotIn("- `Searchable anchors`", candidates)
        self.assertIn("search_web", researcher)
        self.assertIn("canonical content successfully returned by `read_source`", researcher)
        self.assertIn("neither evidence nor a discovery", researcher)
        self.assertIn("reject, combine, extend or independently discover", researcher)
        self.assertIn("geographic or sector manifestation", researcher)
        self.assertIn("asset vulnerability or resilience", researcher)
        self.assertIn("reinforcing", researcher)
        self.assertIn("balancing feedback effects", researcher)
        self.assertIn("consecutively numbered list, starting at 1", researcher)
        self.assertIn("supported within-domain branching", researcher)
        self.assertIn("Do not create empty sections or fixed field blocks", researcher)
        self.assertNotIn("Likelihood: Low | Medium | High | Unknown", researcher)
        for label in (
            "Established external influence",
            "Conditional external pathway",
            "Property dependency without proven adverse external event",
            "Context only",
            "Evidence gap",
        ):
            self.assertIn(label, researcher)
            self.assertIn(label, synthesis)
        self.assertIn("Do not perform new research", synthesis)
        self.assertIn("Merge findings only when", synthesis)
        self.assertIn("Relate rather than merge one shared driver", synthesis)
        self.assertIn("different external drivers that converge", synthesis)
        self.assertIn("derive cross-domain structural relationships", synthesis)
        self.assertIn("Do not invent an external driver", synthesis)
        self.assertIn("Do not independently re-rate", synthesis)
        self.assertIn("## Executive external-risk picture", synthesis)
        self.assertIn("## Numbered external-influence register", synthesis)
        self.assertIn("## Shared external drivers", synthesis)
        self.assertIn("## Divergent and converging pathways", synthesis)
        self.assertIn("## Compound and cascading exposures", synthesis)
        self.assertIn("## Material uncertainty, evidence gaps and context", synthesis)
        self.assertIn("consecutively from 1 in the register", synthesis)
        self.assertIn("combine or omit an empty section", synthesis)
        self.assertIn("amplification or buffering effects", synthesis)
        self.assertNotIn("- `External driver`", synthesis)
        self.assertNotIn("`## Evidence gaps`", synthesis)

    def test_dynamic_inputs_are_delimited_and_synthesis_is_fixed_order(self):
        internal = internal_message("D", "L3")
        candidates = candidate_message("D", "L3")
        research = researcher_message("D", "L3", "CANDIDATES")
        combined = synthesis_message({DOMAIN_NAMES[0]: "AVAILABLE"})

        self.assertIn("<layer3_domain_report>\nL3", internal)
        self.assertIn("<asset_context>\nL3", candidates)
        self.assertIn("<asset_context>\nL3", research)
        self.assertIn("<external_research_brief>\nCANDIDATES", research)
        self.assertNotIn("internal_conditions_report", candidates)
        self.assertNotIn("internal_conditions_report", research)
        self.assertEqual(candidates.count("L3"), 1)
        self.assertEqual(research.count("L3"), 1)
        positions = [combined.index(f"<domain_name>\n{name}\n") for name in DOMAIN_NAMES]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(combined.count(MISSING_EXTERNAL_REPORT), len(DOMAIN_NAMES) - 1)


class Layer4HarnessTests(unittest.TestCase):
    def test_only_external_researcher_receives_tools_and_context_management(self):
        import deepagents

        captured = []

        def record(**kwargs):
            captured.append(kwargs)
            return object()

        with tempfile.TemporaryDirectory() as temporary, patch.dict(
            os.environ, {"OPENAI_API_KEY": "test-not-a-real-key"}
        ), patch.object(deepagents, "create_deep_agent", record):
            _, run_dir = _new_l4(Path(temporary))
            create_internal_harness(run_dir)
            create_candidate_harness(run_dir)
            create_external_researcher_harness(run_dir)
            create_synthesis_harness(run_dir)

        self.assertEqual(len(captured), 4)
        tool_sets = [{getattr(tool, "name", "") for tool in item["tools"]} for item in captured]
        self.assertEqual(tool_sets, [set(), set(), {"search_web", "read_source"}, set()])
        self.assertTrue(all(item["subagents"] == [] for item in captured))
        self.assertTrue(all(item["response_format"] is None for item in captured))
        middleware = [[part.name for part in item["middleware"]] for item in captured]
        self.assertEqual(middleware[0], ["FilesystemMiddleware"])
        self.assertEqual(middleware[1], ["FilesystemMiddleware"])
        self.assertIn("ContextEditingMiddleware", middleware[2])
        self.assertIn("CdiResearchSummarization", middleware[2])
        self.assertEqual(middleware[3], ["FilesystemMiddleware"])


class Layer4CliTests(unittest.TestCase):
    def test_new_research_requires_online_public_confirmation(self):
        with tempfile.TemporaryDirectory() as temporary:
            l3_run = create_complete_l3_run(Path(temporary))
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as caught:
                    main(["--external-research", str(l3_run)])
        self.assertEqual(caught.exception.code, 2)

    def test_cli_surface_has_only_create_and_resume_actions(self):
        parser = _parser()
        actions = {
            option
            for action in parser._actions
            for option in action.option_strings
        }
        self.assertIn("--external-research", actions)
        self.assertIn("--resume-l4", actions)
        self.assertNotIn("--check-only", actions)


if __name__ == "__main__":
    unittest.main()

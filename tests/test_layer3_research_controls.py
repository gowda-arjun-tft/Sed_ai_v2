"""Notebook/CLI selection, linked handoffs and storage prerequisites without executing research."""

import ast
import asyncio
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

from ML.deep_research.layer2.backend.fs import load_json, write_json
from ML.deep_research.layer3.cli import main
from ML.deep_research.layer3.research_run import checkpoint_root, research_policy
from tests.layer3_fixtures import FakeFinder, new_run, snapshot
from tests.test_layer3_notebook import code_cells


class ResearchControlTests(unittest.IsolatedAsyncioTestCase):
    async def test_notebook_linked_action_calls_new_run_once_and_rejects_conflicts(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = new_run(Path(tmp))
            await FakeFinder().run(parent)
            before = snapshot(parent)
            config = Path(tmp) / "unlimited.json"
            write_json(config, dict.fromkeys(("maximum_calls", "wrap_up_after", "finalize_after")))

            async def completed(run, **kwargs):
                """Expose unlimited status without dispatching a researcher."""
                record = load_json(run / "run.json")
                record["research"]["jobs"]["offline"] = {"status": "complete",
                    "budget": {"used": 81, "remaining": None, "phase": "research"}}
                write_json(run / "run.json", record)

            for resume in ("", "conflicting-run"):
                tree = ast.parse(code_cells()[1])
                for node in tree.body:
                    if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                        name = node.targets[0].id
                        overrides = {"LAYER3_PREPARED_RUN_PATH": str(parent), "LAYER3_RESUME_RUN_PATH": resume,
                                     "LAYER3_RESEARCH_CONFIG_PATH": str(config),
                                     "PUBLIC_INPUT_CONFIRMED": True, "LAYER3_RETRY_FAILED": False}
                        if name in overrides:
                            node.value = ast.copy_location(ast.Constant(overrides[name]), node.value)
                code = compile(ast.fix_missing_locations(tree), "Notebook", "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
                with patch("ML.deep_research.layer3.run_all", new_callable=AsyncMock, side_effect=completed) as research, patch(
                    "ML.deep_research.layer2.backend.cli.load_dotenv_key"
                ), patch.dict("os.environ", {"OPENAI_API_KEY": "offline"}), contextlib.redirect_stdout(io.StringIO()) as output:
                    namespace = {}
                    if resume:
                        with self.assertRaisesRegex(RuntimeError, "multiple actions"):
                            await eval(code, namespace)
                        research.assert_not_awaited()
                    else:
                        await eval(code, namespace)
                        child = namespace["L3_SOURCE_RUN"]
                        self.assertNotEqual(child, parent)
                        self.assertEqual(load_json(child / "run.json")["research"]["mode"], "linked")
                        self.assertEqual((child / "_internal/inputs/user_research_instruction.md").read_bytes(),
                                         namespace["LAYER3_RESEARCH_INSTRUCTION_PATH"].read_bytes())
                        self.assertEqual((child / "_internal/inputs/research_config.json").read_bytes(), config.read_bytes())
                        self.assertIn("81 used, unlimited remaining", output.getvalue())
                        research.assert_awaited_once_with(child, retry_failed=False)
                self.assertEqual(snapshot(parent), before)

    async def test_cli_link_and_conflicting_modes_are_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            parent = new_run(Path(tmp))
            await FakeFinder().run(parent)
            before = snapshot(parent)
            instruction = Path(tmp) / "research_instruction.md"
            instruction.write_text("Technical objective — inspect tolerances.\n", encoding="utf-8")
            config = Path(tmp) / "bounded.json"
            write_json(config, {"maximum_calls": 8, "wrap_up_after": 3, "finalize_after": 5})
            with patch("ML.deep_research.layer3.cli.run_all", new_callable=AsyncMock) as execute, patch(
                "ML.deep_research.layer3.cli.load_dotenv_key"
            ), patch.dict("os.environ", {"OPENAI_API_KEY": "offline"}), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(await asyncio.to_thread(main, ["--research-from", str(parent), "--online", "--public-input-confirmed",
                                       "--research-reasoning-effort", "high", "--research-instruction", str(instruction),
                                       "--research-config", str(config)]), 0)
                linked = execute.call_args.args[0]
                self.assertNotEqual(linked, parent)
                self.assertEqual(load_json(linked / "run.json")["research"]["reasoning_effort"], "high")
                self.assertEqual((linked / "_internal/inputs/user_research_instruction.md").read_bytes(), instruction.read_bytes())
                self.assertEqual((linked / "_internal/inputs/research_config.json").read_bytes(), config.read_bytes())
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    main(["--research-from", str(parent), "--resume-l3", str(parent)])
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    main(["--resume-l3", str(parent), "--research-instruction", str(instruction)])
                for action in ("--resume-l3", "--upload-documents", "--check-only"):
                    with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                        main([action, str(parent), "--research-config", str(config)])
            self.assertEqual(snapshot(parent), before)
            script = (Path(__file__).resolve().parents[1] / "run.ps1").read_text(encoding="utf-8")
            self.assertIn("[string]$ResearchFromL3", script)
            self.assertIn("@('--research-from', $ResearchFromL3)", script)
            self.assertIn("[string]$ResearchInstruction", script)
            self.assertIn("@('--research-instruction', $ResearchInstruction)", script)
            self.assertIn("[string]$ResearchConfig", script)
            self.assertIn("@('--research-config', $ResearchConfig)", script)
            self.assertIn("'--research-instruction', '--research-config'", script)

    def test_missing_storage_never_falls_back_to_project_sqlite(self):
        with patch.dict("os.environ", {"SEDAI_RESEARCH_CHECKPOINT_DIR": ""}):
            with self.assertRaisesRegex(RuntimeError, "Docker"):
                checkpoint_root({"research": research_policy()})


if __name__ == "__main__":
    unittest.main()

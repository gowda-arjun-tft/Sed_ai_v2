"""Step 2 of 3 -- the agent that reads the sheet and writes the missions.

This module builds one deepagents harness agent and hands it the job. It contains
no procedure: nothing here splits the fact sheet, allocates facts, or writes a
mission file. Those decisions belong to the agent, and the method it follows is
written in English in `prompts/mission_agent.md`, not in Python.

**What it is given.** The fact sheet and the roster on a filesystem it can read
and write, `run_python` to measure and check with, and two kinds of helper it can
spawn a fresh context into. Capabilities, not instructions.

**The one thing the prompt insists on** is that no single context holds much more
than 20,000 tokens of source text. Not a limit -- nothing truncates and nothing
rejects. Attention decays long before a context window fills, and past about 85%
the harness silently compresses the older half of the conversation into a
summary, so a fact read early stops existing with no error raised. Forgetting
looks exactly like success, which is why the rule is stated in the prompt rather
than left to be discovered.

**What is deliberately absent.** No middleware: no model-call ceiling, no
tool-call ceiling, no retry policy. No tool that validates, scores or rejects
what the agent produces. No `write_todos` -- LangChain's own evaluations found it
costs tokens without helping on work like this, and `task` delegation is already
its own accountability structure.

The only Python-side restriction in the whole layer is a write-deny on `inputs/`,
and that protects a sha256 the next layer verifies -- not the agent's judgement.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

from .fs import read_text
from .planner import load_planner
from .python_tool import run_python
from .settings import MODEL_SPEC, PROMPTS_DIR, REASONING_EFFORT

# Lifts LangGraph's step ceiling out of the way. One "step" is one node
# transition, so a run that reads a large sheet through many helpers can take
# thousands; the framework default would kill it mid-way with a
# GraphRecursionError and no partial credit.
#
# This is passed in the *invoke config*, not to `create_deep_agent` -- it is not
# a constructor argument. `cli.write_missions` is what actually applies it.
RECURSION_LIMIT = 1_000_000

# The virtual prefix the agent's file tools see. `CompositeBackend` maps it to
# the real run folder, so the agent reads `/run/inputs/fact_sheet.md` while the
# bytes live at `runs/L2_.../inputs/fact_sheet.md`.
RUN_ROOT = "/run/"


@cache
def configure_provider() -> None:
    """Register the model's provider profile. Shared with Layer 3.

    A provider profile tells deepagents how to construct the chat model for a
    given model spec -- here: high reasoning effort, the Responses API, and
    `store=False` so no transcript is retained on the provider's side.

    **Why this lives here and nowhere else.** The profile registry is global and
    keyed by model spec. Both layers run on the same `MODEL_SPEC`, so two
    registrations would collide and whichever module imported first would shape
    the other layer's model. `layer3/llm.py` calls this function rather than
    registering its own. `@cache` makes repeat calls free and idempotent.

    The import is local because importing deepagents is slow and pulls in
    LangChain; keeping it inside the function lets `test_structure.py` import
    every module in both layers without paying for it.
    """
    from deepagents import ProviderProfile, register_provider_profile

    register_provider_profile(
        MODEL_SPEC,
        ProviderProfile(
            init_kwargs={
                "reasoning_effort": REASONING_EFFORT,
                "store": False,
                "use_responses_api": True,
            }
        ),
    )


def system_prompt(run_dir: Path, planner_text: str) -> str:
    """Assemble the agent's system prompt: the method, then the roster.

    Args:
        run_dir: The run folder. Its absolute path is substituted for the
            `{run_dir}` placeholder in the prompt, because `run_python` executes
            in a separate process on the real filesystem and cannot see the
            `/run/` virtual paths the file tools use. The agent is given both
            paths and told which tool uses which.
        planner_text: The full text of `planner_prompt.md`, appended verbatim --
            its rules paragraph, the fourteen subject definitions and the mission
            contract are the same text the roster JSON is embedded in.

    Returns:
        The complete system prompt. Since deepagents 0.7 the harness supplies no
        base prompt of its own, so this string is the entirety of what the agent
        is told.
    """
    task = read_text(PROMPTS_DIR / "mission_agent.md")
    return task.replace("{run_dir}", str(run_dir.resolve())) + "\n" + planner_text


def subagents() -> list[dict[str, Any]]:
    """The two kinds of fresh context the agent can spawn, via the `task` tool.

    Both exist for one reason: so that no single head has to hold the whole fact
    sheet, and so the fourteenth mission is written as carefully as the first. In
    the old design the fourteenth brief was reliably the weakest, because it was
    written at the tail of a long context. A delegated mission is written by a
    context holding only that mission's material.

    `slice-reader` reads one slice of a large sheet and stages what it found, per
    subject, into a folder of its own -- which is what lets many of them run at
    once without ever colliding on a file. `mission-writer` gathers one subject
    and writes its mission file, from facts handed to it inline or staged on
    disk, so it serves both the small-sheet and the large-sheet path.

    Several `task` calls in a single assistant message run in parallel, so the
    agent can fan out all fourteen writers at once.

    Each helper carries its own `system_prompt` because **subagents never inherit
    the parent's** -- that is a deepagents rule, and a silent one: a subagent
    without its own prompt gets nothing. The `description` is what the parent
    reads when deciding whether to delegate, so it says what the helper must be
    given.

    Whether to use either is the agent's call. The prompt says they exist and
    what shape of work they suit; it does not order their use.

    Returns:
        Two subagent specifications, ready for `create_deep_agent(subagents=...)`.
    """
    return [
        {
            "name": "slice-reader",
            "description": (
                "Reads one slice of a large fact sheet and stages the facts it "
                "found, per agent, into its own folder. Give it the slice bounds "
                "and its staging folder. Use this when the sheet is too large to "
                "hold in one context."
            ),
            "system_prompt": read_text(PROMPTS_DIR / "slice_reader.md"),
        },
        {
            "name": "mission-writer",
            "description": (
                "Writes one agent's mission file. Give it the agent name and "
                "definition, its facts -- either inline or the staging paths to "
                "gather them from -- and the path to write."
            ),
            "system_prompt": read_text(PROMPTS_DIR / "mission_writer.md"),
        },
    ]


def create_mission_agent(run_dir: Path, checkpointer: Any = None) -> Any:
    """Build the agent for one run folder.

    Args:
        run_dir: The folder `create_run` made. Becomes the agent's `/run/`.
        checkpointer: A LangGraph saver, normally the `AsyncSqliteSaver` from
            `cli.checkpoint_saver`. Optional so tests can construct the graph
            without one; a real run needs it, because it is what makes `--resume`
            continue the same conversation instead of starting over.

    Returns:
        A compiled LangGraph agent. `ainvoke` it with one user message.

    Constructing this makes no model call and needs no working API key, which is
    what lets `test_layer2_agent.py` inspect the tool surface offline.
    """
    from deepagents import FilesystemPermission, create_deep_agent
    from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend

    configure_provider()
    # Read from the copy inside the run folder, not from the repository, so the
    # agent is prompted with exactly the roster this run recorded and hashed.
    planner_text, _ = load_planner(run_dir / "inputs" / "planner_prompt.md")

    return create_deep_agent(
        model=MODEL_SPEC,
        system_prompt=system_prompt(run_dir, planner_text),
        # The only tool added to the built-ins. The file tools (ls, read_file,
        # write_file, edit_file, glob, grep, delete) and `task` come free with
        # the harness; `execute` is present but errors on this backend.
        tools=[run_python],
        # Empty on purpose. Every middleware available here would be a ceiling
        # on, or a wrapper around, the model's behaviour.
        middleware=[],
        # StateBackend stays the composite's default so the harness's own
        # artefacts -- /large_tool_results/ when a tool result is offloaded, and
        # /conversation_history/ when the context is summarised -- stay ephemeral
        # in thread state. With a bare FilesystemBackend they would land in the
        # run folder beside the deliverable and end up in the record.
        backend=CompositeBackend(
            default=StateBackend(),
            routes={
                RUN_ROOT: FilesystemBackend(
                    root_dir=str(run_dir.resolve()), virtual_mode=True
                )
            },
        ),
        # The two input copies must stay byte-identical: the report re-hashes
        # both and Layer 3 re-verifies the planner copy. This protects a hash,
        # not the agent's thinking. It also sidesteps a live deepagents bug where
        # `edit_file` with an empty `old_string` overwrites a whole file.
        permissions=[
            FilesystemPermission(
                operations=["write"], paths=[f"{RUN_ROOT}inputs/**"], mode="deny"
            )
        ],
        subagents=subagents(),
        checkpointer=checkpointer,
        name="cdi-layer2",
    )


def mission_request() -> str:
    """The single user turn that starts the run.

    Deliberately thin. The system prompt already carries the task, the roster and
    the method; repeating any of it here would only give the agent two slightly
    different versions of its instructions to reconcile.

    Asking it to say how it checked its work makes the verification visible in
    the final message, where a human reads it -- the report that follows counts
    files and keys, and cannot see reasoning.
    """
    return (
        "Read the fact sheet and write the fourteen mission files. "
        "Tell me what you wrote and how you checked it."
    )

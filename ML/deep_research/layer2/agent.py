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
rejects. Attention decays long before a context window fills, and two harness
behaviours then compound it silently. Both numbers below were read from the
installed deepagents 0.7.7 and this model's profile, not assumed:

* a single tool result over **20,000 tokens** is evicted to `/large_tool_results/`
  and replaced by a pointer (`filesystem.py: tool_token_limit_before_evict`);
* at **85% of max input -- about 892,500 tokens here** -- summarisation fires and
  keeps `("fraction", 0.10)`, i.e. **the most recent tenth**. An earlier version
  of this docstring and of the prompt said it "compresses the older half", which
  understated it by a wide margin: roughly the older nine tenths are replaced.

A fact read early stops existing with no error raised. Forgetting looks exactly
like success, which is why the rule is stated rather than left to be discovered.

**What is deliberately absent.** `middleware=[]` adds no ceiling of our own: no
model-call limit, no tool-call limit, no retry policy. It does *not* mean the
graph is bare -- the harness always installs its own filesystem, subagent,
summarisation and tool-call-repair middleware, and those stay. What is absent is
anything that would cap or judge the model. There is also no `write_todos`:
LangChain's own evaluations found it costs tokens without helping on work like
this, and `task` delegation is already its own accountability structure.

The only Python-side restriction in the whole layer is a write-deny on `inputs/`,
and that protects a sha256 the next layer verifies -- not the agent's judgement.
Note what it does *not* cover: `run_python` runs a subprocess on the host, which
no `FilesystemPermission` can constrain. Layer 2 is not a sandbox. See AGENTS.md.
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
# thousands.
#
# The installed langgraph 1.2.11 defaults to 10,007, not the 25 that older
# LangGraph documentation and earlier comments in this repository stated --
# verified by letting a trivial cyclic graph run to the error:
#   "Recursion limit of 10007 reached without hitting a stop condition"
# (langgraph/_internal/_config.py: DEFAULT_RECURSION_LIMIT, overridable by the
# LANGGRAPH_DEFAULT_RECURSION_LIMIT environment variable). 10,007 is generous but
# it is still a ceiling, and one that would end a long run with no partial
# credit, so it is lifted rather than relied on.
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
                "timeout": 600,
                "max_retries": 2,
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
    """The two CDI helpers plus an explicit general-purpose helper.

    Both declared helpers exist for one reason: so that no single head has to
    hold the whole fact sheet, and so the fourteenth mission is written as
    carefully as the first. In the old design the fourteenth brief was reliably
    the weakest, because it was written at the tail of a long context. A
    delegated mission is written by a context holding only that mission's
    material.

    `slice-reader` reads one slice of a large sheet and stages what it found, per
    subject, into a folder of its own -- which is what lets many of them run at
    once without ever colliding on a file. `mission-writer` gathers one subject
    and writes its mission file, from facts handed to it inline or staged on
    disk, so it serves both the small-sheet and the large-sheet path.

    Three facts about what the harness actually builds, all read off the compiled
    graph rather than assumed:

    1. **The `general-purpose` helper is explicit**, because Layer 3 disables the
       process-wide implicit helper for the shared model. Layer 2 therefore keeps
       the same three task choices regardless of import order.
    2. **A subagent inherits the parent's `tools` when it declares none**, so
       both helpers get `run_python` as well as the file tools. Their prompts say
       so; a capability nobody mentions goes unused.
    3. **No subagent gets `task`.** `SubAgentMiddleware` is attached to the main
       agent only, so delegation is exactly one level deep. `mission_writer.md`
       used to tell the writer it could "delegate the parts the same way the
       caller delegated to you" -- an instruction it had no tool to obey. Both
       helper prompts now say plainly that they are the last link.

    Each helper carries its own `system_prompt` because **subagents never inherit
    the parent's** -- a deepagents rule, and a silent one: a subagent without its
    own prompt gets nothing. The `description` is the only thing the parent reads
    when deciding whether and how to delegate, so it has to name everything the
    helper cannot work without.

    Whether to use either is the agent's call. The prompt says they exist and
    what shape of work they suit; it does not order their use.

    Returns:
        Three subagent specifications, ready for `create_deep_agent(subagents=...)`.
    """
    from deepagents.middleware.subagents import GENERAL_PURPOSE_SUBAGENT

    return [
        {
            "name": "slice-reader",
            # The roster is named explicitly: the helper cannot allocate facts to
            # subjects it was never shown, and it does not inherit this prompt.
            "description": (
                "Reads one slice of a large fact sheet and stages the facts it "
                "found, per agent, into its own folder. Give it the slice bounds, "
                "its staging folder, and the fourteen agent names with what each "
                "one covers -- it cannot see the roster otherwise. It cannot "
                "delegate further. Use this when the sheet is too large to hold "
                "in one context."
            ),
            "system_prompt": read_text(PROMPTS_DIR / "slice_reader.md"),
        },
        {
            "name": "mission-writer",
            "description": (
                "Writes one agent's mission file. Give it the agent name and "
                "definition, its facts -- either inline or the staging paths to "
                "gather them from -- and the path to write. It cannot delegate "
                "further, so hand it work one agent can finish."
            ),
            "system_prompt": read_text(PROMPTS_DIR / "mission_writer.md"),
        },
        dict(GENERAL_PURPOSE_SUBAGENT),
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
        # Adds no middleware of our own. It does not make the graph bare: the
        # harness still installs filesystem, subagent, summarisation and
        # tool-call-repair middleware, and those are what make the file tools and
        # `task` exist at all. What this omits is any ceiling -- no
        # ModelCallLimitMiddleware, no ToolCallLimitMiddleware, no retry policy.
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

"""Construct the persistent Deep Agent without owning run scheduling or persistence."""

from deepagents import create_deep_agent
from langchain.agents.middleware import TodoListMiddleware

from ML.deep_research.domain_decider.ML.harness import build_model, configure_harness
from .research_memory import ResearchGuard, ResearchSummarization, file_middleware, memory_backend


def build_agent(run, record, root, entry, tools, saver, logger, budget=None, clients=None):
    """Assemble the installed native loop without shell, delegation, repair or loop-budget middleware."""
    configure_harness()
    model = build_model(record["research"]["reasoning_effort"],
                        max_retries=record["provider_max_retries"],
                        timeout=record["timeout_seconds"], **(clients or {}))
    backend = memory_backend(root)
    files = file_middleware(backend)
    prompt_root = run / "_internal/inputs/prompts"
    prompt = (prompt_root / "domain_research.md").read_text(encoding="utf-8")
    if record["research"]["version"] >= 2:
        # Task instructions stay active through compaction, unlike evidence or old dialogue.
        prompt += "\n\n# Selected user research instruction\n\n" + (
            run / "_internal/inputs/user_research_instruction.md").read_text(encoding="utf-8-sig")
    middleware = [files, TodoListMiddleware(),
                  ResearchSummarization(model, backend, record,
                                        (prompt_root / "research_summary.md").read_text(encoding="utf-8"),
                                        logger, budget),
                  ResearchGuard(record, root, entry["fingerprint"], logger, budget)]
    graph = create_deep_agent(model=model, tools=tools, backend=backend, middleware=middleware,
                              subagents=[], checkpointer=saver, response_format=None,
                              system_prompt=prompt, name="domain-research")
    return graph, files, model

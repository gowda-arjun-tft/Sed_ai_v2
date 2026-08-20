"""Runs one structured aggregator call.

One invocation, no retry loop and no validator hook. Whatever the model returns
in its structured response is what the caller gets.

`recursion_limit` is passed only to lift LangGraph's 25-step default out of the
way; it is not a ceiling this layer wants.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .llm import structured_value
from .settings import RECURSION_LIMIT
from .usage import record_agent_usage


async def invoke_structured(
    agent: Any,
    content: str,
    thread_id: str,
    expected: type[Any],
    run_dir: Path,
    role: str,
) -> Any:
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": content}]},
        config={
            "configurable": {"thread_id": thread_id},
            "recursion_limit": RECURSION_LIMIT,
        },
    )
    record_agent_usage(run_dir, thread_id, role, result)
    return structured_value(result, expected)

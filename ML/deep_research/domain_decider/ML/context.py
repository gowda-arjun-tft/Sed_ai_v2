"""Fresh messages, native call options and complete local input accounting."""

import json

from langchain_core.messages import HumanMessage, SystemMessage

from ..backend.windows import token_count


class InputSizeError(ValueError):
    """An assembled input cannot fit; completed model content is never graded."""


def messages(prompt: str, sections: dict[str, str]) -> list:
    """Input instructions and labelled data; return the exact fresh messages sent to the model."""
    content = "\n\n".join(f"<{label}>\n{text}\n</{label}>" for label, text in sections.items())
    return [SystemMessage(content=prompt), HumanMessage(content=content)]


def request_options(stage: str, record: dict) -> dict:
    """Input a stage and frozen policy; return native options shared by dispatch and accounting."""
    if stage == "metadata":
        return {}
    options = {}
    if stage == "distribution":
        options["response_format"] = {"type": "json_object"}
    if stage == "design":
        options.update(tools=[{"type": "web_search", "search_context_size": record["web_search"]["context_size"]}],
                       tool_choice=record["web_search"]["tool_choice"],
                       include=["web_search_call.action.sources"])
        if "verbosity" in record["web_search"]:
            options["text"] = {"verbosity": record["web_search"]["verbosity"]}
    return options


def estimate(values: list, reserve: int, options: dict | None = None) -> int:
    """Input actual messages, options and framing; estimate tokens including tool/format definitions."""
    overhead = token_count(json.dumps(options, ensure_ascii=False, sort_keys=True)) if options else 0
    return sum(token_count(value.content) for value in values) + reserve + 32 * len(values) + overhead

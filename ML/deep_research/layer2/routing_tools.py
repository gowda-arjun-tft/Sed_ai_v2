from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .fs import now_iso, text_hash
from .progress import bucket_entries, read_progress, write_progress


def build_routing_tools(
    run_dir: Path,
    name_to_file: dict[str, Path],
    state: dict[str, Any],
) -> list[Any]:
    from langchain.tools import tool

    @tool(parse_docstring=True)
    def append_to_bucket(agent_name: str, fact_block: str, reason: str) -> str:
        """Append one complete fact block to one agent bucket.

        Args:
            agent_name: One exact roster name, or _unrouted when no agent needs the fact.
            fact_block: The complete ### block copied character for character from the piece.
            reason: One short line explaining the routing decision.
        """
        if agent_name not in name_to_file:
            return f"Rejected: agent_name must be one of {list(name_to_file)}"
        fact = fact_block.replace("\r\n", "\n").replace("\r", "\n").strip()
        if fact not in state["facts"]:
            return (
                "Rejected: fact_block is not an exact complete block from the "
                "current piece. Copy it again exactly."
            )
        if not reason.strip():
            return "Rejected: reason cannot be empty."
        destinations = state["destinations"].setdefault(fact, set())
        routed_and_unrouted = (
            agent_name == "_unrouted" and destinations
        ) or (
            agent_name != "_unrouted" and "_unrouted" in destinations
        )
        if routed_and_unrouted:
            return "Rejected: a fact cannot be both routed and unrouted."

        metadata = {
            "piece_id": state["piece_id"],
            "sha256": text_hash(fact),
            "reason": reason.strip().replace("--", "—"),
        }
        path = name_to_file[agent_name]
        existing = bucket_entries(path)
        additions = []
        for occurrence in range(1, state["facts"].count(fact) + 1):
            occurrence_metadata = {**metadata, "occurrence": occurrence}
            already_exists = any(
                meta.get("piece_id") == metadata["piece_id"]
                and meta.get("sha256") == metadata["sha256"]
                and int(meta.get("occurrence", 1)) == occurrence
                for meta, _ in existing
            )
            if not already_exists:
                marker = json.dumps(
                    occurrence_metadata,
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                additions.append(
                    f"\n<!-- route {marker} -->\n{fact}\n<!-- /route -->\n"
                )
        if additions:
            with path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.writelines(additions)
        destinations.add(agent_name)
        return f"Appended {len(additions)} new occurrence(s) to {agent_name}."

    @tool(parse_docstring=True)
    def mark_piece_done(
        piece_id: str,
        facts_routed: int,
        facts_unrouted: int,
    ) -> str:
        """Mark the current piece complete after every fact has been allocated.

        Args:
            piece_id: Current piece identifier, such as p003.
            facts_routed: Number of facts sent to at least one named agent.
            facts_unrouted: Number of facts sent only to _unrouted.
        """
        if piece_id != state["piece_id"]:
            return f"Rejected: current piece is {state['piece_id']}."
        missing = [
            fact.splitlines()[0]
            for fact in state["facts"]
            if not state["destinations"].get(fact)
        ]
        if missing:
            return f"Rejected: route these facts first: {missing}"
        actual_unrouted = sum(
            state["destinations"][fact] == {"_unrouted"}
            for fact in state["facts"]
        )
        actual_routed = len(state["facts"]) - actual_unrouted
        if (facts_routed, facts_unrouted) != (actual_routed, actual_unrouted):
            return (
                f"Rejected: actual counts are facts_routed={actual_routed}, "
                f"facts_unrouted={actual_unrouted}."
            )
        rows = read_progress(run_dir)
        row = next((item for item in rows if item["piece_id"] == piece_id), None)
        if row is None:
            return "Rejected: piece is not in progress.csv."
        row.update(
            status="done",
            facts_routed=str(actual_routed),
            facts_unrouted=str(actual_unrouted),
            routed_at=now_iso(),
        )
        write_progress(run_dir, rows)
        return f"Marked {piece_id} done."

    return [append_to_bucket, mark_piece_done]

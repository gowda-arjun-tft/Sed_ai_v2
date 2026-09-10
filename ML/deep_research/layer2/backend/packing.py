"""Lazy source seeks and fully accounted stage input pages."""

from .fs import load_json, read_text
from .settings import stage_uses_tools
from .evidence_text import message_text
from .windows import source_windows, text_pages, token_count
from ..ML.agent import Layer2Response, read_only_filesystem
from ..ML.context import dump, estimate


def input_tokens(run, stage, payload):
    """Input stage/payload; count complete instructions, native tools, schema and framing."""
    record = load_json(run / "run.json")
    policy = record["context_policy"]
    prompt = read_text(run / "_internal/inputs/prompts" / f"{stage}.md")
    tools = read_only_filesystem().tools if stage_uses_tools(stage) else ()
    return estimate([{"role": "user", "content": message_text(payload)}], prompt, tools,
                    Layer2Response.model_json_schema(), policy["framing_reserve"])


def fits(run, stage, payload):
    """Input assembled payload; report whether it fits the normal input target."""
    return input_tokens(run, stage, payload) <= load_json(run / "run.json")["context_policy"]["target_tokens"]


def page_budget(run, stage, context, cap=40_000):
    """Input mandatory context; reserve space for three bounded record/definition/decision groups."""
    policy = load_json(run / "run.json")["context_policy"]
    room = policy["target_tokens"] - input_tokens(run, stage, context) - 2_000
    # An unfit mandatory input reaches the operational guard, not millions of tiny jobs.
    return max(1_024, min(cap, room // 3))


def source_payloads(run):
    """Input frozen source ranges; seek and yield one original window or repacked fragment at a time."""
    policy = load_json(run / "run.json")["context_policy"]
    allowance = policy["target_tokens"] - input_tokens(run, "understanding", {}) - 2_000
    manifest = load_json(run / "_internal/trace/source/manifest.json")
    with (run / "_internal/inputs/fact_sheet.md").open("rb") as handle:
        for item in manifest:
            handle.seek(item["start_byte"] + item["input_bom_bytes"])
            raw = handle.read(item["end_byte"] - item["start_byte"])
            cut = item["new_start_byte"] - item["start_byte"]
            window = {"source": {**item, "part": 1},
                      "overlap_context": raw[:cut].decode("utf-8"), "new_content": raw[cut:].decode("utf-8")}
            if fits(run, "understanding", window) or allowance <= 12_000:
                yield window
                continue
            text = raw.decode("utf-8")
            # Serialized escaping is counted before selecting a smaller source window.
            ratio = max(1, token_count(dump(dump(text))))
            size = max(10_001, int(token_count(text) * allowance / ratio) - 2_000)
            for index, part in enumerate(source_windows(text, size=size, overlap=10_000, include_text=False), 1):
                new = min(part["end_byte"], max(part["new_start_byte"], cut))
                location = {**item, "part": index,
                            "start_byte": item["start_byte"] + part["start_byte"],
                            "end_byte": item["start_byte"] + part["end_byte"],
                            "new_start_byte": item["start_byte"] + new}
                yield {"source": location,
                       "overlap_context": raw[part["start_byte"]:new].decode("utf-8"),
                       "new_content": raw[new:part["end_byte"]].decode("utf-8")}


def record_pages(records, budget=40_000):
    """Input record iterator; yield token-bounded pages, preserving oversized parent/fragment links."""
    page, used = [], 0
    for index, record in enumerate(records):
        serialized = dump(record)
        size = token_count(dump(serialized)) + 32
        if size > budget:
            if page:
                yield page
                page, used = [], 0
            parent = record if isinstance(record, dict) else {}
            identities = {k: parent[k] for k in ("fact_id", "domain_id", "proposal_id", "evidence_id") if k in parent}
            identity = next(iter(identities.values()), f"record-{index}")
            # Original records remain unchanged; only the invocation uses linked text fragments.
            for part, text in enumerate(text_pages(serialized, max(1, budget // 3)), 1):
                yield [{"parent_record_id": identity, **identities,
                        "fragment": part, "record_fragment": text}]
            continue
        if page and used + size > budget:
            yield page
            page, used = [], 0
        page.append(record)
        used += size
    if page:
        yield page


def definition_pages(store, collection="domains", budget=80_000):
    """Input the disk-backed domain registry; yield complete bounded definition pages."""
    yield from record_pages(store.rows(collection), budget)

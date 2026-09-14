"""Original-source windows with Unicode-safe boundaries."""

from __future__ import annotations

from functools import cache

import tiktoken

from .settings import CHUNK_ENCODING, CHUNK_OVERLAP_TOKENS, CHUNK_SIZE_TOKENS


@cache
def encoding(name: str = CHUNK_ENCODING):
    """Input an encoding name; return the shared tokenizer used for input accounting."""
    return tiktoken.get_encoding(name)


def token_count(text: str) -> int:
    """Input text; return a local source-token count, never a provider billing claim."""
    return len(encoding().encode(text, disallowed_special=()))


def source_windows(
    text: str, size: int = CHUNK_SIZE_TOKENS, overlap: int = CHUNK_OVERLAP_TOKENS,
    *, include_text: bool = True,
) -> list[dict]:
    """Input original text and policy; return UTF-8-safe windows with exact byte locators."""
    if not 0 <= overlap < size:
        raise ValueError("invalid source window policy")
    codec = encoding()
    ids = codec.encode(text, disallowed_special=())
    raw = text.encode("utf-8")
    # Only window boundaries survive the single tokenizer allocation; no per-token
    # offset/safe-boundary arrays or decoded corpus copies are retained.
    starts = range(0, len(ids), size - overlap)
    wanted = sorted({0, len(ids), *starts, *(min(s + size, len(ids)) for s in starts)})
    before, after, cursor, offset, last_safe = {}, {}, 0, 0, (0, 0)
    for i in range(len(ids) + 1):
        safe = offset == len(raw) or raw[offset] & 0xC0 != 0x80
        if safe:
            while cursor < len(wanted) and wanted[cursor] <= i:
                target = wanted[cursor]
                before[target] = (i, offset) if target == i else last_safe
                after[target] = (i, offset)
                cursor += 1
            last_safe = (i, offset)
        if i < len(ids):
            offset += len(codec.decode_single_token_bytes(ids[i]))
    result, previous_end_byte = [], 0
    for nominal_start in starts:
        start, start_byte = before[nominal_start]
        nominal_end = min(nominal_start + size, len(ids))
        end, end_byte = after[nominal_end]
        boundary = max(start_byte, previous_end_byte)
        result.append({
            "source_id": f"s{len(result) + 1:06d}",
            "nominal_start_token": nominal_start, "nominal_end_token": nominal_end,
            "start_token": start, "end_token": end,
            "start_byte": start_byte, "end_byte": end_byte,
            "new_start_byte": boundary, "tokens": end - start,
        })
        if include_text:
            result[-1].update(overlap_context=raw[start_byte:boundary].decode("utf-8"),
                              new_content=raw[boundary:end_byte].decode("utf-8"))
        previous_end_byte = end_byte
        if end == len(ids):
            break
    return result

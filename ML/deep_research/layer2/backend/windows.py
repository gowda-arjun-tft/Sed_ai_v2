"""Original-source windows and bounded Unicode-safe pages."""

from __future__ import annotations

import bisect
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
) -> list[dict]:
    """Input original text and policy; return UTF-8-safe windows with exact byte locators."""
    if not 0 <= overlap < size:
        raise ValueError("invalid source window policy")
    codec = encoding()
    ids = codec.encode(text, disallowed_special=())
    raw = text.encode("utf-8")
    offsets = [0]
    for token in ids:
        offsets.append(offsets[-1] + len(codec.decode_single_token_bytes(token)))
    # A token can end inside a Unicode character. Align to an existing token AND
    # character boundary, keeping original bytes rather than decoding replacement text.
    safe = [i for i, offset in enumerate(offsets)
            if offset == len(raw) or raw[offset] & 0xC0 != 0x80]
    result, previous_end = [], 0
    for nominal_start in range(0, len(ids), size - overlap):
        start = safe[max(0, bisect.bisect_right(safe, nominal_start) - 1)]
        nominal_end = min(nominal_start + size, len(ids))
        end = safe[bisect.bisect_left(safe, nominal_end)]
        boundary = max(start, previous_end)
        result.append({
            "source_id": f"s{len(result) + 1:06d}",
            "nominal_start_token": nominal_start, "nominal_end_token": nominal_end,
            "start_token": start, "end_token": end,
            "start_byte": offsets[start], "end_byte": offsets[end],
            "new_start_byte": offsets[boundary], "tokens": end - start,
            "overlap_context": raw[offsets[start]:offsets[boundary]].decode("utf-8"),
            "new_content": raw[offsets[boundary]:offsets[end]].decode("utf-8"),
        })
        previous_end = end
        if end == len(ids):
            break
    return result


def text_pages(text: str, budget: int = 8_000) -> list[str]:
    """Input text and token allowance; return complete nonoverlapping character-safe pages."""
    if budget < 1:
        raise ValueError("page token allowance must be positive")
    pages = []
    while text:
        lo, hi = 1, min(len(text), budget * 8)
        best = 0
        while lo <= hi:
            mid = (lo + hi) // 2
            if token_count(text[:mid]) <= budget:
                best, lo = mid, mid + 1
            else:
                hi = mid - 1
        if not best:
            raise ValueError("one source character exceeds page token allowance")
        pages.append(text[:best])
        text = text[best:]
    return pages

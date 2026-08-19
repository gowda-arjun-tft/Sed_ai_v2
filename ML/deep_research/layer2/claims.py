from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .fs import read_text


Claim = dict[str, Any]


def load_claims(path: Path) -> tuple[list[Claim], str]:
    try:
        document = json.loads(read_text(path))
    except json.JSONDecodeError as error:
        raise ValueError(f"invalid JSON input: {error}") from error
    if isinstance(document, list):
        claims, pointer_base = document, ""
    elif isinstance(document, dict) and isinstance(document.get("claims"), list):
        claims, pointer_base = document["claims"], "/claims"
    else:
        raise ValueError(
            'JSON input must be a list of claim objects or an object with a "claims" list'
        )
    if not claims:
        raise ValueError("JSON input contains no claims")
    if any(not isinstance(claim, dict) or not claim for claim in claims):
        raise ValueError("every claim must be a non-empty JSON object")
    return claims, pointer_base


def claim_pointer(pointer_base: str, index: int) -> str:
    return f"{pointer_base}/{index}"


def claim_block(claim: Claim, pointer: str, number: int) -> str:
    payload = json.dumps(claim, ensure_ascii=False, indent=2)
    return (
        f"### Claim {number:03d}\n\n"
        f"**JSON Pointer:** `{pointer}`\n\n"
        f"```json\n{payload}\n```"
    )


def input_claim_blocks(path: Path) -> list[str]:
    claims, pointer_base = load_claims(path)
    return [
        claim_block(claim, claim_pointer(pointer_base, index), index + 1)
        for index, claim in enumerate(claims)
    ]


def context_from_claim_block(block: str) -> dict[str, Any]:
    pointer = re.search(r"(?m)^\*\*JSON Pointer:\*\* `(.+?)`$", block)
    payload = re.search(r"(?ms)^```json\n(.*?)\n```$", block)
    if not pointer or not payload:
        raise ValueError("invalid internal claim block")
    return {
        "claim": json.loads(payload.group(1)),
        "input_pointer": pointer.group(1),
    }


def claims_by_pointer(path: Path) -> dict[str, Claim]:
    claims, pointer_base = load_claims(path)
    return {
        claim_pointer(pointer_base, index): claim
        for index, claim in enumerate(claims)
    }

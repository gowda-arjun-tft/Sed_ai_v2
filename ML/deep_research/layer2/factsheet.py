from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

from .fs import read_text


@dataclass(frozen=True)
class Section:
    title: str
    raw: str


def estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


def split_sections(text: str) -> list[Section]:
    matches = list(re.finditer(r"(?m)^## (?!#)(.+?)\s*$", text))
    return [
        Section(
            match.group(1).strip(),
            text[
                match.start() : matches[index + 1].start()
                if index + 1 < len(matches)
                else len(text)
            ].strip(),
        )
        for index, match in enumerate(matches)
    ]


def fact_blocks(text: str) -> list[str]:
    headings = list(re.finditer(r"(?m)^##(?:#)? (?!#).+?\s*$", text))
    return [
        text[
            heading.start() : headings[index + 1].start()
            if index + 1 < len(headings)
            else len(text)
        ].strip()
        for index, heading in enumerate(headings)
        if heading.group(0).startswith("### ")
    ]


def piece_body(path: Path) -> str:
    return re.sub(
        r"\A<!-- piece .*? -->\s*",
        "",
        read_text(path),
        count=1,
        flags=re.S,
    )


def atoms(text: str, mode: str) -> list[str]:
    return fact_blocks(text) if mode in {"facts", "claims"} else [section.raw for section in split_sections(text)]


def field_value(block: str, name: str) -> str:
    match = re.search(
        rf"(?ms)^\*\*{re.escape(name)}:\*\*\s*(.*?)"
        rf"(?=^\*\*(?:Evidence|Source|Interpretation):\*\*|\Z)",
        block,
    )
    return match.group(1).strip() if match else ""


def context_from_block(block: str) -> dict[str, str]:
    heading = re.match(r"### (.+?)\s*$", block.splitlines()[0])
    evidence = field_value(block, "Evidence")
    return {
        "section": heading.group(1).strip() if heading else "Unlabelled fact",
        "fact": evidence or block.strip(),
        "means": field_value(block, "Interpretation"),
        "where": field_value(block, "Source"),
    }

"""Turning fetched bytes into quotable text.

Two things here determine whether an agent can inspect retained evidence:
working out how a page is encoded and preserving the structure of a table.
Both used to be assumptions -- UTF-8 and no cell separator -- and both silently
produced mangled text that made source review unreliable.
"""

from __future__ import annotations

import codecs
import re
from email.message import Message
from html.parser import HTMLParser


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.ignored += 1
        elif tag in {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")
        elif tag in {"td", "th"}:
            # Without a cell separator every row collapses into one unbroken
            # string, which is how rent rolls and cost tables used to arrive.
            self.parts.append(" | ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self.ignored:
            self.ignored -= 1
        elif tag in {"p", "div", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.ignored:
            self.parts.append(data)


_BOMS = (
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xff\xfe", "utf-16-le"),
    (b"\xfe\xff", "utf-16-be"),
)
_META_CHARSET = re.compile(rb"""charset\s*=\s*["']?\s*([\w.:-]+)""", re.I)


def detect_encoding(body: bytes, content_type: str) -> str:
    """Work out how to decode a page instead of assuming UTF-8.

    Order: byte-order mark, then the HTTP header, then the document's own meta
    declaration, then UTF-8 if it decodes cleanly, then windows-1252 as a
    last resort that never raises.

    Assuming UTF-8 silently mangles most of the world's official sources --
    windows-1251 in Russia and Ukraine, Shift-JIS in Japan, Big5 in Taiwan,
    windows-1256 for Arabic, ISO-8859-x across Europe. The model then quotes the
    mangled text and the citation check rejects it for reasons nobody can see.
    """
    for marker, name in _BOMS:
        if body.startswith(marker):
            return name

    declared = Message()
    declared["content-type"] = content_type or ""
    header_charset = declared.get_param("charset")
    if isinstance(header_charset, str) and _usable(header_charset):
        return header_charset

    match = _META_CHARSET.search(body[:4096])
    if match:
        candidate = match.group(1).decode("ascii", errors="ignore")
        if _usable(candidate):
            return candidate

    try:
        body.decode("utf-8")
    except UnicodeDecodeError:
        return "windows-1252"
    return "utf-8"


def encoding_was_declared(body: bytes, content_type: str) -> bool:
    """Whether the source told us its encoding, or we had to fall back.

    A page that declares nothing and is not valid UTF-8 is decoded on a guess.
    That guess is right for Western European text and wrong for Cyrillic, Greek,
    Hebrew and Thai bytes, which are indistinguishable without statistical
    detection. Recording the difference is what makes the resulting citation
    failure explainable instead of mysterious.
    """
    if any(body.startswith(marker) for marker, _ in _BOMS):
        return True
    declared = Message()
    declared["content-type"] = content_type or ""
    header_charset = declared.get_param("charset")
    if isinstance(header_charset, str) and _usable(header_charset):
        return True
    match = _META_CHARSET.search(body[:4096])
    if match and _usable(match.group(1).decode("ascii", errors="ignore")):
        return True
    try:
        body.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def _usable(name: str) -> bool:
    try:
        codecs.lookup(name)
    except (LookupError, TypeError):
        return False
    return True


def canonical_text(body: bytes, content_type: str) -> str | None:
    media_type = content_type.partition(";")[0].strip().casefold()
    charset = detect_encoding(body, content_type)
    if media_type in {"text/plain", "text/markdown", "application/json"}:
        text = body.decode(charset, errors="replace")
    elif media_type in {"text/html", "application/xhtml+xml"}:
        parser = _TextExtractor()
        parser.feed(body.decode(charset, errors="replace"))
        text = "".join(parser.parts)
    else:
        return None
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line).strip() + "\n"

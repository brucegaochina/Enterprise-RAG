"""Structure-aware chunking.

Text is split into paragraphs and sentences, which are packed into chunks of
roughly `chunk_size` characters. A new chunk starts at a section heading when
the current chunk is already big enough, so chunks rarely mix unrelated topics.
Each chunk remembers its character offsets (for highlighting the citation in
the source document), its page and the section heading it belongs to.
"""

from __future__ import annotations

import bisect
import re
from dataclasses import dataclass

MD_HEADING = re.compile(r"^#{1,6}\s+(.+?)\s*#*$")
RULE_LINE = re.compile(r"^[=\-_*]{3,}$")
LIST_ITEM = re.compile(r"^([-*\u2022]|\d+[.)])\s+")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")


@dataclass
class Chunk:
    index: int
    content: str
    start_char: int
    end_char: int
    heading: str | None
    page: int | None


@dataclass
class _Unit:
    start: int
    end: int
    heading: str | None
    is_heading: bool = False

    @property
    def length(self) -> int:
        return self.end - self.start


def _heading_text(line: str) -> str | None:
    s = line.strip()
    m = MD_HEADING.match(s)
    if m:
        return m.group(1).strip()
    if LIST_ITEM.match(s) or re.search(r"[|$%]", s) or not (s[0].isupper() or s[0].isdigit()):
        return None
    # FAQ-style headings ("How do I reset my password?") may be longer and end with "?".
    is_question = s.endswith("?")
    if len(s) > (90 if is_question else 70) or len(s.split()) > (14 if is_question else 9):
        return None
    if s[-1] in ".,;:!)\"'%":
        return None
    return s


def _units(text: str, chunk_size: int) -> list[_Unit]:
    units: list[_Unit] = []
    heading: str | None = None
    para_start = para_end = None

    def flush_paragraph() -> None:
        nonlocal para_start, para_end
        if para_start is None:
            return
        segment = text[para_start:para_end]
        cursor = 0
        for piece in SENTENCE_END.split(segment):
            offset = segment.find(piece, cursor)
            cursor = offset + len(piece)
            start = para_start + offset
            # Hard-split pathological sentences (e.g. flattened tables).
            while len(piece) > chunk_size:
                cut = piece.rfind(" ", 0, chunk_size)
                if cut <= chunk_size // 2:
                    cut = chunk_size
                units.append(_Unit(start, start + cut, heading))
                rest = piece[cut:]
                piece = rest.lstrip()
                start += cut + len(rest) - len(piece)
            if piece.strip():
                units.append(_Unit(start, start + len(piece), heading))
        para_start = para_end = None

    for match in re.finditer(r"[^\n]+", text):
        line = match.group().strip()
        if not line or RULE_LINE.match(line):
            flush_paragraph()
            continue
        title = _heading_text(line)
        if title:
            flush_paragraph()
            heading = title
            units.append(_Unit(match.start(), match.end(), heading, is_heading=True))
            continue
        if LIST_ITEM.match(line) or "|" in line:
            flush_paragraph()
        if para_start is None:
            para_start = match.start()
        para_end = match.end()
        # Blank line ends a paragraph.
        nxt = text[match.end():match.end() + 2]
        if nxt == "\n\n" or LIST_ITEM.match(line) or "|" in line:
            flush_paragraph()
    flush_paragraph()
    return units


def chunk_text(
    text: str,
    page_starts: list[tuple[int, int]],
    chunk_size: int = 900,
    overlap: int = 150,
    min_chunk: int = 250,
) -> list[Chunk]:
    units = _units(text, chunk_size)
    page_offsets = [start for _, start in page_starts]

    def page_of(offset: int) -> int | None:
        if not page_starts:
            return None
        return page_starts[max(0, bisect.bisect_right(page_offsets, offset) - 1)][0]

    chunks: list[Chunk] = []
    current: list[_Unit] = []

    def size(us: list[_Unit]) -> int:
        return us[-1].end - us[0].start if us else 0

    def emit() -> None:
        body = [u for u in current if not u.is_heading] or current
        start, end = current[0].start, current[-1].end
        content = text[start:end].strip()
        if len(content) < 40 and all(u.is_heading for u in current):
            return
        chunks.append(Chunk(
            index=len(chunks),
            content=content,
            start_char=start,
            end_char=end,
            heading=body[0].heading,
            page=page_of(body[0].start),
        ))

    for unit in units:
        if unit.is_heading and current and size(current) >= min_chunk:
            emit()
            current = []
        elif current and unit.end - current[0].start > chunk_size:
            emit()
            # Carry the last sentences over so context is not lost at the boundary.
            carry: list[_Unit] = []
            for prev in reversed(current):
                if prev.is_heading or sum(u.length for u in carry) + prev.length > overlap:
                    break
                carry.insert(0, prev)
            current = carry
        current.append(unit)
    if current:
        emit()
    return chunks

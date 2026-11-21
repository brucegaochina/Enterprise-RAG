"""Turn uploaded files into plain text while keeping page boundaries,
so that every chunk can later be cited with its page number."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from docx import Document as DocxDocument
from docx.table import Table as DocxTable
from docx.text.paragraph import Paragraph as DocxParagraph
from pypdf import PdfReader

BULLET_GLYPH = re.compile(r"^\s*[\x7f\u2022\u25aa\u25cf\u25e6\uf0b7]\s+")

SUPPORTED_TYPES = {".pdf": "pdf", ".docx": "docx", ".md": "md", ".markdown": "md", ".txt": "txt"}


@dataclass
class ParsedDocument:
    text: str
    title: str | None = None
    # (page_number, start_offset) for every page, in order
    page_starts: list[tuple[int, int]] = field(default_factory=list)

    @property
    def num_pages(self) -> int | None:
        return len(self.page_starts) or None


def parse_file(path: Path, file_type: str) -> ParsedDocument:
    if file_type == "pdf":
        return _parse_pdf(path)
    if file_type == "docx":
        return _parse_docx(path)
    if file_type in ("md", "txt"):
        return _parse_text(path)
    raise ValueError(f"Unsupported file type: {file_type}")


def _normalise(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _parse_pdf(path: Path) -> ParsedDocument:
    reader = PdfReader(str(path))
    pages = [_normalise(_layout_text(page)) for page in reader.pages]

    # Drop running headers/footers: lines that repeat on most pages (digits ignored).
    if len(pages) >= 2:
        def key(line: str) -> str:
            return re.sub(r"\d+", "#", line.strip().lower())

        counts = Counter(k for p in pages for k in {key(l) for l in p.splitlines() if l.strip()})
        boilerplate = {k for k, n in counts.items() if n >= max(2, int(len(pages) * 0.6))}
        pages = ["\n".join(l for l in p.splitlines() if key(l) not in boilerplate) for p in pages]

    text, page_starts = "", []
    for number, page_text in enumerate(pages, start=1):
        if text:
            text += "\n\n"
        page_starts.append((number, len(text)))
        text += page_text

    meta_title = None
    try:
        meta_title = (reader.metadata.title or "").strip() if reader.metadata else None
    except Exception:  # malformed metadata should never block ingestion
        meta_title = None
    return ParsedDocument(text=text, title=meta_title or _first_line(text), page_starts=page_starts)


def _layout_text(page) -> str:
    """Layout mode keeps table rows on one line; wide gaps between columns become ' | '."""
    try:
        text = page.extract_text(extraction_mode="layout") or ""
    except Exception:  # some malformed PDFs only work with the default extractor
        return page.extract_text() or ""
    lines = []
    for line in text.splitlines():
        line = BULLET_GLYPH.sub("- ", line)
        lines.append(re.sub(r"(?<=\S) {3,}(?=\S)", " | ", line))
    return "\n".join(lines)


def _parse_docx(path: Path) -> ParsedDocument:
    doc = DocxDocument(str(path))
    lines: list[str] = []
    title = (doc.core_properties.title or "").strip() or None

    for element in doc.element.body.iterchildren():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "p":
            para = DocxParagraph(element, doc)
            text = para.text.strip()
            if not text:
                continue
            style = (para.style.name if para.style is not None else "").lower()
            if style == "title":
                lines.append(f"# {text}")
                title = title or text
            elif style.startswith("heading"):
                level = int(style[-1]) if style[-1].isdigit() else 1
                lines.append(f"{'#' * min(level + 1, 6)} {text}")
            elif "list" in style:
                lines.append(f"- {text}")
            else:
                lines.append(text)
            lines.append("")
        elif tag == "tbl":
            table = DocxTable(element, doc)
            for row in table.rows:
                lines.append(" | ".join(cell.text.strip() for cell in row.cells))
            lines.append("")

    text = _normalise("\n".join(lines))
    return ParsedDocument(text=text, title=title or _first_line(text), page_starts=[])


def _parse_text(path: Path) -> ParsedDocument:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    text = _normalise(text)
    return ParsedDocument(text=text, title=_first_line(text), page_starts=[])


def _first_line(text: str) -> str | None:
    for line in text.splitlines():
        line = line.strip().lstrip("#").strip()
        if line:
            return line[:200]
    return None

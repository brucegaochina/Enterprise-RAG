"""Render the markdown sources in sample_data/source into a realistic mix of
PDF, DOCX, Markdown and plain-text files in sample_data/documents.

    python scripts/generate_sample_docs.py
"""

from __future__ import annotations

import re
import shutil
from html import escape
from pathlib import Path

from docx import Document as DocxDocument
from docx.shared import Pt, RGBColor
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "sample_data" / "source"
OUTPUT_DIR = ROOT / "sample_data" / "documents"

FORMATS = {
    "01": "pdf", "02": "pdf", "03": "md", "04": "pdf", "05": "docx",
    "06": "pdf", "07": "md", "08": "docx", "09": "md", "10": "docx",
    "11": "pdf", "12": "md", "13": "txt", "14": "pdf", "15": "docx",
    "16": "md", "17": "pdf", "18": "md", "19": "pdf", "20": "txt",
}

PAGEBREAK = "<!-- pagebreak -->"


def parse_blocks(markdown: str) -> list[tuple[str, object]]:
    """Very small markdown reader: headings, paragraphs, bullets, numbered lists, tables."""
    blocks: list[tuple[str, object]] = []
    lines = markdown.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            i += 1
            continue
        if line.strip() == PAGEBREAK:
            blocks.append(("pagebreak", None))
            i += 1
            continue
        if line.startswith("# "):
            blocks.append(("title", line[2:].strip()))
            i += 1
            continue
        if line.startswith("## "):
            blocks.append(("heading", line[3:].strip()))
            i += 1
            continue
        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows.append(cells)
                i += 1
            blocks.append(("table", rows))
            continue
        if line.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(lines[i][2:].strip())
                i += 1
            blocks.append(("bullets", items))
            continue
        if re.match(r"^\d+\.\s", line):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s", lines[i]):
                items.append(re.sub(r"^\d+\.\s", "", lines[i]).strip())
                i += 1
            blocks.append(("numbered", items))
            continue
        para = [line.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#|\||- |\d+\.\s|<!--)", lines[i]):
            para.append(lines[i].strip())
            i += 1
        blocks.append(("paragraph", " ".join(para)))
    return blocks


def render_pdf(blocks, out: Path, title: str) -> None:
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=10.5, leading=15, spaceAfter=8)
    h1 = ParagraphStyle("h1", parent=styles["Title"], fontSize=20, leading=24, spaceAfter=14,
                        textColor=colors.HexColor("#0b3d91"), alignment=0)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=13.5, leading=17, spaceBefore=10,
                        spaceAfter=6, textColor=colors.HexColor("#0b3d91"))
    cell = ParagraphStyle("cell", parent=body, fontSize=9.5, leading=12, spaceAfter=0)

    story = []
    for kind, value in blocks:
        if kind == "title":
            story.append(Paragraph(escape(value), h1))
        elif kind == "heading":
            story.append(Paragraph(escape(value), h2))
        elif kind == "paragraph":
            story.append(Paragraph(escape(value), body))
        elif kind in ("bullets", "numbered"):
            items = [ListItem(Paragraph(escape(t), body), leftIndent=12) for t in value]
            story.append(ListFlowable(items, bulletType="bullet" if kind == "bullets" else "1",
                                      start=None if kind == "bullets" else 1, leftIndent=14))
        elif kind == "table":
            data = [[Paragraph(escape(c), cell) for c in row] for row in value]
            table = Table(data, hAlign="LEFT", repeatRows=1,
                          colWidths=[(LETTER[0] - 2 * inch) / len(value[0])] * len(value[0]))
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef9")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#b8c4d9")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.extend([table, Spacer(1, 10)])
        elif kind == "pagebreak":
            story.append(PageBreak())

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.grey)
        canvas.drawString(inch, 0.6 * inch, f"Helios Dynamics | {title} | Internal")
        canvas.drawRightString(LETTER[0] - inch, 0.6 * inch, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(out), pagesize=LETTER, title=title, author="Helios Dynamics",
                            leftMargin=inch, rightMargin=inch, topMargin=0.9 * inch, bottomMargin=inch)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def render_docx(blocks, out: Path, title: str) -> None:
    doc = DocxDocument()
    doc.core_properties.title = title
    doc.core_properties.author = "Helios Dynamics"
    doc.styles["Normal"].font.size = Pt(11)
    for kind, value in blocks:
        if kind == "title":
            heading = doc.add_heading(value, level=0)
            for run in heading.runs:
                run.font.color.rgb = RGBColor(0x0B, 0x3D, 0x91)
        elif kind == "heading":
            doc.add_heading(value, level=1)
        elif kind == "paragraph":
            doc.add_paragraph(value)
        elif kind == "bullets":
            for item in value:
                doc.add_paragraph(item, style="List Bullet")
        elif kind == "numbered":
            for item in value:
                doc.add_paragraph(item, style="List Number")
        elif kind == "table":
            table = doc.add_table(rows=len(value), cols=len(value[0]))
            table.style = "Light Grid Accent 1"
            for r, row in enumerate(value):
                for c, text in enumerate(row):
                    table.cell(r, c).text = text
        elif kind == "pagebreak":
            doc.add_page_break()
    doc.save(str(out))


def render_txt(blocks, out: Path) -> None:
    parts: list[str] = []
    for kind, value in blocks:
        if kind == "title":
            parts.append(f"{value}\n{'=' * len(value)}")
        elif kind == "heading":
            parts.append(value)
        elif kind == "paragraph":
            parts.append(value)
        elif kind == "bullets":
            parts.append("\n".join(f"* {item}" for item in value))
        elif kind == "numbered":
            parts.append("\n".join(f"{n}. {item}" for n, item in enumerate(value, 1)))
        elif kind == "table":
            parts.append("\n".join(" | ".join(row) for row in value))
    out.write_text("\n\n".join(parts) + "\n", encoding="utf-8")


def main() -> None:
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    for src in sorted(SOURCE_DIR.glob("*.md")):
        prefix = src.stem.split("_", 1)[0]
        fmt = FORMATS[prefix]
        markdown = src.read_text(encoding="utf-8")
        blocks = parse_blocks(markdown)
        title = next((v for k, v in blocks if k == "title"), src.stem)
        out = OUTPUT_DIR / f"{src.stem}.{fmt}"

        if fmt == "pdf":
            render_pdf(blocks, out, title)
        elif fmt == "docx":
            render_docx(blocks, out, title)
        elif fmt == "txt":
            render_txt(blocks, out)
        else:
            out.write_text(markdown.replace(PAGEBREAK + "\n\n", ""), encoding="utf-8")
        print(f"  {out.name:48s} {out.stat().st_size / 1024:6.1f} KB")

    print(f"Generated {len(list(OUTPUT_DIR.iterdir()))} documents in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

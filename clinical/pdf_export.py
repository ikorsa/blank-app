"""Markdown to PDF conversion for medical reports."""

from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

PDF_FONT_NAME = "DejaVuSans"
PAGE_MARGIN_MM = 28


def register_pdf_font() -> str:
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/local/share/fonts/DejaVuSans.ttf",
    ]
    for font_path in font_paths:
        if Path(font_path).exists():
            if PDF_FONT_NAME not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(PDF_FONT_NAME, font_path))
            return PDF_FONT_NAME
    return "Helvetica"


def _inline_markup(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`(.+?)`", r"<font name='Courier'>\1</font>", text)
    return text


def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and "|" in stripped[1:]


def _is_separator_row(line: str) -> bool:
    return bool(re.fullmatch(r"\|?[\s:\-|]+\|?", line.strip()))


def _parse_table_row(line: str) -> list[str]:
    parts = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return [_inline_markup(cell) for cell in parts]


def _make_styles(font_name: str) -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle(
            "MdH1",
            parent=base["Heading1"],
            fontName=font_name,
            fontSize=16,
            leading=20,
            spaceBefore=8,
            spaceAfter=10,
            alignment=TA_JUSTIFY,
        ),
        "h2": ParagraphStyle(
            "MdH2",
            parent=base["Heading2"],
            fontName=font_name,
            fontSize=13,
            leading=17,
            spaceBefore=12,
            spaceAfter=6,
            alignment=TA_JUSTIFY,
        ),
        "h3": ParagraphStyle(
            "MdH3",
            parent=base["Heading3"],
            fontName=font_name,
            fontSize=12,
            leading=15,
            spaceBefore=8,
            spaceAfter=4,
            alignment=TA_JUSTIFY,
        ),
        "normal": ParagraphStyle(
            "MdNormal",
            parent=base["Normal"],
            fontName=font_name,
            fontSize=11,
            leading=15,
            spaceAfter=6,
            alignment=TA_JUSTIFY,
        ),
        "bullet": ParagraphStyle(
            "MdBullet",
            parent=base["Normal"],
            fontName=font_name,
            fontSize=11,
            leading=15,
            leftIndent=10,
            bulletIndent=0,
            spaceAfter=3,
            alignment=TA_JUSTIFY,
        ),
        "quote": ParagraphStyle(
            "MdQuote",
            parent=base["Normal"],
            fontName=font_name,
            fontSize=10.5,
            leading=14,
            leftIndent=12,
            rightIndent=6,
            textColor=colors.HexColor("#333333"),
            spaceAfter=8,
            alignment=TA_JUSTIFY,
        ),
    }


def _table_col_widths(col_count: int, available_mm: float) -> list[float]:
    if col_count == 4:
        weights = [0.18, 0.22, 0.24, 0.36]
    elif col_count == 3:
        weights = [0.22, 0.30, 0.48]
    elif col_count == 2:
        weights = [0.32, 0.68]
    else:
        weights = [1.0 / col_count] * col_count
    return [available_mm * weight * mm for weight in weights]


def _table_from_rows(rows: list[list[str]], styles: dict[str, ParagraphStyle], available_mm: float) -> Table:
    cell_style = ParagraphStyle(
        "MdTableCell",
        parent=styles["normal"],
        fontSize=9.5,
        leading=12,
        alignment=TA_JUSTIFY,
    )
    wrapped = [[Paragraph(cell, cell_style) for cell in row] for row in rows]
    col_count = max(len(row) for row in wrapped)
    table = Table(
        wrapped,
        colWidths=_table_col_widths(col_count, available_mm),
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), styles["normal"].fontName),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF7")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1A1A1A")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#B0B8C4")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def build_markdown_pdf(markdown_text: str, title: str) -> bytes:
    font_name = register_pdf_font()
    styles = _make_styles(font_name)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=PAGE_MARGIN_MM * mm,
        rightMargin=PAGE_MARGIN_MM * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )
    available_mm = (A4[0] / mm) - (2 * PAGE_MARGIN_MM)

    story: list = [Paragraph(_inline_markup(title), styles["h1"]), Spacer(1, 4 * mm)]
    lines = markdown_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            story.append(Spacer(1, 2 * mm))
            i += 1
            continue

        if stripped == "---":
            story.append(Spacer(1, 3 * mm))
            i += 1
            continue

        if stripped.startswith("# ") and not stripped.startswith("## "):
            story.append(Paragraph(_inline_markup(stripped[2:]), styles["h1"]))
            i += 1
            continue

        if stripped.startswith("## "):
            story.append(Paragraph(_inline_markup(stripped[3:]), styles["h2"]))
            i += 1
            continue

        if stripped.startswith("### "):
            story.append(Paragraph(_inline_markup(stripped[4:]), styles["h3"]))
            i += 1
            continue

        if _is_table_row(stripped):
            table_rows: list[list[str]] = []
            while i < len(lines) and _is_table_row(lines[i].strip()):
                row_line = lines[i].strip()
                if not _is_separator_row(row_line):
                    table_rows.append(_parse_table_row(row_line))
                i += 1
            if table_rows:
                story.append(_table_from_rows(table_rows, styles, available_mm))
                story.append(Spacer(1, 3 * mm))
            continue

        if stripped.startswith("- "):
            story.append(Paragraph(f"• {_inline_markup(stripped[2:])}", styles["bullet"]))
            i += 1
            continue

        numbered = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if numbered:
            story.append(
                Paragraph(
                    f"{numbered.group(1)}. {_inline_markup(numbered.group(2))}",
                    styles["bullet"],
                )
            )
            i += 1
            continue

        if stripped.startswith("> "):
            quote = stripped[2:]
            if "python scripts" in quote.lower():
                i += 1
                continue
            story.append(Paragraph(_inline_markup(quote), styles["quote"]))
            i += 1
            continue

        story.append(Paragraph(_inline_markup(stripped), styles["normal"]))
        i += 1

    doc.build(story)
    return buffer.getvalue()


def build_text_pdf(body: str, title: str) -> bytes:
    """Plain text lines to PDF (for calculator exports)."""
    font_name = register_pdf_font()
    styles = _make_styles(font_name)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=PAGE_MARGIN_MM * mm,
        rightMargin=PAGE_MARGIN_MM * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )
    story = [Paragraph(_inline_markup(title), styles["h1"]), Spacer(1, 4 * mm)]
    for line in body.splitlines():
        text = line if line.strip() else "&nbsp;"
        story.append(Paragraph(_inline_markup(text), styles["normal"]))
    doc.build(story)
    return buffer.getvalue()

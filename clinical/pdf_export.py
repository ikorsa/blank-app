"""Shared PDF export for clinical calculators."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

PDF_FONT_NAME = "DejaVuSans"


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


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_text_pdf(body: str, title: str) -> bytes:
    buffer = BytesIO()
    font_name = register_pdf_font()
    styles = getSampleStyleSheet()
    normal = ParagraphStyle(
        "ClinicalNormal",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=10,
        leading=14,
        spaceAfter=4,
    )
    heading = ParagraphStyle(
        "ClinicalHeading",
        parent=styles["Heading1"],
        fontName=font_name,
        fontSize=14,
        leading=18,
        spaceAfter=8,
    )
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
    )
    story = [Paragraph(_escape(title), heading), Spacer(1, 4 * mm)]
    for line in body.splitlines():
        text = line if line.strip() else "&nbsp;"
        story.append(Paragraph(_escape(text), normal))
    doc.build(story)
    return buffer.getvalue()

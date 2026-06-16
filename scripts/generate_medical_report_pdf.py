#!/usr/bin/env python3
"""Generate PDF version of the 2026 medical activity report."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clinical.pdf_export import build_markdown_pdf

REPORT_MD = ROOT / "docs" / "MEDICAL_REPORT_2026.md"
OUTPUT_PDF = ROOT / "docs" / "MEDICAL_REPORT_2026.pdf"
REPORT_TITLE = "Отчёт о проделанной работе"


def main() -> None:
    body = REPORT_MD.read_text(encoding="utf-8")
    pdf = build_markdown_pdf(body, REPORT_TITLE)
    OUTPUT_PDF.write_bytes(pdf)
    print(f"Saved: {OUTPUT_PDF}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate PDF version of the 2026 medical activity report."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clinical.pdf_export import build_text_pdf

REPORT_MD = ROOT / "docs" / "MEDICAL_REPORT_2026.md"
OUTPUT_PDF = ROOT / "docs" / "MEDICAL_REPORT_2026.pdf"


def main() -> None:
    body = REPORT_MD.read_text(encoding="utf-8")
    pdf = build_text_pdf(body, "Отчёт по медицинской деятельности — 2026")
    OUTPUT_PDF.write_bytes(pdf)
    print(f"Saved: {OUTPUT_PDF}")


if __name__ == "__main__":
    main()

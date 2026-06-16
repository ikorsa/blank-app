#!/usr/bin/env python3
"""Generate DOCX version of the 2026 medical activity report."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clinical.docx_export import build_markdown_docx

REPORT_MD = ROOT / "docs" / "MEDICAL_REPORT_2026.md"
OUTPUT_DOCX = ROOT / "docs" / "MEDICAL_REPORT_2026.docx"


REPORT_TITLE = "Отчёт о проделанной работе"


def main() -> None:
    body = REPORT_MD.read_text(encoding="utf-8")
    docx = build_markdown_docx(body, REPORT_TITLE)
    OUTPUT_DOCX.write_bytes(docx)
    print(f"Saved: {OUTPUT_DOCX}")


if __name__ == "__main__":
    main()

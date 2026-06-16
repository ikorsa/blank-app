#!/usr/bin/env python3
"""Generate HTML version of the medical report (opens reliably in Word)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clinical.html_export import build_markdown_html

REPORT_MD = ROOT / "docs" / "MEDICAL_REPORT_2026.md"
OUTPUT_HTML = ROOT / "docs" / "MEDICAL_REPORT_2026.html"


REPORT_TITLE = "Отчёт о проделанной работе"


def main() -> None:
    body = REPORT_MD.read_text(encoding="utf-8")
    OUTPUT_HTML.write_text(
        build_markdown_html(body, REPORT_TITLE),
        encoding="utf-8",
    )
    print(f"Saved: {OUTPUT_HTML}")


if __name__ == "__main__":
    main()

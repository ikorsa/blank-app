"""Markdown to HTML for opening in Microsoft Word."""

from __future__ import annotations

import html
import re


def _inline_html(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|")


def _is_separator_row(line: str) -> bool:
    return bool(re.fullmatch(r"\|?[\s:\-|]+\|?", line.strip()))


def build_markdown_html(markdown_text: str, title: str) -> str:
    parts = [
        "<!DOCTYPE html>",
        '<html lang="ru">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>{html.escape(title)}</title>",
        "<style>",
        "body { font-family: 'Times New Roman', serif; font-size: 12pt; margin: 2cm; }",
        "h1 { text-align: center; font-size: 18pt; }",
        "h2 { font-size: 14pt; margin-top: 18px; }",
        "h3 { font-size: 12pt; margin-top: 14px; }",
        "table { border-collapse: collapse; width: 100%; margin: 12px 0; }",
        "th, td { border: 1px solid #444; padding: 6px; vertical-align: top; }",
        "th { background: #e8eef7; }",
        "blockquote { margin-left: 1cm; color: #333; font-style: italic; }",
        "ul, ol { margin-top: 0; }",
        "</style>",
        "</head>",
        "<body>",
        f"<h1>{html.escape(title)}</h1>",
    ]

    lines = markdown_text.splitlines()
    i = 0
    skip_first_h1 = True

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped or stripped == "---":
            i += 1
            continue

        if stripped.startswith("# ") and not stripped.startswith("## "):
            heading = _strip_plain(stripped[2:])
            if skip_first_h1 and heading == title:
                skip_first_h1 = False
                i += 1
                continue
            parts.append(f"<h1>{_inline_html(stripped[2:])}</h1>")
            i += 1
            continue

        if stripped.startswith("## "):
            parts.append(f"<h2>{_inline_html(stripped[3:])}</h2>")
            i += 1
            continue

        if stripped.startswith("### "):
            parts.append(f"<h3>{_inline_html(stripped[4:])}</h3>")
            i += 1
            continue

        if _is_table_row(stripped):
            rows: list[list[str]] = []
            while i < len(lines) and _is_table_row(lines[i].strip()):
                row_line = lines[i].strip()
                if not _is_separator_row(row_line):
                    rows.append([cell.strip() for cell in row_line.strip("|").split("|")])
                i += 1
            if rows:
                parts.append("<table>")
                for r_idx, row in enumerate(rows):
                    parts.append("<tr>")
                    tag = "th" if r_idx == 0 else "td"
                    for cell in row:
                        parts.append(f"<{tag}>{_inline_html(cell)}</{tag}>")
                    parts.append("</tr>")
                parts.append("</table>")
            continue

        if stripped.startswith("- "):
            parts.append(f"<ul><li>{_inline_html(stripped[2:])}</li></ul>")
            i += 1
            continue

        numbered = re.match(r"^(\d+)\.\s+(.+)$", stripped)
        if numbered:
            parts.append(f"<ol start='{numbered.group(1)}'><li>{_inline_html(numbered.group(2))}</li></ol>")
            i += 1
            continue

        if stripped.startswith("> "):
            quote = stripped[2:]
            if "docs/MEDICAL" in quote:
                i += 1
                continue
            parts.append(f"<blockquote><p>{_inline_html(quote)}</p></blockquote>")
            i += 1
            continue

        parts.append(f"<p>{_inline_html(stripped)}</p>")
        i += 1

    parts.extend(["</body>", "</html>"])
    return "\n".join(parts)


def _strip_plain(text: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"\1", text).strip()

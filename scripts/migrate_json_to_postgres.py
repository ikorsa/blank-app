#!/usr/bin/env python3
"""One-time migration: data/*.json -> PostgreSQL. Requires ANAMNES_DATABASE_URL."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from anamnes_storage import (  # noqa: E402
    DATABASE_URL,
    DOCTORS_FILE,
    DRAFTS_DIR,
    SUBMISSIONS_DIR,
    init_postgres_schema,
    save_draft_record,
    upsert_doctor,
    write_submission_record,
)


def main() -> None:
    if not DATABASE_URL:
        raise SystemExit("Set ANAMNES_DATABASE_URL before running migration.")

    init_postgres_schema()
    doctors_count = 0
    if DOCTORS_FILE.exists():
        raw = json.loads(DOCTORS_FILE.read_text(encoding="utf-8"))
        items = raw.get("doctors", raw) if isinstance(raw, dict) else raw
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    upsert_doctor(item)
                    doctors_count += 1

    submissions_count = 0
    for path in SUBMISSIONS_DIR.glob("*.json"):
        submission = json.loads(path.read_text(encoding="utf-8"))
        submission.setdefault("summary", "")
        write_submission_record(submission)
        submissions_count += 1

    drafts_count = 0
    for path in DRAFTS_DIR.glob("*.json"):
        draft = json.loads(path.read_text(encoding="utf-8"))
        save_draft_record(draft)
        drafts_count += 1

    print(
        f"Migration complete: doctors={doctors_count}, "
        f"submissions={submissions_count}, drafts={drafts_count}"
    )


if __name__ == "__main__":
    main()

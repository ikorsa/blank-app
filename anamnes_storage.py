"""JSON file storage (default) or PostgreSQL when ANAMNES_DATABASE_URL is set."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DATA_DIR = Path(os.getenv("ANAMNES_DATA_DIR", "data"))
SUBMISSIONS_DIR = DATA_DIR / "submissions"
DRAFTS_DIR = DATA_DIR / "drafts"
DRAFT_UPLOADS_DIR = DATA_DIR / "draft_uploads"
DOCTORS_FILE = Path(os.getenv("ANAMNES_DOCTORS_FILE", str(DATA_DIR / "doctors.json")))
DRAFT_RETENTION_DAYS = int(os.getenv("ANAMNES_DRAFT_RETENTION_DAYS", "30"))


def _load_env_files() -> None:
    root = Path(__file__).resolve().parent
    for env_path in (
        root / ".env",
        root / "config" / "database.env",
        Path(os.getenv("ANAMNES_DATA_DIR", str(root / "data"))).parent / "config" / "database.env",
    ):
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_env_files()


def get_database_url() -> str:
    return os.getenv("ANAMNES_DATABASE_URL", "").strip()


def use_postgres() -> bool:
    return bool(get_database_url())


def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-zА-Яа-я0-9._-]+", "_", name).strip("._")
    return cleaned or "file"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_doctor(doctor: dict[str, Any], include_inactive: bool = False) -> dict[str, str]:
    doctor_id = safe_filename(str(doctor.get("id") or doctor.get("slug") or "")).lower()
    is_active = doctor.get("is_active", True)
    if isinstance(is_active, str):
        is_active = is_active.lower() not in {"false", "0", "no"}
    if not include_inactive and not is_active:
        return {}
    return {
        "id": doctor_id,
        "name": str(doctor.get("name") or doctor_id or "Врач"),
        "specialty": str(doctor.get("specialty") or "Эндокринолог"),
        "email": str(doctor.get("email") or ""),
        "telegram_chat_id": str(doctor.get("telegram_chat_id") or ""),
        "password": str(doctor.get("password") or ""),
        "is_active": "true" if is_active else "false",
    }


def default_doctor_record() -> dict[str, str]:
    admin_password = os.getenv("ANAMNES_ADMIN_PASSWORD", "admin")
    smtp_to = os.getenv("ANAMNES_SMTP_TO", "")
    telegram_chat = os.getenv("ANAMNES_TELEGRAM_CHAT_ID", "")
    return {
        "id": "default",
        "name": "Врач по умолчанию",
        "specialty": "Эндокринолог",
        "email": smtp_to,
        "telegram_chat_id": telegram_chat,
        "password": admin_password,
        "is_active": "true",
    }


def init_storage_dirs() -> None:
    SUBMISSIONS_DIR.mkdir(parents=True, exist_ok=True)
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    DRAFT_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def _pg_connect():
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(get_database_url(), row_factory=dict_row)


def init_postgres_schema() -> None:
    with _pg_connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS doctors (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                specialty TEXT NOT NULL DEFAULT 'Эндокринолог',
                email TEXT NOT NULL DEFAULT '',
                telegram_chat_id TEXT NOT NULL DEFAULT '',
                password TEXT NOT NULL DEFAULT '',
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS submissions (
                id TEXT PRIMARY KEY,
                doctor_id TEXT REFERENCES doctors(id),
                status TEXT NOT NULL DEFAULT 'submitted',
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL,
                viewed_at TIMESTAMPTZ,
                payload JSONB NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_submissions_doctor ON submissions(doctor_id);
            CREATE INDEX IF NOT EXISTS idx_submissions_status ON submissions(status);
            CREATE INDEX IF NOT EXISTS idx_submissions_created ON submissions(created_at DESC);
            CREATE TABLE IF NOT EXISTS drafts (
                id TEXT PRIMARY KEY,
                doctor_id TEXT,
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL,
                payload JSONB NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_drafts_updated ON drafts(updated_at DESC);
            """
        )
        conn.commit()


def init_storage() -> None:
    init_storage_dirs()
    if use_postgres():
        init_postgres_schema()


def _write_doctors_json(doctors: list[dict[str, str]]) -> None:
    DOCTORS_FILE.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for doctor in doctors:
        row = {
            "id": doctor["id"],
            "name": doctor["name"],
            "specialty": doctor["specialty"],
            "email": doctor.get("email", ""),
            "telegram_chat_id": doctor.get("telegram_chat_id", ""),
            "password": doctor.get("password", ""),
        }
        if doctor.get("is_active") == "false":
            row["is_active"] = False
        rows.append(row)
    DOCTORS_FILE.write_text(json.dumps({"doctors": rows}, ensure_ascii=False, indent=2), encoding="utf-8")


def load_doctors(*, include_inactive: bool = False) -> list[dict[str, str]]:
    init_storage()
    if use_postgres():
        with _pg_connect() as conn:
            rows = conn.execute(
                "SELECT id, name, specialty, email, telegram_chat_id, password, is_active "
                "FROM doctors ORDER BY name"
            ).fetchall()
        doctors = []
        for row in rows:
            item = normalize_doctor(dict(row), include_inactive=include_inactive)
            if item:
                doctors.append(item)
        return doctors or [default_doctor_record()]

    if not DOCTORS_FILE.exists():
        return [default_doctor_record()]
    try:
        raw = json.loads(DOCTORS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return [default_doctor_record()]

    items = raw.get("doctors", raw) if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return [default_doctor_record()]

    doctors = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized = normalize_doctor(item, include_inactive=include_inactive)
        if normalized.get("id"):
            doctors.append(normalized)
    return doctors or [default_doctor_record()]


def get_doctor_by_id(doctor_id: str, *, include_inactive: bool = False) -> dict[str, str] | None:
    doctor_id = safe_filename(doctor_id).lower()
    return next(
        (doctor for doctor in load_doctors(include_inactive=include_inactive) if doctor["id"] == doctor_id),
        None,
    )


def upsert_doctor(doctor: dict[str, Any]) -> dict[str, str]:
    record = normalize_doctor(doctor, include_inactive=True)
    if not record.get("id"):
        raise ValueError("У врача должен быть указан id (латиница, slug).")
    if not record.get("name"):
        raise ValueError("Укажите ФИО врача.")

    if not record.get("password"):
        existing = get_doctor_by_id(record["id"], include_inactive=True)
        if existing and existing.get("password"):
            record["password"] = existing["password"]

    init_storage()
    if use_postgres():
        is_active = doctor.get("is_active", True)
        if isinstance(is_active, str):
            is_active = is_active.lower() not in {"false", "0", "no"}
        else:
            is_active = is_active is not False
        with _pg_connect() as conn:
            conn.execute(
                """
                INSERT INTO doctors (id, name, specialty, email, telegram_chat_id, password, is_active, updated_at)
                VALUES (%(id)s, %(name)s, %(specialty)s, %(email)s, %(telegram_chat_id)s, %(password)s, %(is_active)s, NOW())
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    specialty = EXCLUDED.specialty,
                    email = EXCLUDED.email,
                    telegram_chat_id = EXCLUDED.telegram_chat_id,
                    password = EXCLUDED.password,
                    is_active = EXCLUDED.is_active,
                    updated_at = NOW()
                """,
                {
                    "id": record["id"],
                    "name": record["name"],
                    "specialty": record["specialty"],
                    "email": record["email"],
                    "telegram_chat_id": record["telegram_chat_id"],
                    "password": record["password"],
                    "is_active": is_active,
                },
            )
            conn.commit()
        return record

    doctors = load_doctors(include_inactive=True)
    replaced = False
    for index, item in enumerate(doctors):
        if item["id"] == record["id"]:
            if doctor.get("password") in ("", None) and item.get("password"):
                record["password"] = item["password"]
            doctors[index] = record
            replaced = True
            break
    if not replaced:
        doctors.append(record)
    _write_doctors_json(doctors)
    return record


def set_doctor_active(doctor_id: str, *, active: bool) -> None:
    doctor = get_doctor_by_id(doctor_id, include_inactive=True)
    if not doctor:
        raise FileNotFoundError(f"Врач {doctor_id} не найден")
    doctor["is_active"] = "true" if active else "false"
    upsert_doctor(doctor)


def write_submission_record(submission: dict[str, Any]) -> None:
    init_storage()
    submission = dict(submission)
    doctor_id = str(submission.get("assigned_doctor", {}).get("id") or "")
    if use_postgres():
        with _pg_connect() as conn:
            conn.execute(
                """
                INSERT INTO submissions (id, doctor_id, status, created_at, updated_at, viewed_at, payload)
                VALUES (%(id)s, %(doctor_id)s, %(status)s, %(created_at)s::timestamptz, %(updated_at)s::timestamptz,
                        %(viewed_at)s::timestamptz, %(payload)s::jsonb)
                ON CONFLICT (id) DO UPDATE SET
                    doctor_id = EXCLUDED.doctor_id,
                    status = EXCLUDED.status,
                    updated_at = EXCLUDED.updated_at,
                    viewed_at = EXCLUDED.viewed_at,
                    payload = EXCLUDED.payload
                """,
                {
                    "id": submission["id"],
                    "doctor_id": doctor_id or None,
                    "status": submission.get("status", "submitted"),
                    "created_at": submission.get("created_at", now_iso()),
                    "updated_at": now_iso(),
                    "viewed_at": submission.get("viewed_at"),
                    "payload": json.dumps(submission, ensure_ascii=False),
                },
            )
            conn.commit()
        return

    (SUBMISSIONS_DIR / f"{submission['id']}.json").write_text(
        json.dumps(submission, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_submissions() -> list[dict[str, Any]]:
    init_storage()
    if use_postgres():
        with _pg_connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM submissions ORDER BY created_at DESC"
            ).fetchall()
        submissions = []
        for row in rows:
            payload = row["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            submissions.append(payload)
        return submissions

    submissions = []
    for path in SUBMISSIONS_DIR.glob("*.json"):
        try:
            submissions.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return sorted(submissions, key=lambda item: item.get("created_at", ""), reverse=True)


def get_submission(submission_id: str) -> dict[str, Any] | None:
    submission_id = safe_filename(submission_id)
    if use_postgres():
        with _pg_connect() as conn:
            row = conn.execute(
                "SELECT payload FROM submissions WHERE id = %s",
                (submission_id,),
            ).fetchone()
        if not row:
            return None
        payload = row["payload"]
        return json.loads(payload) if isinstance(payload, str) else payload

    path = SUBMISSIONS_DIR / f"{submission_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def update_submission_status(submission_id: str, status: str) -> None:
    submission = get_submission(submission_id)
    if not submission:
        raise FileNotFoundError(f"Анкета {submission_id} не найдена")
    submission["status"] = status
    if status in {"viewed", "in_progress", "closed"}:
        submission["viewed_at"] = submission.get("viewed_at") or now_iso()
    write_submission_record(submission)


def update_doctor_fields(
    submission_id: str,
    status: str,
    note: str,
    requested_documents: str,
    appointment_date: str,
) -> None:
    submission = get_submission(submission_id)
    if not submission:
        raise FileNotFoundError(f"Анкета {submission_id} не найдена")
    submission["status"] = status
    if status in {"viewed", "in_progress", "closed"}:
        submission["viewed_at"] = submission.get("viewed_at") or now_iso()
    submission["doctor"] = {
        "note": note.strip(),
        "requested_documents": requested_documents.strip(),
        "appointment_date": appointment_date.strip(),
        "updated_at": now_iso(),
    }
    write_submission_record(submission)


def purge_expired_drafts() -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(days=DRAFT_RETENTION_DAYS)
    if use_postgres():
        with _pg_connect() as conn:
            rows = conn.execute(
                "SELECT id FROM drafts WHERE updated_at < %s",
                (cutoff,),
            ).fetchall()
            for row in rows:
                delete_draft(row["id"])
        return

    if not DRAFTS_DIR.exists():
        return
    for path in DRAFTS_DIR.glob("*.json"):
        try:
            draft = json.loads(path.read_text(encoding="utf-8"))
            updated = datetime.fromisoformat(draft.get("updated_at", draft.get("created_at", "")))
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
        if updated < cutoff:
            delete_draft(path.stem)


def load_draft(draft_id: str) -> dict[str, Any] | None:
    draft_id = safe_filename(draft_id)
    if use_postgres():
        with _pg_connect() as conn:
            row = conn.execute("SELECT payload FROM drafts WHERE id = %s", (draft_id,)).fetchone()
        if not row:
            return None
        payload = row["payload"]
        return json.loads(payload) if isinstance(payload, str) else payload

    path = DRAFTS_DIR / f"{draft_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def save_draft_record(draft: dict[str, Any]) -> str:
    init_storage()
    draft_id = safe_filename(draft["id"])
    draft["id"] = draft_id
    doctor_id = str(draft.get("assigned_doctor", {}).get("id") or "")

    if use_postgres():
        with _pg_connect() as conn:
            conn.execute(
                """
                INSERT INTO drafts (id, doctor_id, created_at, updated_at, payload)
                VALUES (%(id)s, %(doctor_id)s, %(created_at)s::timestamptz, %(updated_at)s::timestamptz, %(payload)s::jsonb)
                ON CONFLICT (id) DO UPDATE SET
                    doctor_id = EXCLUDED.doctor_id,
                    updated_at = EXCLUDED.updated_at,
                    payload = EXCLUDED.payload
                """,
                {
                    "id": draft_id,
                    "doctor_id": doctor_id or None,
                    "created_at": draft.get("created_at", now_iso()),
                    "updated_at": draft.get("updated_at", now_iso()),
                    "payload": json.dumps(draft, ensure_ascii=False),
                },
            )
            conn.commit()
        return draft_id

    (DRAFTS_DIR / f"{draft_id}.json").write_text(
        json.dumps(draft, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return draft_id


def delete_draft(draft_id: str) -> None:
    draft_id = safe_filename(draft_id)
    if use_postgres():
        with _pg_connect() as conn:
            conn.execute("DELETE FROM drafts WHERE id = %s", (draft_id,))
            conn.commit()

    draft_path = DRAFTS_DIR / f"{draft_id}.json"
    if draft_path.exists():
        draft_path.unlink()

    upload_dir = DRAFT_UPLOADS_DIR / draft_id
    if upload_dir.exists():
        for file_path in upload_dir.iterdir():
            if file_path.is_file():
                file_path.unlink()
        upload_dir.rmdir()

#!/usr/bin/env bash
# PostgreSQL dump for anamnes (custom format, restorable with scripts/restore_postgres.sh).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="${ANAMNES_BACKUP_DIR:-/opt/anamnes/backups}"
RETENTION_DAYS="${ANAMNES_BACKUP_RETENTION_DAYS:-14}"

load_database_url() {
  if [[ -n "${ANAMNES_DATABASE_URL:-}" ]]; then
    return 0
  fi
  for candidate in \
    "${ANAMNES_DATABASE_ENV:-}" \
    "$ROOT_DIR/config/database.env" \
    "/opt/anamnes/config/database.env"; do
    if [[ -n "$candidate" && -f "$candidate" ]]; then
      set -a
      # shellcheck disable=SC1090
      source "$candidate"
      set +a
      break
    fi
  done
}

load_database_url

if [[ -z "${ANAMNES_DATABASE_URL:-}" ]]; then
  echo "ANAMNES_DATABASE_URL not set — skip PostgreSQL backup."
  exit 0
fi

if ! command -v pg_dump >/dev/null 2>&1; then
  echo "pg_dump not found. Install: sudo apt install -y postgresql-client" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive="$BACKUP_DIR/anamnes-pg-$timestamp.dump"

pg_dump "$ANAMNES_DATABASE_URL" --format=custom --no-owner --file="$archive"
find "$BACKUP_DIR" -name 'anamnes-pg-*.dump' -type f -mtime +"$RETENTION_DAYS" -delete

echo "Created PostgreSQL backup: $archive"
ls -lh "$archive"

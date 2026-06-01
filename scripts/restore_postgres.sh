#!/usr/bin/env bash
# Restore PostgreSQL from a pg_dump custom-format archive.
# Usage: ./scripts/restore_postgres.sh /opt/anamnes/backups/anamnes-pg-YYYYMMDDTHHMMSSZ.dump
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <path-to-anamnes-pg-*.dump>" >&2
  exit 1
fi

DUMP_FILE="$1"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -f "$DUMP_FILE" ]]; then
  echo "Dump file not found: $DUMP_FILE" >&2
  exit 1
fi

if [[ -z "${ANAMNES_DATABASE_URL:-}" ]]; then
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
fi

if [[ -z "${ANAMNES_DATABASE_URL:-}" ]]; then
  echo "Set ANAMNES_DATABASE_URL or config/database.env" >&2
  exit 1
fi

if ! command -v pg_restore >/dev/null 2>&1; then
  echo "pg_restore not found. Install: sudo apt install -y postgresql-client" >&2
  exit 1
fi

echo "WARNING: this will replace data in the database pointed to by ANAMNES_DATABASE_URL."
echo "Dump: $DUMP_FILE"
echo "Press Ctrl+C within 5 seconds to abort..."
sleep 5

pg_restore --dbname="$ANAMNES_DATABASE_URL" --clean --if-exists --no-owner "$DUMP_FILE"
echo "Restore finished. Restart app: sudo systemctl restart anamnes anamnes-bot"

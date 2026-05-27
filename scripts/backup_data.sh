#!/usr/bin/env bash
set -euo pipefail

DATA_DIR="${ANAMNES_DATA_DIR:-/opt/anamnes/data}"
BACKUP_DIR="${ANAMNES_BACKUP_DIR:-/opt/anamnes/backups}"
RETENTION_DAYS="${ANAMNES_BACKUP_RETENTION_DAYS:-14}"

if [[ ! -d "$DATA_DIR" ]]; then
  echo "Data directory does not exist: $DATA_DIR" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive="$BACKUP_DIR/anamnes-data-$timestamp.tar.gz"

tar -czf "$archive" -C "$(dirname "$DATA_DIR")" "$(basename "$DATA_DIR")"
find "$BACKUP_DIR" -name 'anamnes-data-*.tar.gz' -type f -mtime +"$RETENTION_DAYS" -delete

echo "Created backup: $archive"

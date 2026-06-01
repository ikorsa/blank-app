#!/usr/bin/env bash
# Run on VPS as root: sudo bash /opt/anamnes/deploy/setup_postgres.sh
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/anamnes}"
DB_NAME="${DB_NAME:-anamnes}"
DB_USER="${DB_USER:-anamnes}"
ENV_FILE="${ENV_FILE:-/etc/anamnes.env}"
DB_ENV_FILE="${APP_DIR}/config/database.env"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root: sudo bash $0" >&2
  exit 1
fi

if ! command -v psql >/dev/null; then
  echo "PostgreSQL client not found. Install: apt install postgresql" >&2
  exit 1
fi

if [[ ! -f "${DB_ENV_FILE}" ]]; then
  DB_PASS="$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)"
  sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${DB_USER}') THEN
    CREATE ROLE ${DB_USER} LOGIN PASSWORD '${DB_PASS}';
  ELSE
    ALTER ROLE ${DB_USER} WITH PASSWORD '${DB_PASS}';
  END IF;
END
\$\$;
SELECT 'CREATE DATABASE ${DB_NAME} OWNER ${DB_USER}'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DB_NAME}')\gexec
SQL
  mkdir -p "${APP_DIR}/config"
  chown ikorsa:ikorsa "${APP_DIR}/config" 2>/dev/null || true
  cat >"${DB_ENV_FILE}" <<EOF
# Created by deploy/setup_postgres.sh — readable by app user ikorsa
ANAMNES_DATABASE_URL=postgresql://${DB_USER}:${DB_PASS}@127.0.0.1:5432/${DB_NAME}
EOF
  chmod 600 "${DB_ENV_FILE}"
  chown ikorsa:ikorsa "${DB_ENV_FILE}" 2>/dev/null || true
  echo "Wrote ${DB_ENV_FILE}"
else
  echo "Using existing ${DB_ENV_FILE}"
fi

if [[ -f "${ENV_FILE}" ]] && ! grep -q '^ANAMNES_DATABASE_URL=' "${ENV_FILE}"; then
  echo "" >>"${ENV_FILE}"
  echo "# PostgreSQL (duplicate of config/database.env for systemd)" >>"${ENV_FILE}"
  grep '^ANAMNES_DATABASE_URL=' "${DB_ENV_FILE}" >>"${ENV_FILE}"
  chmod 600 "${ENV_FILE}"
fi

cd "${APP_DIR}"
sudo -u ikorsa -H bash -lc "
  set -a
  source ${DB_ENV_FILE}
  set +a
  .venv/bin/pip install -q -r requirements.txt
  .venv/bin/python scripts/migrate_json_to_postgres.py
"

systemctl restart anamnes anamnes-bot
echo "Done. Check Streamlit sidebar: should show PostgreSQL."

#!/usr/bin/env bash
# Install/repair systemd unit for the Telegram bot (.venv python, not conda).
# Usage: sudo bash /opt/anamnes/deploy/fix-anamnes-bot-service.sh
#
# Fixes the common production bug where anamnes-bot runs under
# /home/*/anaconda3/bin/python instead of /opt/anamnes/.venv/bin/python.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib-app-user.sh
source "${SCRIPT_DIR}/lib-app-user.sh"

ANAMNES_ROOT="${ANAMNES_ROOT:-/opt/anamnes}"
ENV_FILE="${ANAMNES_ENV_FILE:-/etc/anamnes.env}"
UNIT_PATH="/etc/systemd/system/anamnes-bot.service"
VENV_PY="${ANAMNES_ROOT}/.venv/bin/python"

APP_USER="$(resolve_anamnes_app_user "${ANAMNES_ROOT}")"
APP_GROUP="$(resolve_anamnes_app_group "${APP_USER}" "${ANAMNES_ROOT}")"

echo "=== Fix anamnes-bot systemd (${APP_USER}) ==="

if [[ ! -x "${VENV_PY}" ]]; then
  echo "ERROR: Missing ${VENV_PY}"
  echo "Create venv: cd ${ANAMNES_ROOT} && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: Missing ${ENV_FILE} (copy from deploy/anamnes.env.example)"
  exit 1
fi

mkdir -p "${ANAMNES_ROOT}/data/telegram_sessions"
chown -R "${APP_USER}:${APP_GROUP}" "${ANAMNES_ROOT}/data" 2>/dev/null || true

# Stop manual/stray bot processes (conda shell, nohup, etc.)
while read -r pid cmd; do
  [[ -z "${pid}" || "${pid}" == "$$" ]] && continue
  if [[ "${cmd}" == *"telegram_bot.py"* ]]; then
    exe="$(readlink -f "/proc/${pid}/exe" 2>/dev/null || true)"
    echo "Stopping stray telegram_bot.py pid=${pid} exe=${exe:-unknown}"
    kill "${pid}" 2>/dev/null || true
    sleep 1
    kill -9 "${pid}" 2>/dev/null || true
  fi
done < <(pgrep -af "telegram_bot.py" 2>/dev/null || true)

sed -e "s/^User=.*/User=${APP_USER}/" \
    -e "s/^Group=.*/Group=${APP_GROUP}/" \
    "${ANAMNES_ROOT}/deploy/anamnes-bot.service" > "${UNIT_PATH}"

echo "Installed ${UNIT_PATH}:"
grep -E '^(User|Group|WorkingDirectory|ExecStart)=' "${UNIT_PATH}"

systemctl daemon-reload
systemctl enable anamnes-bot
systemctl restart anamnes-bot
sleep 2

if systemctl is-active anamnes-bot >/dev/null 2>&1; then
  main_pid="$(systemctl show anamnes-bot -p MainPID --value 2>/dev/null || echo 0)"
  exe=""
  if [[ -n "${main_pid}" && "${main_pid}" != "0" ]]; then
    exe="$(readlink -f "/proc/${main_pid}/exe" 2>/dev/null || true)"
  fi
  echo "OK: anamnes-bot active (pid=${main_pid}, python=${exe})"
  if [[ "${exe}" != "${VENV_PY}" ]]; then
    echo "WARN: expected python ${VENV_PY}, got ${exe}"
    exit 1
  fi
else
  echo "ERROR: anamnes-bot failed to start. Logs:"
  journalctl -u anamnes-bot -n 30 --no-pager || true
  exit 1
fi

echo ""
echo "Tail logs: sudo journalctl -u anamnes-bot -f"

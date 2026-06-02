#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./scripts/update_vps.sh [branch]
# Example:
#   ./scripts/update_vps.sh main
#   ./scripts/update_vps.sh cursor/fix-reason-step-state-8488

BRANCH="${1:-main}"
APP_DIR="${APP_DIR:-/opt/anamnes}"
VENV_PATH="${VENV_PATH:-$APP_DIR/.venv/bin/activate}"
APP_SERVICE="${APP_SERVICE:-anamnes}"
BOT_SERVICE="${BOT_SERVICE:-anamnes-bot}"
RESTART_BOT="${RESTART_BOT:-1}"

echo "==> Deploy branch: $BRANCH"
echo "==> App dir: $APP_DIR"

cd "$APP_DIR"
git fetch --all --prune
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"

if [[ -f "$VENV_PATH" ]]; then
  # shellcheck disable=SC1090
  source "$VENV_PATH"
else
  echo "ERROR: virtualenv not found at $VENV_PATH"
  exit 1
fi

pip install -r requirements.txt
sudo systemctl restart "$APP_SERVICE"
sudo systemctl status "$APP_SERVICE" --no-pager -l | sed -n '1,25p'

if [[ "$RESTART_BOT" == "1" ]]; then
  if systemctl list-unit-files | rg -q "^${BOT_SERVICE}\.service"; then
    sudo systemctl restart "$BOT_SERVICE"
    sudo systemctl status "$BOT_SERVICE" --no-pager -l | sed -n '1,15p'
  else
    echo "==> Bot service '${BOT_SERVICE}' not found, skipping"
  fi
fi

echo "==> Deploy completed"

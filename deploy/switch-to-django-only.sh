#!/usr/bin/env bash
# Switch VPS to Django-only (gunicorn :8000, nginx proxy). Run on server as root.
# Usage: sudo bash /opt/anamnes/deploy/switch-to-django-only.sh
# If there is no Unix user "anamnes", set: export ANAMNES_USER=ikorsa

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib-app-user.sh
source "${SCRIPT_DIR}/lib-app-user.sh"

ANAMNES_ROOT="${ANAMNES_ROOT:-/opt/anamnes}"
DOMAIN="${ANAMNES_DOMAIN:-anamnes.ikorsakov.tech}"
ENV_FILE="${ANAMNES_ENV_FILE:-/etc/anamnes.env}"

APP_USER="$(resolve_anamnes_app_user "${ANAMNES_ROOT}")"
APP_GROUP="$(resolve_anamnes_app_group "${APP_USER}" "${ANAMNES_ROOT}")"

echo "=== Django-only cutover (${DOMAIN}) ==="
echo "App user: ${APP_USER} (group: ${APP_GROUP})"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Create ${ENV_FILE} from deploy/anamnes.env.example first."
  exit 1
fi

if ! grep -qE '^[[:space:]]*DJANGO_DEBUG=0[[:space:]]*$' "${ENV_FILE}" 2>/dev/null; then
  echo "Add to ${ENV_FILE}:"
  echo "  DJANGO_DEBUG=0"
  echo "  DJANGO_SECRET_KEY=\$(openssl rand -base64 48)"
  echo "  DJANGO_ALLOWED_HOSTS=${DOMAIN}"
  echo "Then re-run this script."
  exit 1
fi

cd "${ANAMNES_ROOT}"
sudo -u "${APP_USER}" -H bash -lc "
  cd '${ANAMNES_ROOT}'
  source .venv/bin/activate
  pip install -q -r requirements.txt
  python manage.py migrate --noinput
  python manage.py collectstatic --noinput
  python manage.py sync_doctors_from_legacy || true
"

mkdir -p "${ANAMNES_ROOT}/media/pending_uploads"
mkdir -p "${ANAMNES_ROOT}/data/telegram_sessions"
chown -R "${APP_USER}:${APP_GROUP}" "${ANAMNES_ROOT}/media" "${ANAMNES_ROOT}/data" 2>/dev/null || true

sed -e "s/^User=.*/User=${APP_USER}/" \
    -e "s/^Group=.*/Group=${APP_GROUP}/" \
    "${ANAMNES_ROOT}/deploy/anamnes-django.service" > /etc/systemd/system/anamnes-django.service
echo "Installed systemd unit for User=${APP_USER}"

systemctl daemon-reload
systemctl enable anamnes-django
systemctl restart anamnes-django

cp "${ANAMNES_ROOT}/deploy/nginx-anamnes-django.conf.example" /etc/nginx/sites-available/anamnes
ln -sf /etc/nginx/sites-available/anamnes /etc/nginx/sites-enabled/anamnes

if [[ ! -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]]; then
  echo "Issuing certificate..."
  certbot --nginx -d "${DOMAIN}" --non-interactive --agree-tos --register-unsafely-without-email || true
fi

bash "${ANAMNES_ROOT}/deploy/fix-ssl-cert.sh" || true
nginx -t && systemctl reload nginx

if systemctl is-active anamnes >/dev/null 2>&1; then
  systemctl stop anamnes
  systemctl disable anamnes
  echo "Stopped legacy Streamlit service 'anamnes'."
fi

sed -e "s/^User=.*/User=${APP_USER}/" \
    -e "s/^Group=.*/Group=${APP_GROUP}/" \
    "${ANAMNES_ROOT}/deploy/anamnes-bot.service" > /etc/systemd/system/anamnes-bot.service
systemctl daemon-reload
systemctl enable anamnes-bot
systemctl restart anamnes-bot
echo "Installed and restarted anamnes-bot (User=${APP_USER}, .venv python)."

ANAMNES_USER="${APP_USER}" bash "${ANAMNES_ROOT}/deploy/check-production.sh" || true

echo ""
echo "Done. Test: https://${DOMAIN}/?doctor=ivanova"

#!/usr/bin/env bash
# Switch VPS to Django-only (gunicorn :8000, nginx proxy). Run on server as root.
# Usage: sudo bash /opt/anamnes/deploy/switch-to-django-only.sh

set -euo pipefail

ANAMNES_ROOT="${ANAMNES_ROOT:-/opt/anamnes}"
DOMAIN="${ANAMNES_DOMAIN:-anamnes.ikorsakov.tech}"
ENV_FILE="${ANAMNES_ENV_FILE:-/etc/anamnes.env}"
APP_USER="${ANAMNES_USER:-anamnes}"

echo "=== Django-only cutover (${DOMAIN}) ==="

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
  source .venv/bin/activate
  pip install -q -r requirements.txt
  python manage.py migrate --noinput
  python manage.py collectstatic --noinput
  python manage.py sync_doctors_from_legacy || true
"

mkdir -p "${ANAMNES_ROOT}/media/pending_uploads"
chown -R "${APP_USER}:${APP_USER}" "${ANAMNES_ROOT}/media" "${ANAMNES_ROOT}/staticfiles" 2>/dev/null || true

cp "${ANAMNES_ROOT}/deploy/anamnes-django.service" /etc/systemd/system/
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

bash "${ANAMNES_ROOT}/deploy/check-production.sh" || true

echo ""
echo "Done. Test: https://${DOMAIN}/?doctor=ivanova"

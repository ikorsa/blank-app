#!/usr/bin/env bash
# Preflight for production VPS. Run: sudo bash deploy/check-production.sh
# Expects: /etc/anamnes.env, Django at /opt/anamnes (override ANAMNES_ROOT).

set -euo pipefail

DOMAIN="${ANAMNES_DOMAIN:-anamnes.ikorsakov.tech}"
ANAMNES_ROOT="${ANAMNES_ROOT:-/opt/anamnes}"
ENV_FILE="${ANAMNES_ENV_FILE:-/etc/anamnes.env}"
NGINX_SITE="${NGINX_SITE:-/etc/nginx/sites-available/anamnes}"
FAIL=0

warn() { echo "WARN: $*"; FAIL=1; }
ok() { echo "OK: $*"; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib-app-user.sh
source "${SCRIPT_DIR}/lib-app-user.sh"
if APP_USER="$(resolve_anamnes_app_user "${ANAMNES_ROOT}" 2>/dev/null)"; then
  echo "=== Anamnes production check (${DOMAIN}), app user: ${APP_USER} ==="
else
  echo "=== Anamnes production check (${DOMAIN}) ==="
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  warn "Missing ${ENV_FILE}"
else
  ok "Found ${ENV_FILE}"
  # shellcheck disable=SC1090
  set -a
  source "${ENV_FILE}"
  set +a

  [[ "${DJANGO_DEBUG:-1}" == "0" ]] && ok "DJANGO_DEBUG=0" || warn "Set DJANGO_DEBUG=0 in ${ENV_FILE}"
  [[ -n "${DJANGO_SECRET_KEY:-}" && "${DJANGO_SECRET_KEY}" != "dev-secret-key-change-me" ]] \
    && ok "DJANGO_SECRET_KEY is set" || warn "Set DJANGO_SECRET_KEY (openssl rand -base64 48)"
  [[ "${DJANGO_ALLOWED_HOSTS:-*}" != "*" ]] \
    && ok "DJANGO_ALLOWED_HOSTS=${DJANGO_ALLOWED_HOSTS}" \
    || warn "Set DJANGO_ALLOWED_HOSTS=${DOMAIN} (not *)"
  [[ -n "${ANAMNES_ADMIN_PASSWORD:-}" && "${ANAMNES_ADMIN_PASSWORD}" != "change-me-strong-password" ]] \
    && ok "ANAMNES_ADMIN_PASSWORD is set" || warn "Set strong ANAMNES_ADMIN_PASSWORD"
  if [[ -n "${ANAMNES_SMTP_HOST:-}" ]]; then
    ok "SMTP configured (${ANAMNES_SMTP_HOST})"
  else
    warn "No ANAMNES_SMTP_HOST — email notifications disabled"
  fi
fi

echo ""
echo "=== Django ==="
if [[ -d "${ANAMNES_ROOT}/.venv" ]]; then
  (
    cd "${ANAMNES_ROOT}"
    export DJANGO_SETTINGS_MODULE=anamnes_site.settings
    if [[ -f "${ENV_FILE}" ]]; then set -a; source "${ENV_FILE}"; set +a; fi
    "${ANAMNES_ROOT}/.venv/bin/python" manage.py check --deploy 2>&1 | tail -20
  ) || warn "manage.py check --deploy reported issues"
else
  warn "No venv at ${ANAMNES_ROOT}/.venv"
fi

echo ""
echo "=== Services ==="
systemctl is-active anamnes-django >/dev/null 2>&1 && ok "anamnes-django active" || warn "anamnes-django not active"
if systemctl is-active anamnes >/dev/null 2>&1; then
  warn "Streamlit 'anamnes' still active — run deploy/switch-to-django-only.sh after cutover"
else
  ok "Streamlit 'anamnes' not running (Django-only)"
fi
curl -sf -o /dev/null -w "HTTP %{http_code}\n" -H "Host: ${DOMAIN}" "http://127.0.0.1:8000/" \
  && ok "Django responds on :8000 (Host: ${DOMAIN})" \
  || warn "No response on 127.0.0.1:8000 — check: curl -H 'Host: ${DOMAIN}' http://127.0.0.1:8000/"

echo ""
echo "=== TLS (${DOMAIN}) ==="
if echo | openssl s_client -connect "127.0.0.1:443" -servername "${DOMAIN}" 2>/dev/null | openssl x509 -noout -subject 2>/dev/null | grep -q "${DOMAIN}"; then
  ok "Certificate SAN matches ${DOMAIN}"
else
  warn "TLS mismatch — run: sudo bash ${ANAMNES_ROOT}/deploy/fix-ssl-cert.sh"
fi
if [[ -f "${NGINX_SITE}" ]]; then
  grep -E 'ssl_certificate|proxy_pass|server_name' "${NGINX_SITE}" | head -8 || true
else
  warn "Nginx site not found: ${NGINX_SITE}"
fi

echo ""
if [[ "${FAIL}" -eq 0 ]]; then
  echo "All checks passed."
else
  echo "Some checks failed — fix warnings above before going live."
  exit 1
fi

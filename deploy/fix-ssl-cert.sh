#!/usr/bin/env bash
# Fix NET::ERR_CERT_COMMON_NAME_INVALID for anamnes.ikorsakov.tech
# Run on VPS: sudo bash /opt/anamnes/deploy/fix-ssl-cert.sh

set -euo pipefail

DOMAIN="anamnes.ikorsakov.tech"
NGINX_SITE="/etc/nginx/sites-available/anamnes"
CERT_DIR="/etc/letsencrypt/live/${DOMAIN}"

echo "=== 1. Certificate on disk ==="
if [[ -f "${CERT_DIR}/fullchain.pem" ]]; then
  openssl x509 -in "${CERT_DIR}/fullchain.pem" -noout -subject -dates \
    -ext subjectAltName 2>/dev/null || openssl x509 -in "${CERT_DIR}/fullchain.pem" -noout -subject -dates
else
  echo "MISSING: ${CERT_DIR}/fullchain.pem — need certbot"
fi

echo ""
echo "=== 2. What nginx serves (SNI ${DOMAIN}) ==="
echo | openssl s_client -connect "127.0.0.1:443" -servername "${DOMAIN}" 2>/dev/null \
  | openssl x509 -noout -subject -ext subjectAltName 2>/dev/null \
  || echo "Cannot read cert from local :443 (nginx down or no SSL?)"

echo ""
echo "=== 3. nginx server_name + ssl_certificate lines ==="
grep -E 'server_name|ssl_certificate' "${NGINX_SITE}" 2>/dev/null || echo "Site file not found: ${NGINX_SITE}"

echo ""
echo "=== 4. Issue or renew Let's Encrypt cert ==="
if command -v certbot >/dev/null; then
  certbot certonly --nginx -d "${DOMAIN}" --non-interactive --agree-tos --register-unsafely-without-email \
    || certbot --nginx -d "${DOMAIN}"
else
  echo "Install: apt install certbot python3-certbot-nginx"
  exit 1
fi

echo ""
echo "=== 5. Ensure nginx uses this cert (uncomment if needed) ==="
if grep -q '^[[:space:]]*#.*ssl_certificate' "${NGINX_SITE}" 2>/dev/null; then
  sed -i "s|#[[:space:]]*ssl_certificate .*|ssl_certificate ${CERT_DIR}/fullchain.pem;|" "${NGINX_SITE}"
  sed -i "s|#[[:space:]]*ssl_certificate_key .*|ssl_certificate_key ${CERT_DIR}/privkey.pem;|" "${NGINX_SITE}"
  echo "Uncommented ssl_certificate paths in ${NGINX_SITE}"
fi

nginx -t
systemctl reload nginx

echo ""
echo "Done. Open https://${DOMAIN}/ in browser (incognito). Use exact host, not www."

#!/usr/bin/env bash
# HTTPS для SPVT через nip.io + секретный ключ выгрузки CSV для Power BI Service.
set -euo pipefail

PUBLIC_IP="${PUBLIC_IP:-45.144.220.51}"
NIP_HOST="${NIP_HOST:-45-144-220-51.nip.io}"
CERT_EMAIL="${CERT_EMAIL:-admin@${NIP_HOST}}"
CREDS_FILE="${CREDS_FILE:-/root/spvt-export-url.txt}"

if ! grep -q '^POWERBI_EXPORT_KEY=' /etc/spvt.env 2>/dev/null; then
  EXPORT_KEY="$(openssl rand -hex 24)"
  echo "POWERBI_EXPORT_KEY=${EXPORT_KEY}" >> /etc/spvt.env
else
  EXPORT_KEY="$(grep '^POWERBI_EXPORT_KEY=' /etc/spvt.env | cut -d= -f2-)"
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq certbot python3-certbot-nginx

cat > /etc/nginx/sites-available/spvt <<NGINX
server {
    listen 80;
    listen [::]:80;
    server_name ${NIP_HOST} ${PUBLIC_IP};

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
NGINX

ln -sf /etc/nginx/sites-available/spvt /etc/nginx/sites-enabled/spvt
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

certbot --nginx -d "${NIP_HOST}" --non-interactive --agree-tos -m "${CERT_EMAIL}" --redirect || {
  echo "certbot failed — проверьте, что ${NIP_HOST} указывает на ${PUBLIC_IP}"
  exit 1
}

systemctl restart spvt || true

HTTPS_URL="https://${NIP_HOST}/api/export/public/powerbi.csv?key=${EXPORT_KEY}"

cat > "${CREDS_FILE}" <<INFO
# Публичная выгрузка CSV для Power BI Service (без шлюза)
POWERBI_EXPORT_KEY=${EXPORT_KEY}
HTTPS_URL=${HTTPS_URL}
INFO
chmod 600 "${CREDS_FILE}"

echo "Готово."
echo "URL для Power BI:"
echo "${HTTPS_URL}"

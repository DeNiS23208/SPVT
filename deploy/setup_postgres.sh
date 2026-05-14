#!/usr/bin/env bash
set -euo pipefail

if ! id postgres &>/dev/null; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y -qq postgresql postgresql-contrib
fi

DB_NAME="${DB_NAME:-spvt}"
APP_USER="${APP_USER:-spvt_app}"
PBI_USER="${PBI_USER:-powerbi_read}"
CREDS_FILE="${CREDS_FILE:-/root/spvt-db-credentials.txt}"

if [[ -f "$CREDS_FILE" ]]; then
  echo "Учётные данные уже есть: $CREDS_FILE"
  exit 0
fi

APP_PASS="$(openssl rand -hex 16)"
PBI_PASS="$(openssl rand -hex 16)"

sudo -u postgres psql -v ON_ERROR_STOP=1 <<EOF
CREATE USER ${APP_USER} WITH PASSWORD '${APP_PASS}';
CREATE USER ${PBI_USER} WITH PASSWORD '${PBI_PASS}';
CREATE DATABASE ${DB_NAME} OWNER ${APP_USER};
GRANT CONNECT ON DATABASE ${DB_NAME} TO ${PBI_USER};
EOF

PG_CONF="$(sudo -u postgres psql -tAc "SHOW config_file")"
PG_HBA="$(sudo -u postgres psql -tAc "SHOW hba_file")"
PG_DIR="$(dirname "$PG_CONF")"

# Слушать localhost + внешние подключения (для Power BI)
if grep -q "^listen_addresses" "$PG_CONF"; then
  sed -i "s/^#*listen_addresses.*/listen_addresses = '*'/" "$PG_CONF"
else
  echo "listen_addresses = '*'" >> "$PG_CONF"
fi

# Доступ: приложение только локально, Power BI — по паролю извне
if ! grep -q "spvt_app local" "$PG_HBA"; then
  cat >> "$PG_HBA" <<HBA

# SPVT
local   ${DB_NAME}    ${APP_USER}                              scram-sha-256
host    ${DB_NAME}    ${APP_USER}    127.0.0.1/32              scram-sha-256
host    ${DB_NAME}    ${PBI_USER}    0.0.0.0/0                 scram-sha-256
HBA
fi

systemctl restart postgresql

cat > "$CREDS_FILE" <<CREDS
# SPVT PostgreSQL — храните в секрете
DB_NAME=${DB_NAME}
APP_USER=${APP_USER}
APP_PASS=${APP_PASS}
PBI_USER=${PBI_USER}
PBI_PASS=${PBI_PASS}
DATABASE_URL=postgresql+psycopg2://${APP_USER}:${APP_PASS}@127.0.0.1:5432/${DB_NAME}
POWERBI_DB_USER=${PBI_USER}

# Power BI Desktop — подключение:
# Сервер: IP_ВАШЕГО_VPS (порт 5432)
# База: ${DB_NAME}
# Пользователь: ${PBI_USER}
# Пароль: ${PBI_PASS}
# Таблица/представление: v_powerbi_export
CREDS
chmod 600 "$CREDS_FILE"

# Добавить в env приложения (не затирая SECRET_KEY)
touch /etc/spvt.env
grep -q '^DATABASE_URL=' /etc/spvt.env \
  || echo "DATABASE_URL=postgresql+psycopg2://${APP_USER}:${APP_PASS}@127.0.0.1:5432/${DB_NAME}" >> /etc/spvt.env
grep -q '^POWERBI_DB_USER=' /etc/spvt.env \
  || echo "POWERBI_DB_USER=${PBI_USER}" >> /etc/spvt.env

ufw allow 5432/tcp comment 'PostgreSQL for Power BI' || true

echo "Готово. Учётные данные: $CREDS_FILE"

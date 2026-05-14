#!/usr/bin/env bash
set -euo pipefail
CONF=/etc/postgresql/16/main/postgresql.conf
sed -i '/^ssl =/d' "$CONF"
echo 'ssl = off' >> "$CONF"
systemctl restart postgresql
grep '^ssl =' "$CONF"

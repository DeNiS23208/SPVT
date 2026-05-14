#!/usr/bin/env bash
set -euo pipefail
cd /opt/spvt
set -a
source /etc/spvt.env
set +a
export PYTHONPATH=/opt/spvt
.venv/bin/python -c "from app.pg_setup import setup_postgresql_extras; setup_postgresql_extras()"
sudo -u postgres psql -d spvt -c '\dv'

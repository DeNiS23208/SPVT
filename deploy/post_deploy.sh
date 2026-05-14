#!/usr/bin/env bash
set -euo pipefail
cd /opt/spvt
export PYTHONPATH=/opt/spvt

set -a
source /etc/spvt.env
set +a

.venv/bin/pip install -q -r requirements.txt
.venv/bin/python -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine)"
.venv/bin/python -c "from app.schema_migrate import ensure_user_profile_columns; ensure_user_profile_columns()"
.venv/bin/python scripts/migrate_sqlite_to_postgres.py /opt/spvt/spvt.db || true
.venv/bin/python -c "from app.seed import init_db; init_db()"
chown -R www-data:www-data /opt/spvt
systemctl restart spvt
sleep 2
systemctl is-active spvt
sleep 2
systemctl is-active spvt

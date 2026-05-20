#!/usr/bin/env bash
set -euo pipefail
cd /opt/spvt
export PYTHONPATH=/opt/spvt

set -a
source /etc/spvt.env
set +a

.venv/bin/pip install -q -r requirements.txt
.venv/bin/python -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine)"
.venv/bin/python -c "from app.schema_migrate import ensure_user_profile_columns, ensure_user_is_active_column; ensure_user_profile_columns(); ensure_user_is_active_column()"
.venv/bin/python scripts/migrate_sqlite_to_postgres.py /opt/spvt/spvt.db || true
.venv/bin/python -c "from app.seed import init_db; init_db()"
.venv/bin/python scripts/remove_test_users.py || true
if [ -f data/employees_ink.xlsx ]; then
  .venv/bin/python scripts/sync_employees_from_excel.py data/employees_ink.xlsx --no-create
fi
.venv/bin/python scripts/ensure_single_admin.py
chown -R www-data:www-data /opt/spvt
systemctl restart spvt
sleep 2
systemctl is-active spvt
sleep 2
systemctl is-active spvt

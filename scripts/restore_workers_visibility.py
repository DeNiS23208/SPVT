#!/usr/bin/env python3
"""Вернуть всех сотрудников после демо (по резервной копии hide_workers_for_demo.py)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_ENV_FILE = Path("/etc/spvt.env")


def _load_server_env() -> None:
    if os.environ.get("DATABASE_URL") or not _ENV_FILE.is_file():
        return
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_server_env()

from app.database import SessionLocal
from app.models import User, UserRole
from app.schema_migrate import ensure_user_is_active_column
from app.seed import init_db

BACKUP_PATH = ROOT / "data" / "demo_worker_visibility_backup.json"


def main() -> None:
    init_db()
    ensure_user_is_active_column()
    db = SessionLocal()
    try:
        restored = 0
        if BACKUP_PATH.is_file():
            payload = json.loads(BACKUP_PATH.read_text(encoding="utf-8"))
            for row in payload.get("users", []):
                user = db.get(User, row["id"])
                if user and user.role == UserRole.worker:
                    user.is_active = bool(row.get("is_active", True))
                    restored += 1
            print(f"Восстановлено по резервной копии: {restored}")
        else:
            for user in db.query(User).filter(User.role == UserRole.worker).all():
                user.is_active = True
                restored += 1
            print(f"Резервной копии нет — включены все работники: {restored}")

        db.commit()
        active = db.query(User).filter(User.role == UserRole.worker, User.is_active.is_(True)).count()
        print(f"Активных работников сейчас: {active}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

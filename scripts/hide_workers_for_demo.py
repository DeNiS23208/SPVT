#!/usr/bin/env python3
"""Скрыть сотрудников для демо/презентации (остаются Гуляев + Декин, Казанков, Сарнецкий К.П.)."""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
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

from app.admin_account import ensure_single_admin
from app.database import SessionLocal
from app.models import User, UserRole
from app.schema_migrate import ensure_user_is_active_column
from app.seed import init_db
from app.user_visibility import is_demo_visible_worker, should_keep_worker_visible

BACKUP_PATH = ROOT / "data" / "demo_worker_visibility_backup.json"


def main() -> None:
    init_db()
    ensure_user_is_active_column()
    db = SessionLocal()
    try:
        ensure_single_admin(db)
        db.flush()

        visible: list[User] = []
        hidden: list[dict] = []
        backup_rows: list[dict] = []

        for user in db.query(User).filter(User.role == UserRole.worker).order_by(User.full_name).all():
            if should_keep_worker_visible(user):
                user.is_active = True
                visible.append(user)
            else:
                if user.is_active:
                    backup_rows.append(
                        {
                            "id": user.id,
                            "username": user.username,
                            "full_name": user.full_name,
                            "department": user.department,
                            "is_active": True,
                        }
                    )
                user.is_active = False
                hidden.append(
                    {
                        "id": user.id,
                        "full_name": user.full_name,
                        "department": user.department,
                    }
                )

        BACKUP_PATH.parent.mkdir(parents=True, exist_ok=True)
        BACKUP_PATH.write_text(
            json.dumps(
                {
                    "hidden_at": datetime.now(timezone.utc).isoformat(),
                    "users": backup_rows,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        db.commit()

        print(f"Видимых работников: {len(visible)}")
        for user in visible:
            dept = user.department or "—"
            print(f"  • {user.full_name} ({dept})")
        print(f"Скрыто: {len(hidden)}")
        print(f"Резервная копия: {BACKUP_PATH}")
        print("Восстановление: .venv/bin/python scripts/restore_workers_visibility.py")
        db_url = os.environ.get("DATABASE_URL", "sqlite:///./spvt.db")
        print(f"База: {db_url.split('@')[-1] if '@' in db_url else db_url}")
        if len(hidden) < 10 and "postgresql" not in db_url:
            print("ВНИМАНИЕ: похоже, скрипт подключился не к production PostgreSQL.")

        kazankov = [u for u in visible if is_demo_visible_worker(u) and "казанков" in (u.full_name or "").lower()]
        if not kazankov:
            print("ВНИМАНИЕ: Казанков не найден в базе — проверьте ФИО в Excel.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

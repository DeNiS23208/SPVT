#!/usr/bin/env python3
"""Оставить одного администратора (Гуляев Д.М.), убрать админ/начальник."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.admin_account import ADMIN_FULL_NAME, ADMIN_USERNAME, ensure_single_admin
from app.database import SessionLocal
from app.models import User, UserRole
from app.seed import init_db


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        admin = ensure_single_admin(db)
        db.commit()
        print(f"Администратор: {admin.full_name} (логин: {admin.username}, пароль: 123)")
        others = (
            db.query(User)
            .filter(User.role.in_((UserRole.admin, UserRole.manager)), User.id != admin.id)
            .count()
        )
        print(f"Других admin/manager: {others}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

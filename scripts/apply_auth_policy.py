#!/usr/bin/env python3
"""Пароль 123 для всех; логины работников — кириллица (фамилия_инициалы)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.auth import hash_password
from app.database import SessionLocal
from app.models import User, UserRole
from app.seed import USERS, ensure_users, init_db
from app.usernames import DEFAULT_PASSWORD, username_from_name


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        ensure_users(db)
        db.commit()

        password_hash = hash_password(DEFAULT_PASSWORD)
        used = {u.username for u in db.query(User).all()}

        for user in db.query(User).filter(User.role == UserRole.worker).order_by(User.id):
            if user.username in used:
                used.discard(user.username)
            user.username = username_from_name(user.full_name, user.id, used)
            user.password_hash = password_hash

        for user in db.query(User).filter(User.role != UserRole.worker).all():
            user.password_hash = password_hash

        for item in USERS:
            row = db.query(User).filter(User.username == item["username"]).first()
            if row:
                row.password_hash = password_hash

        db.commit()
        total = db.query(User).count()
        print(f"Готово: {total} пользователей, пароль «{DEFAULT_PASSWORD}», работники — логины кириллицей.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

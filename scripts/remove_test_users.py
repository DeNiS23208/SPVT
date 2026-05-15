#!/usr/bin/env python3
"""Удалить тестовых работников из БД (оставить админ/начальник и реальный импорт)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.models import Answer, TestAttempt, User, UserRole

TEST_USERNAMES = frozenset(
    {
        "worker",
        "worker2",
        "worker3",
        "иванов_ии",
        "петров_пп",
        "сидоров_сс",
    }
)

TEST_NAME_MARKERS = ("(тест)",)


def main() -> None:
    db = SessionLocal()
    try:
        workers = db.query(User).filter(User.role == UserRole.worker).all()
        to_delete: list[User] = []
        for user in workers:
            if user.username in TEST_USERNAMES:
                to_delete.append(user)
                continue
            if any(marker in (user.full_name or "") for marker in TEST_NAME_MARKERS):
                to_delete.append(user)

        if not to_delete:
            print("Тестовые работники не найдены.")
            return

        ids = [u.id for u in to_delete]
        attempts = db.query(TestAttempt).filter(TestAttempt.user_id.in_(ids)).all()
        attempt_ids = [a.id for a in attempts]
        if attempt_ids:
            db.query(Answer).filter(Answer.attempt_id.in_(attempt_ids)).delete(
                synchronize_session=False
            )
            db.query(TestAttempt).filter(TestAttempt.id.in_(attempt_ids)).delete(
                synchronize_session=False
            )

        for user in to_delete:
            db.delete(user)
            print(f"Удалён: {user.username} — {user.full_name}")

        db.commit()
        print(f"Всего удалено: {len(to_delete)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

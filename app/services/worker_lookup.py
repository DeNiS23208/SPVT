"""Поиск сотрудников по ФИО для упрощённого входа."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import User, UserRole
from app.name_utils import fio_core_key, normalize_name_key


def name_matches_query(full_name: str, query: str) -> bool:
    """Все значимые слова запроса должны встречаться в ФИО (фамилия, имя, отчество)."""
    query_key = normalize_name_key(query)
    if len(query_key.replace(" ", "")) < 2:
        return False

    name_key = fio_core_key(full_name)
    name_words = name_key.split()
    parts = [p for p in query_key.split() if len(p) >= 2]
    if not parts:
        return False

    for part in parts:
        if part in name_key:
            continue
        if any(w.startswith(part) for w in name_words):
            continue
        return False
    return True


def find_workers_by_name(db: Session, query: str, *, limit: int = 40) -> list[User]:
    q = query.strip()
    if len(q.replace(" ", "")) < 2:
        return []

    workers = (
        db.query(User)
        .filter(
            User.role.in_((UserRole.worker, UserRole.admin)),
            User.is_active.is_(True),
            User.department.isnot(None),
            User.department != "",
        )
        .order_by(User.full_name)
        .all()
    )
    matched = [w for w in workers if name_matches_query(w.full_name, q)]
    return matched[:limit]

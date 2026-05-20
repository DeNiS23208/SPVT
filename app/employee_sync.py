"""Синхронизация сотрудников с Excel (подразделение, должность, ФИО)."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.auth import hash_password
from app.employee_import import EmployeeRow, read_employees_xlsx
from app.models import User, UserRole
from app.name_utils import fio_core_key, normalize_name_key
from app.usernames import DEFAULT_PASSWORD, username_from_name


def build_excel_indexes(rows: list[EmployeeRow]) -> tuple[dict[str, EmployeeRow], dict[str, list[EmployeeRow]]]:
    by_exact: dict[str, EmployeeRow] = {}
    by_core: dict[str, list[EmployeeRow]] = {}
    for row in rows:
        exact = normalize_name_key(row.full_name)
        by_exact[exact] = row
        core = fio_core_key(row.full_name)
        by_core.setdefault(core, []).append(row)
    return by_exact, by_core


def find_excel_row(
    user: User,
    by_exact: dict[str, EmployeeRow],
    by_core: dict[str, list[EmployeeRow]],
) -> EmployeeRow | None:
    exact = normalize_name_key(user.full_name or "")
    if exact in by_exact:
        return by_exact[exact]

    core = fio_core_key(user.full_name or "")
    candidates = by_core.get(core, [])
    if len(candidates) == 1:
        return candidates[0]
    return None


@dataclass
class SyncStats:
    updated: int = 0
    created: int = 0
    unchanged: int = 0
    not_in_excel: int = 0
    ambiguous: int = 0


def sync_employees_from_excel(
    db: Session,
    path: str,
    *,
    create_missing: bool = True,
) -> SyncStats:
    rows = read_employees_xlsx(path)
    by_exact, by_core = build_excel_indexes(rows)
    stats = SyncStats()
    password_hash = hash_password(DEFAULT_PASSWORD)

    workers = db.query(User).filter(User.role == UserRole.worker).all()
    matched_excel_keys: set[str] = set()

    for user in workers:
        core = fio_core_key(user.full_name or "")
        candidates = by_core.get(core, [])
        if len(candidates) > 1 and normalize_name_key(user.full_name or "") not in by_exact:
            stats.ambiguous += 1
            continue

        row = find_excel_row(user, by_exact, by_core)
        if not row:
            stats.not_in_excel += 1
            continue

        matched_excel_keys.add(normalize_name_key(row.full_name))

        changed = False
        if user.full_name != row.full_name:
            user.full_name = row.full_name
            changed = True
        if (user.department or "") != row.department:
            user.department = row.department or None
            changed = True
        if (user.position or "") != row.position:
            user.position = row.position or None
            changed = True

        if changed:
            stats.updated += 1
        else:
            stats.unchanged += 1

    if create_missing:
        used_usernames = {u.username for u in db.query(User).all()}
        for row in rows:
            key = normalize_name_key(row.full_name)
            if key in matched_excel_keys:
                continue
            if db.query(User).filter(User.full_name == row.full_name, User.role == UserRole.worker).first():
                continue
            username = username_from_name(row.full_name, stats.created + 1, used_usernames)
            db.add(
                User(
                    username=username,
                    password_hash=password_hash,
                    role=UserRole.worker,
                    full_name=row.full_name,
                    position=row.position or None,
                    department=row.department or None,
                    is_active=True,
                )
            )
            stats.created += 1

    db.commit()
    return stats

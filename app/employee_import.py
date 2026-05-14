from __future__ import annotations

import os
import re
from dataclasses import dataclass

from openpyxl import load_workbook
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import User, UserRole

_CYRILLIC = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


def translit(text: str) -> str:
    result: list[str] = []
    for char in text.strip().lower():
        if char in _CYRILLIC:
            result.append(_CYRILLIC[char])
        elif char.isalnum():
            result.append(char)
    return "".join(result)


def username_from_name(full_name: str, row_num: int, used: set[str]) -> str:
    parts = [part for part in full_name.split() if part]
    if len(parts) >= 3:
        base = f"{translit(parts[0])}_{translit(parts[1][0])}{translit(parts[2][0])}"
    elif len(parts) == 2:
        base = f"{translit(parts[0])}_{translit(parts[1][0])}"
    else:
        base = f"emp_{row_num:04d}"

    base = re.sub(r"[^a-z0-9_]", "", base.lower())[:48] or f"emp_{row_num:04d}"
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}_{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


@dataclass
class EmployeeRow:
    full_name: str
    position: str
    department: str


def read_employees_xlsx(path: str) -> list[EmployeeRow]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    worksheet = workbook[workbook.sheetnames[0]]
    rows = list(worksheet.iter_rows(values_only=True))
    if not rows:
        return []

    header = [str(cell or "").strip().lower() for cell in rows[0]]
    name_idx = next((i for i, value in enumerate(header) if "сотрудник" in value or value == "фио"), 0)
    position_idx = next((i for i, value in enumerate(header) if "должност" in value), 1)
    department_idx = next((i for i, value in enumerate(header) if "подраздел" in value), 2)

    employees: list[EmployeeRow] = []
    for row in rows[1:]:
        if not row or not row[name_idx]:
            continue
        employees.append(
            EmployeeRow(
                full_name=str(row[name_idx]).strip(),
                position=str(row[position_idx] or "").strip(),
                department=str(row[department_idx] or "").strip(),
            )
        )
    return employees


@dataclass
class ImportStats:
    created: int = 0
    updated: int = 0
    skipped: int = 0


def import_employees_from_xlsx(
    db: Session,
    path: str,
    *,
    default_password: str | None = None,
    update_existing: bool = True,
) -> ImportStats:
    password = default_password or os.environ.get("DEFAULT_WORKER_PASSWORD", "INK2026")
    employees = read_employees_xlsx(path)
    stats = ImportStats()

    existing_by_name = {
        user.full_name.strip().lower(): user
        for user in db.query(User).filter(User.role == UserRole.worker).all()
    }
    used_usernames = {user.username for user in db.query(User).all()}

    for index, employee in enumerate(employees, start=1):
        key = employee.full_name.lower()
        existing = existing_by_name.get(key)
        if existing:
            if update_existing:
                changed = False
                if employee.position and existing.position != employee.position:
                    existing.position = employee.position
                    changed = True
                if employee.department and existing.department != employee.department:
                    existing.department = employee.department
                    changed = True
                if changed:
                    stats.updated += 1
                else:
                    stats.skipped += 1
            else:
                stats.skipped += 1
            continue

        username = username_from_name(employee.full_name, index, used_usernames)
        db.add(
            User(
                username=username,
                password_hash=hash_password(password),
                role=UserRole.worker,
                full_name=employee.full_name,
                position=employee.position or None,
                department=employee.department or None,
            )
        )
        stats.created += 1
        if stats.created % 250 == 0:
            db.flush()
            print(f"  импортировано {stats.created}...", flush=True)

    db.commit()
    return stats

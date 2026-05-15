#!/usr/bin/env python3
"""Строгий аудит: только точное совпадение ФИО из Excel."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.employee_import import read_employees_xlsx
from app.models import User, UserRole
from app.name_utils import normalize_name_key
from app.seed import init_db


def main() -> None:
    xlsx = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "employees_ink.xlsx"
    rows = read_employees_xlsx(str(xlsx))
    by_exact = {normalize_name_key(r.full_name): r for r in rows}

    init_db()
    db = SessionLocal()
    dept_mismatch = []
    no_exact = []
    try:
        for user in db.query(User).filter(User.role == UserRole.worker).all():
            key = normalize_name_key(user.full_name or "")
            row = by_exact.get(key)
            if not row:
                no_exact.append(user.full_name)
                continue
            if normalize_name_key(user.department or "") != normalize_name_key(row.department):
                dept_mismatch.append((user.full_name, user.department, row.department))
    finally:
        db.close()

    print(f"Excel: {len(rows)}")
    print(f"Exact dept mismatch: {len(dept_mismatch)}")
    print(f"No exact name in Excel: {len(no_exact)}")
    for item in dept_mismatch[:25]:
        print(f"  {item[0]}")
        print(f"    DB:    {item[1]}")
        print(f"    Excel: {item[2]}")


if __name__ == "__main__":
    main()

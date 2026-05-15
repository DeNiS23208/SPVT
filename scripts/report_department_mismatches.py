#!/usr/bin/env python3
"""Отчёт: расхождения подразделений БД vs Excel."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.seed import init_db
from app.employee_import import read_employees_xlsx
from app.employee_sync import build_excel_indexes, find_excel_row
from app.name_utils import normalize_name_key
from app.models import User, UserRole


def main() -> None:
    xlsx = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "employees_ink.xlsx"
    if not xlsx.is_file():
        print(f"File not found: {xlsx}", file=sys.stderr)
        sys.exit(1)

    rows = read_employees_xlsx(str(xlsx))
    by_exact, by_core = build_excel_indexes(rows)

    init_db()
    db = SessionLocal()
    mismatches: list[tuple[str, str, str]] = []
    no_match = 0
    try:
        for user in db.query(User).filter(User.role == UserRole.worker).all():
            row = find_excel_row(user, by_exact, by_core)
            if not row:
                no_match += 1
                continue
            if normalize_name_key(user.department or "") != normalize_name_key(row.department):
                mismatches.append((user.full_name, user.department or "", row.department))
    finally:
        db.close()

    print(f"Excel rows: {len(rows)}")
    print(f"Department mismatches: {len(mismatches)}")
    print(f"No Excel match: {no_match}")
    for name, db_dept, xl_dept in mismatches[:30]:
        print(f"  {name}")
        print(f"    DB:    {db_dept}")
        print(f"    Excel: {xl_dept}")
    if len(mismatches) > 30:
        print(f"  ... and {len(mismatches) - 30} more")


if __name__ == "__main__":
    main()

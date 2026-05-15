#!/usr/bin/env python3
"""Пересинхронизация подразделений и должностей из Excel."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.seed import init_db
from app.employee_sync import sync_employees_from_excel


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync workers from Excel (department, position, name)")
    parser.add_argument("xlsx", type=Path, help="Path to Работники ИНКС.xlsx")
    parser.add_argument("--no-create", action="store_true", help="Do not create missing workers")
    args = parser.parse_args()

    if not args.xlsx.is_file():
        print(f"File not found: {args.xlsx}", file=sys.stderr)
        sys.exit(1)

    init_db()
    db = SessionLocal()
    try:
        stats = sync_employees_from_excel(
            db,
            str(args.xlsx),
            create_missing=not args.no_create,
        )
    finally:
        db.close()

    print(f"Updated:      {stats.updated}")
    print(f"Unchanged:    {stats.unchanged}")
    print(f"Not in Excel: {stats.not_in_excel}")
    print(f"Ambiguous:    {stats.ambiguous}")
    print(f"Created:      {stats.created}")


if __name__ == "__main__":
    main()

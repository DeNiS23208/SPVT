#!/usr/bin/env python3
from collections import Counter

from app.database import SessionLocal
from app.employee_import import read_employees_xlsx
from app.models import User, UserRole
from app.seed import init_db


def main() -> None:
    init_db()
    rows = read_employees_xlsx("data/employees_ink.xlsx")
    xl = Counter(r.department for r in rows)

    db = SessionLocal()
    db_counts = Counter()
    for user in db.query(User).filter(User.role == UserRole.worker).all():
        db_counts[user.department or ""] += 1
    db.close()

    bad = []
    for dept in sorted(set(xl) | set(db_counts)):
        if not dept:
            continue
        if xl.get(dept, 0) != db_counts.get(dept, 0):
            bad.append((dept, db_counts.get(dept, 0), xl.get(dept, 0)))
    print(f"Excel departments: {len(xl)}")
    print(f"Count mismatches: {len(bad)}")
    for dept, cdb, cx in bad[:20]:
        print(f"  {cdb} vs {cx}  {dept}")


if __name__ == "__main__":
    main()

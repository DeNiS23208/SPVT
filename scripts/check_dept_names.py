#!/usr/bin/env python3
"""Похожие названия подразделений (опечатки, лишние пробелы)."""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.models import User, UserRole
from app.name_utils import normalize_name_key
from app.seed import init_db


def main() -> None:
    init_db()
    db = SessionLocal()
    counts: dict[str, int] = defaultdict(int)
    try:
        for user in db.query(User).filter(User.role == UserRole.worker).all():
            counts[user.department or ""] += 1
    finally:
        db.close()

    keys = sorted(k for k in counts if k)
    print(f"Подразделений: {len(keys)}, сотрудников: {sum(counts.values())}")
    pairs = []
    for i, a in enumerate(keys):
        na = normalize_name_key(a)
        for b in keys[i + 1 :]:
            nb = normalize_name_key(b)
            if na == nb and a != b:
                pairs.append((a, b, counts[a], counts[b]))
            elif na and nb and len(na) > 8 and (na in nb or nb in na) and na != nb:
                pairs.append((a, b, counts[a], counts[b]))
    print(f"Похожие пары: {len(pairs)}")
    for a, b, ca, cb in pairs[:20]:
        print(f"  [{ca}] {a}")
        print(f"  [{cb}] {b}")


if __name__ == "__main__":
    main()

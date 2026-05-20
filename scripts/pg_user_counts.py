#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text
from app.database import engine, is_postgresql

print("postgresql", is_postgresql())
with engine.connect() as conn:
    total = conn.execute(text("SELECT count(*) FROM users")).scalar()
    print("total", total)
    rows = conn.execute(text("SELECT role::text, count(*) FROM users GROUP BY role ORDER BY 1")).all()
    for r in rows:
        print(r[0], r[1])
    sample = conn.execute(
        text(
            "SELECT full_name, role::text, is_active, department FROM users "
            "WHERE full_name ILIKE '%декин%' OR full_name ILIKE '%казанков%' "
            "OR full_name ILIKE '%сарнецкий%' OR full_name ILIKE '%гуляев%' LIMIT 20"
        )
    ).all()
    print("sample", len(sample))
    for row in sample:
        print(" ", row)

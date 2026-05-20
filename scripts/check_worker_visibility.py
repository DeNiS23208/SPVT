#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.models import User, UserRole
from app.user_visibility import is_demo_visible_worker

db = SessionLocal()
total = db.query(User).count()
print(f"total_users={total}")
for role in UserRole:
    print(f"  role {role.value}: {db.query(User).filter(User.role == role).count()}")
workers = db.query(User).filter(User.role == UserRole.worker).count()
active = db.query(User).filter(User.role == UserRole.worker, User.is_active.is_(True)).count()
print(f"workers={workers} active={active} inactive={workers - active}")
for u in db.query(User).filter(User.role == UserRole.worker, User.is_active.is_(True)).order_by(User.full_name).all():
    print(f"  ACTIVE: {u.full_name} | {u.department}")
for needle in ("декин", "казанков", "сарнецкий"):
    hits = db.query(User).filter(User.full_name.ilike(f"%{needle}%")).limit(10).all()
    print(f"--- {needle}: {len(hits)}")
    for u in hits:
        print(f"  {u.full_name} | active={u.is_active} | demo={is_demo_visible_worker(u)}")
db.close()

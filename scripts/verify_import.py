#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.models import User, UserRole

db = SessionLocal()
workers = db.query(User).filter(User.role == UserRole.worker).count()
managers = db.query(User).filter(User.role == UserRole.manager).count()
sample = (
    db.query(User)
    .filter(User.role == UserRole.worker, User.department.like("Буровая бригада 1%"))
    .order_by(User.id)
    .first()
)
print("workers", workers)
print("managers", managers)
if sample:
    print("sample", sample.username, sample.full_name, sample.position, sample.department)
db.close()

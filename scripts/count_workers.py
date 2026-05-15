#!/usr/bin/env python3
from app.database import SessionLocal, engine
from app.models import User, UserRole

print("DB:", engine.url)
db = SessionLocal()
print("workers:", db.query(User).filter(User.role == UserRole.worker).count())
db.close()

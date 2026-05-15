#!/usr/bin/env python3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.services.site_settings import get_all_settings

db = SessionLocal()
print(get_all_settings(db).get("logo_url"))
db.close()

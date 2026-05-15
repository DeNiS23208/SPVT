#!/usr/bin/env python3
"""Фон главной без вшитого логотипа (только буровая)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.seed import init_db
from app.services.site_settings import get_all_settings, set_settings

# Без «ИНК» в сердце — иначе дублируется с ink-logo-inkservice.png
HERO_URL = "/static/images/hero-bg.png"


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        set_settings(db, {"hero_background_url": HERO_URL})
        print("hero_background_url:", get_all_settings(db)["hero_background_url"])
    finally:
        db.close()


if __name__ == "__main__":
    main()

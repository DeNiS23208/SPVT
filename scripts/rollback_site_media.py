#!/usr/bin/env python3
"""Откат медиа главной: оригинальный логотип и фон с животными."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.seed import init_db
from app.services.site_settings import get_all_settings, set_settings

LOGO_URL = "/static/images/ink-logo.png"
HERO_URL = "/static/images/hero-bg-d7b69497f2-opt.webp"


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        set_settings(db, {"logo_url": LOGO_URL, "hero_background_url": HERO_URL})
        s = get_all_settings(db)
        print("logo_url:", s["logo_url"])
        print("hero_background_url:", s["hero_background_url"])
    finally:
        db.close()


if __name__ == "__main__":
    main()

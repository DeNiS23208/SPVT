#!/usr/bin/env python3
"""Обновить logo_url в настройках сайта (сброс кэша браузера)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.seed import init_db
from app.services.site_settings import get_all_settings, set_settings

NEW_LOGO = "/static/images/ink-logo-inkservice.png"


def main() -> None:
    init_db()
    db = SessionLocal()
    try:
        set_settings(db, {"logo_url": NEW_LOGO})
        print("logo_url:", get_all_settings(db)["logo_url"])
    finally:
        db.close()


if __name__ == "__main__":
    main()

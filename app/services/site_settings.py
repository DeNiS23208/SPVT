from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import SiteSetting

DEFAULTS: dict[str, str] = {
    "site_title": "Система предвахтового тестирования",
    "site_subtitle": "Проверка готовности работников к выходу на смену",
    "hero_background_url": "/static/images/hero-bg.png",
    "logo_url": "/static/images/ink-logo.png",
    "hero_overlay_opacity": "0.75",
    "accent_color": "#38bdf8",
    "pass_threshold": "80",
    "question_time_limit_seconds": "",
}


def get_setting(db: Session, key: str) -> str:
    row = db.query(SiteSetting).filter(SiteSetting.key == key).first()
    if row and row.value != "":
        return row.value
    return DEFAULTS.get(key, "")


def get_all_settings(db: Session) -> dict[str, str]:
    stored = {row.key: row.value for row in db.query(SiteSetting).all()}
    result = dict(DEFAULTS)
    result.update({key: value for key, value in stored.items() if value != ""})
    return result


def set_settings(db: Session, values: dict[str, str]) -> dict[str, str]:
    allowed = set(DEFAULTS)
    for key, value in values.items():
        if key not in allowed:
            continue
        row = db.query(SiteSetting).filter(SiteSetting.key == key).first()
        if row:
            row.value = value
        else:
            db.add(SiteSetting(key=key, value=value))
    db.commit()
    return get_all_settings(db)


def get_pass_threshold(db: Session) -> float:
    raw = get_setting(db, "pass_threshold")
    try:
        return float(raw)
    except ValueError:
        return 80.0


def get_question_time_limit_seconds(db: Session) -> int | None:
    """Лимит секунд на один вопрос для всех тестов; пусто — без лимита."""
    raw = get_setting(db, "question_time_limit_seconds").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value > 0 else None


def set_question_time_limit_seconds(db: Session, seconds: int | None) -> None:
    value = str(seconds) if seconds is not None and seconds > 0 else ""
    row = db.query(SiteSetting).filter(SiteSetting.key == "question_time_limit_seconds").first()
    if row:
        row.value = value
    else:
        db.add(SiteSetting(key="question_time_limit_seconds", value=value))
    db.commit()

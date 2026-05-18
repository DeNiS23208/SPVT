"""Справочник типов тестов и статус для работника."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models import Answer, AttemptStatus, Question, TestAttempt, TestTicket, TestType, User
from app.seed import today_shift_date

_CYR_LAT = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


def slug_from_title(title: str) -> str:
    text = title.strip().lower().replace("ё", "е")
    parts: list[str] = []
    for char in text:
        if char in _CYR_LAT:
            parts.append(_CYR_LAT[char])
        elif char.isascii() and char.isalnum():
            parts.append(char)
        else:
            parts.append("-")
    slug = "".join(parts)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:48] or f"test-{uuid4().hex[:8]}"


def delete_test_type(db: Session, test_type: TestType) -> None:
    """Удалить тест вместе с вопросами, попытками и ответами."""
    attempt_ids = [
        row[0]
        for row in db.query(TestAttempt.id).filter(TestAttempt.test_type_id == test_type.id).all()
    ]
    if attempt_ids:
        db.query(Answer).filter(Answer.attempt_id.in_(attempt_ids)).delete(
            synchronize_session=False
        )
    db.query(TestAttempt).filter(TestAttempt.test_type_id == test_type.id).delete(
        synchronize_session=False
    )
    db.query(Question).filter(Question.test_type_id == test_type.id).delete(synchronize_session=False)
    db.query(TestTicket).filter(TestTicket.test_type_id == test_type.id).delete(synchronize_session=False)
    db.delete(test_type)
    db.commit()


def unique_slug(db: Session, title: str) -> str:
    base = slug_from_title(title)
    candidate = base
    suffix = 2
    while db.query(TestType.id).filter(TestType.slug == candidate).first():
        candidate = f"{base}-{suffix}"
        suffix += 1
    return candidate


def get_test_type_by_slug(db: Session, slug: str, *, active_only: bool = True) -> TestType | None:
    q = db.query(TestType).filter(TestType.slug == slug.strip().lower())
    if active_only:
        q = q.filter(TestType.is_active.is_(True))
    return q.first()


def list_all_test_types(db: Session) -> list[TestType]:
    return db.query(TestType).order_by(TestType.sort_order, TestType.id).all()


def list_active_test_types(db: Session) -> list[TestType]:
    return (
        db.query(TestType)
        .filter(TestType.is_active.is_(True))
        .order_by(TestType.sort_order, TestType.id)
        .all()
    )


def latest_attempt_for_user(
    db: Session,
    user_id: int,
    test_type_id: int,
    *,
    shift_date: str | None = None,
) -> TestAttempt | None:
    q = db.query(TestAttempt).filter(
        TestAttempt.user_id == user_id,
        TestAttempt.test_type_id == test_type_id,
    )
    if shift_date is not None:
        q = q.filter(TestAttempt.shift_date == shift_date)
    return q.order_by(TestAttempt.id.desc()).first()


def pass_retake_available_at(
    db: Session, user_id: int, test_type_id: int, retake_after_days: int | None
) -> datetime | None:
    """Когда можно снова сдать тест после последней успешной сдачи."""
    if not retake_after_days or retake_after_days < 1:
        return None
    last_pass = (
        db.query(TestAttempt)
        .filter(
            TestAttempt.user_id == user_id,
            TestAttempt.test_type_id == test_type_id,
            TestAttempt.status == AttemptStatus.ready,
            TestAttempt.passed.is_(True),
            TestAttempt.finished_at.isnot(None),
        )
        .order_by(TestAttempt.finished_at.desc())
        .first()
    )
    if not last_pass or not last_pass.finished_at:
        return None
    finished = last_pass.finished_at
    if finished.tzinfo is None:
        finished = finished.replace(tzinfo=timezone.utc)
    else:
        finished = finished.astimezone(timezone.utc)
    return finished + timedelta(days=int(retake_after_days))


def last_finished_attempt(db: Session, user_id: int, test_type_id: int) -> TestAttempt | None:
    return (
        db.query(TestAttempt)
        .filter(
            TestAttempt.user_id == user_id,
            TestAttempt.test_type_id == test_type_id,
            TestAttempt.status.in_((AttemptStatus.ready, AttemptStatus.not_ready)),
            TestAttempt.finished_at.isnot(None),
        )
        .options(joinedload(TestAttempt.answers))
        .order_by(TestAttempt.finished_at.desc())
        .first()
    )


def catalog_item_for_user(db: Session, user: User, test_type: TestType) -> dict:
    shift_date = today_shift_date()
    today_attempt = latest_attempt_for_user(db, user.id, test_type.id, shift_date=shift_date)
    last_finished = last_finished_attempt(db, user.id, test_type.id)

    has_attempt_today = bool(
        today_attempt
        and today_attempt.status not in (AttemptStatus.in_progress, AttemptStatus.reset)
    )
    can_start = not has_attempt_today
    next_retake_at = pass_retake_available_at(
        db, user.id, test_type.id, test_type.retake_after_days
    )
    if can_start and next_retake_at is not None:
        now = datetime.now(timezone.utc)
        if now < next_retake_at:
            can_start = False

    passed_today: bool | None = None
    status_today: AttemptStatus | None = None
    score_today: float | None = None
    if today_attempt and today_attempt.status not in (
        AttemptStatus.in_progress,
        AttemptStatus.reset,
    ):
        passed_today = today_attempt.passed
        status_today = today_attempt.status
        score_today = today_attempt.score_percent

    last_passed: bool | None = None
    last_status: AttemptStatus | None = None
    last_score: float | None = None
    last_finished_at = None
    last_correct_count: int | None = None
    last_total_questions: int | None = None
    if last_finished:
        last_passed = last_finished.passed
        last_status = last_finished.status
        last_score = last_finished.score_percent
        last_finished_at = last_finished.finished_at
        if last_finished_at is not None and last_finished_at.tzinfo is None:
            last_finished_at = last_finished_at.replace(tzinfo=timezone.utc)
        if last_finished.answers:
            last_total_questions = len(last_finished.answers)
            last_correct_count = sum(1 for a in last_finished.answers if a.is_correct)

    return {
        "slug": test_type.slug,
        "title": test_type.title,
        "description": test_type.description or "",
        "shift_date": shift_date,
        "can_start": can_start,
        "has_attempt_today": has_attempt_today,
        "passed_today": passed_today,
        "status_today": status_today,
        "score_percent_today": score_today,
        "last_passed": last_passed,
        "last_status": last_status,
        "last_score_percent": last_score,
        "last_finished_at": last_finished_at,
        "last_correct_count": last_correct_count,
        "last_total_questions": last_total_questions,
        "retake_after_days": test_type.retake_after_days,
        "next_retake_at": next_retake_at,
    }

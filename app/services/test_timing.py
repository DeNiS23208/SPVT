from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Answer, Question, TestAttempt, TestType


def test_timer_payload(test_type: TestType) -> dict:
    """Лимиты времени для одного теста. Приоритет: на вопрос, затем на билет."""
    q_sec = test_type.question_time_limit_seconds
    t_min = test_type.ticket_time_limit_minutes
    if q_sec is not None and q_sec > 0:
        return {
            "timer_mode": "question",
            "question_time_limit_seconds": int(q_sec),
            "ticket_time_limit_minutes": t_min,
        }
    if t_min is not None and t_min > 0:
        return {
            "timer_mode": "ticket",
            "question_time_limit_seconds": None,
            "ticket_time_limit_minutes": int(t_min),
        }
    return {
        "timer_mode": None,
        "question_time_limit_seconds": None,
        "ticket_time_limit_minutes": None,
    }


def _question_count_for_attempt(db: Session, attempt: TestAttempt) -> int:
    if attempt.ticket_id:
        count = (
            db.query(func.count(Question.id))
            .filter(Question.ticket_id == attempt.ticket_id, Question.is_active.is_(True))
            .scalar()
        )
        if count:
            return int(count)
    answer_count = (
        db.query(func.count(Answer.id)).filter(Answer.attempt_id == attempt.id).scalar() or 0
    )
    return int(answer_count) if answer_count else 0


def allotted_seconds_for_attempt(db: Session, attempt: TestAttempt) -> tuple[int | None, str | None]:
    """Секунды лимита и режим: question | ticket."""
    tt = attempt.test_type
    if not tt:
        return None, None
    q_sec = tt.question_time_limit_seconds
    t_min = tt.ticket_time_limit_minutes
    if q_sec is not None and q_sec > 0:
        n = _question_count_for_attempt(db, attempt)
        return int(q_sec) * max(n, 1), "question"
    if t_min is not None and t_min > 0:
        return int(t_min) * 60, "ticket"
    return None, None


def elapsed_seconds_for_attempt(attempt: TestAttempt) -> int | None:
    if not attempt.started_at:
        return None
    start = attempt.started_at
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    end = attempt.finished_at or datetime.now(timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return max(0, int((end - start).total_seconds()))


def attempt_time_stats(db: Session, attempt: TestAttempt) -> dict:
    allotted, kind = allotted_seconds_for_attempt(db, attempt)
    return {
        "elapsed_seconds": elapsed_seconds_for_attempt(attempt),
        "allotted_seconds": allotted,
        "time_limit_kind": kind,
    }

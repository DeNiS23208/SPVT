"""Билет на попытку теста."""
from __future__ import annotations

import re
import secrets

from sqlalchemy.orm import Session

from app.models import Answer, Question, TestAttempt, TestTicket


def tickets_with_active_questions(db: Session, test_type_id: int) -> list[TestTicket]:
    tickets = (
        db.query(TestTicket)
        .filter(TestTicket.test_type_id == test_type_id)
        .order_by(TestTicket.sort_order, TestTicket.id)
        .all()
    )
    with_questions: list[TestTicket] = []
    for ticket in tickets:
        count = (
            db.query(Question.id)
            .filter(
                Question.ticket_id == ticket.id,
                Question.test_type_id == test_type_id,
                Question.is_active.is_(True),
            )
            .count()
        )
        if count:
            with_questions.append(ticket)
    return with_questions


def pick_random_ticket(
    db: Session,
    test_type_id: int,
    *,
    exclude_ticket_ids: set[int] | None = None,
) -> TestTicket | None:
    with_questions = tickets_with_active_questions(db, test_type_id)
    if not with_questions:
        return (
            db.query(TestTicket)
            .filter(TestTicket.test_type_id == test_type_id)
            .order_by(TestTicket.sort_order, TestTicket.id)
            .first()
        )
    pool = with_questions
    if exclude_ticket_ids:
        filtered = [t for t in pool if t.id not in exclude_ticket_ids]
        if filtered:
            pool = filtered
    return secrets.choice(pool)


def ticket_number_label(ticket: TestTicket | None) -> str:
    if not ticket:
        return "—"
    match = re.search(r"(\d+)\s*$", ticket.title.strip())
    if match:
        return match.group(1)
    return str(ticket.sort_order) if ticket.sort_order else ticket.title


def infer_ticket_id_from_answers(db: Session, attempt_id: int) -> int | None:
    """Восстановить билет по сохранённым ответам (старые попытки без ticket_id)."""
    rows = (
        db.query(Question.ticket_id)
        .join(Answer, Answer.question_id == Question.id)
        .filter(Answer.attempt_id == attempt_id, Question.ticket_id.isnot(None))
        .distinct()
        .all()
    )
    ticket_ids = sorted({row[0] for row in rows})
    if len(ticket_ids) == 1:
        return ticket_ids[0]
    return ticket_ids[0] if ticket_ids else None


def resolve_attempt_ticket(db: Session, attempt: TestAttempt) -> TestTicket | None:
    if attempt.ticket:
        return attempt.ticket
    ticket_id = attempt.ticket_id or infer_ticket_id_from_answers(db, attempt.id)
    if not ticket_id:
        return None
    return db.get(TestTicket, ticket_id)


def attempt_ticket_label(db: Session, attempt: TestAttempt) -> str:
    return ticket_number_label(resolve_attempt_ticket(db, attempt))


def backfill_attempt_ticket_ids(db: Session) -> int:
    """Проставить ticket_id попыткам, где он не был сохранён."""
    updated = 0
    attempts = db.query(TestAttempt).filter(TestAttempt.ticket_id.is_(None)).all()
    for attempt in attempts:
        ticket_id = infer_ticket_id_from_answers(db, attempt.id)
        if ticket_id:
            attempt.ticket_id = ticket_id
            updated += 1
    if updated:
        db.commit()
    return updated

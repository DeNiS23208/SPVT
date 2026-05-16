"""Билеты теста — группы вопросов."""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Question, TestTicket, TestType


def backfill_test_tickets(db: Session) -> None:
    """Создать «Билет 1» и привязать вопросы без билета."""
    for test_type in db.query(TestType).all():
        ticket = (
            db.query(TestTicket)
            .filter(TestTicket.test_type_id == test_type.id)
            .order_by(TestTicket.sort_order, TestTicket.id)
            .first()
        )
        if not ticket:
            ticket = TestTicket(test_type_id=test_type.id, title="Билет 1", sort_order=1)
            db.add(ticket)
            db.flush()

        db.query(Question).filter(
            Question.test_type_id == test_type.id,
            Question.ticket_id.is_(None),
        ).update({Question.ticket_id: ticket.id}, synchronize_session=False)


def default_ticket_for_test(db: Session, test_type_id: int) -> TestTicket:
    ticket = (
        db.query(TestTicket)
        .filter(TestTicket.test_type_id == test_type_id)
        .order_by(TestTicket.sort_order, TestTicket.id)
        .first()
    )
    if ticket:
        return ticket
    ticket = TestTicket(test_type_id=test_type_id, title="Билет 1", sort_order=1)
    db.add(ticket)
    db.flush()
    return ticket


def next_ticket_title(db: Session, test_type_id: int) -> str:
    count = (
        db.query(func.count(TestTicket.id))
        .filter(TestTicket.test_type_id == test_type_id)
        .scalar()
        or 0
    )
    return f"Билет {count + 1}"


def get_ticket_for_test(db: Session, test_type_id: int, ticket_id: int) -> TestTicket | None:
    return (
        db.query(TestTicket)
        .filter(TestTicket.id == ticket_id, TestTicket.test_type_id == test_type_id)
        .first()
    )


def balance_questions_across_tickets(db: Session, test_type_id: int) -> int:
    """Если вопросы лежат только в одном билете, а билетов несколько — разнести по кругу."""
    tickets = (
        db.query(TestTicket)
        .filter(TestTicket.test_type_id == test_type_id)
        .order_by(TestTicket.sort_order, TestTicket.id)
        .all()
    )
    if len(tickets) < 2:
        return 0

    questions = (
        db.query(Question)
        .filter(Question.test_type_id == test_type_id, Question.is_active.is_(True))
        .order_by(Question.sort_order, Question.id)
        .all()
    )
    if not questions:
        return 0

    ticket_ids_with_questions = {q.ticket_id for q in questions if q.ticket_id}
    if len(ticket_ids_with_questions) != 1:
        return 0

    moved = 0
    for index, question in enumerate(questions):
        target = tickets[index % len(tickets)]
        if question.ticket_id != target.id:
            question.ticket_id = target.id
            moved += 1
    if moved:
        db.commit()
    return moved

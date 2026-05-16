import random
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth import parse_options, require_role
from app.database import get_db
from app.models import (
    Answer,
    AttemptStatus,
    Question,
    TestAttempt,
    TestTicket,
    User,
    UserRole,
)
from app.schemas import (
    QuestionOut,
    TestCatalogItemOut,
    TestCatalogOut,
    TestResultOut,
    TestSubmitRequest,
)
from app.services.attempt_tickets import infer_ticket_id_from_answers, pick_random_ticket
from app.services.site_settings import get_pass_threshold
from app.services.test_types import (
    catalog_item_for_user,
    get_test_type_by_slug,
    latest_attempt_for_user,
    list_active_test_types,
)
from app.seed import today_shift_date

router = APIRouter(prefix="/api/test", tags=["test"])


def question_to_out(question: Question) -> QuestionOut:
    return QuestionOut(
        id=question.id,
        text=question.text,
        question_type=question.question_type,
        options=parse_options(question.options_json),
        sort_order=question.sort_order,
    )


def resolve_test_type(db: Session, slug: str):
    test_type = get_test_type_by_slug(db, slug)
    if not test_type:
        raise HTTPException(status_code=404, detail="Тест не найден")
    return test_type


def _questions_for_ticket(
    db: Session,
    test_type_id: int,
    ticket_id: int,
    *,
    shuffle_seed: int | None = None,
) -> list[Question]:
    questions = (
        db.query(Question)
        .filter(
            Question.is_active.is_(True),
            Question.test_type_id == test_type_id,
            Question.ticket_id == ticket_id,
        )
        .order_by(Question.sort_order, Question.id)
        .all()
    )
    if shuffle_seed is not None and len(questions) > 1:
        ordered = list(questions)
        rng = random.Random(shuffle_seed)
        rng.shuffle(ordered)
        return ordered
    return questions


def _ensure_today_attempt(db: Session, user: User, test_type_id: int, shift_date: str) -> TestAttempt:
    attempt = latest_attempt_for_user(db, user.id, test_type_id, shift_date=shift_date)

    if attempt and attempt.status in (AttemptStatus.ready, AttemptStatus.not_ready):
        raise HTTPException(status_code=400, detail="Тест на сегодня уже пройден")

    if attempt and attempt.status == AttemptStatus.reset:
        db.query(Answer).filter(Answer.attempt_id == attempt.id).delete(synchronize_session=False)
        exclude = {attempt.ticket_id} if attempt.ticket_id else None
        ticket = pick_random_ticket(db, test_type_id, exclude_ticket_ids=exclude)
        if not ticket:
            raise HTTPException(status_code=400, detail="Нет билетов с вопросами для этого теста")
        attempt.status = AttemptStatus.in_progress
        attempt.ticket_id = ticket.id
        attempt.reset_at = None
        attempt.score_percent = None
        attempt.passed = None
        attempt.finished_at = None
        db.commit()
        db.refresh(attempt)
        return attempt

    if attempt and attempt.status == AttemptStatus.in_progress:
        if not attempt.ticket_id:
            ticket = pick_random_ticket(db, test_type_id)
            if ticket:
                attempt.ticket_id = ticket.id
                db.commit()
                db.refresh(attempt)
        return attempt

    ticket = pick_random_ticket(db, test_type_id)
    if not ticket:
        raise HTTPException(status_code=400, detail="Нет билетов с вопросами для этого теста")

    attempt = TestAttempt(
        user_id=user.id,
        test_type_id=test_type_id,
        ticket_id=ticket.id,
        shift_date=shift_date,
        status=AttemptStatus.in_progress,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


@router.get("/catalog", response_model=TestCatalogOut)
def get_test_catalog(
    user: Annotated[User, Depends(require_role(UserRole.worker))],
    db: Annotated[Session, Depends(get_db)],
):
    items = [
        TestCatalogItemOut(**catalog_item_for_user(db, user, test_type))
        for test_type in list_active_test_types(db)
    ]
    return TestCatalogOut(tests=items)


@router.get("/questions", response_model=list[QuestionOut])
def get_questions(
    user: Annotated[User, Depends(require_role(UserRole.worker))],
    db: Annotated[Session, Depends(get_db)],
    test_type: str = Query(min_length=1, description="Код теста: gnvp, pdd"),
):
    tt = resolve_test_type(db, test_type)
    shift_date = today_shift_date()
    attempt = _ensure_today_attempt(db, user, tt.id, shift_date)
    if not attempt.ticket_id:
        raise HTTPException(status_code=400, detail="Билет для теста не назначен")
    questions = _questions_for_ticket(
        db, tt.id, attempt.ticket_id, shuffle_seed=attempt.id
    )
    if not questions:
        raise HTTPException(status_code=400, detail="В выбранном билете нет вопросов")
    return [question_to_out(q) for q in questions]


@router.get("/status")
def get_today_status(
    user: Annotated[User, Depends(require_role(UserRole.worker))],
    db: Annotated[Session, Depends(get_db)],
    test_type: str = Query(min_length=1, description="Код теста: gnvp, pdd"),
):
    tt = resolve_test_type(db, test_type)
    shift_date = today_shift_date()
    attempt = latest_attempt_for_user(db, user.id, tt.id, shift_date=shift_date)
    if not attempt or attempt.status in (AttemptStatus.reset, AttemptStatus.in_progress):
        return {
            "test_type": tt.slug,
            "test_title": tt.title,
            "shift_date": shift_date,
            "has_attempt": False,
        }

    return {
        "test_type": tt.slug,
        "test_title": tt.title,
        "shift_date": shift_date,
        "has_attempt": True,
        "attempt_id": attempt.id,
        "status": attempt.status,
        "score_percent": attempt.score_percent,
        "passed": attempt.passed,
        "finished_at": attempt.finished_at,
    }


@router.post("/submit", response_model=TestResultOut)
def submit_test(
    payload: TestSubmitRequest,
    user: Annotated[User, Depends(require_role(UserRole.worker))],
    db: Annotated[Session, Depends(get_db)],
):
    tt = resolve_test_type(db, payload.test_type)
    shift_date = today_shift_date()
    attempt = latest_attempt_for_user(db, user.id, tt.id, shift_date=shift_date)

    if not attempt or attempt.status != AttemptStatus.in_progress:
        raise HTTPException(
            status_code=400,
            detail=f"Тест «{tt.title}» на сегодня уже пройден или не начат. Обновите страницу.",
        )

    if not attempt.ticket_id:
        question_ids = [item.question_id for item in payload.answers]
        rows = (
            db.query(Question.ticket_id)
            .filter(Question.id.in_(question_ids), Question.ticket_id.isnot(None))
            .distinct()
            .all()
        )
        ticket_ids = {row[0] for row in rows}
        if len(ticket_ids) == 1:
            attempt.ticket_id = ticket_ids.pop()
            db.flush()
        elif not ticket_ids:
            inferred = infer_ticket_id_from_answers(db, attempt.id)
            if inferred:
                attempt.ticket_id = inferred
                db.flush()

    if not attempt.ticket_id:
        raise HTTPException(status_code=400, detail="Билет для теста не назначен")

    questions = _questions_for_ticket(
        db, tt.id, attempt.ticket_id, shuffle_seed=attempt.id
    )
    question_map = {q.id: q for q in questions}
    if len(payload.answers) != len(questions):
        raise HTTPException(status_code=400, detail="Нужно ответить на все вопросы билета")

    correct_count = 0

    for item in payload.answers:
        question = question_map.get(item.question_id)
        if not question:
            raise HTTPException(status_code=400, detail=f"Неизвестный вопрос: {item.question_id}")

        is_correct = item.answer.strip() == question.correct_answer.strip()
        if is_correct:
            correct_count += 1

        db.add(
            Answer(
                attempt_id=attempt.id,
                question_id=question.id,
                answer_given=item.answer,
                is_correct=is_correct,
            )
        )

    score = round((correct_count / len(questions)) * 100, 1) if questions else 0.0
    threshold = get_pass_threshold(db)
    passed = score >= threshold
    attempt.score_percent = score
    attempt.passed = passed
    attempt.status = AttemptStatus.ready if passed else AttemptStatus.not_ready
    attempt.finished_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(attempt)

    if passed:
        message = f"Допущен к работе. Результат: {score}%"
    else:
        message = f"Не допущен к работе (порог {threshold}%). Результат: {score}%"

    return TestResultOut(
        attempt_id=attempt.id,
        score_percent=score,
        passed=passed,
        status=attempt.status,
        message=message,
    )

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import parse_options, require_role
from app.database import get_db
from app.models import (
    Answer,
    AttemptStatus,
    Question,
    TestAttempt,
    User,
    UserRole,
)
from app.schemas import QuestionOut, TestResultOut, TestSubmitRequest
from app.services.site_settings import get_pass_threshold
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


@router.get("/questions", response_model=list[QuestionOut])
def get_questions(
    user: Annotated[User, Depends(require_role(UserRole.worker))],
    db: Annotated[Session, Depends(get_db)],
):
    questions = (
        db.query(Question)
        .filter(Question.is_active.is_(True))
        .order_by(Question.sort_order)
        .all()
    )
    return [question_to_out(q) for q in questions]


@router.get("/status")
def get_today_status(
    user: Annotated[User, Depends(require_role(UserRole.worker))],
    db: Annotated[Session, Depends(get_db)],
):
    shift_date = today_shift_date()
    attempt = (
        db.query(TestAttempt)
        .filter(TestAttempt.user_id == user.id, TestAttempt.shift_date == shift_date)
        .order_by(TestAttempt.id.desc())
        .first()
    )
    if not attempt:
        return {"shift_date": shift_date, "has_attempt": False}

    return {
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
    shift_date = today_shift_date()
    existing = (
        db.query(TestAttempt)
        .filter(
            TestAttempt.user_id == user.id,
            TestAttempt.shift_date == shift_date,
            TestAttempt.status != AttemptStatus.in_progress,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Тест на сегодня уже пройден. Повторное прохождение недоступно.",
        )

    questions = (
        db.query(Question)
        .filter(Question.is_active.is_(True))
        .order_by(Question.sort_order)
        .all()
    )
    question_map = {q.id: q for q in questions}
    if len(payload.answers) != len(questions):
        raise HTTPException(status_code=400, detail="Нужно ответить на все вопросы")

    attempt = TestAttempt(user_id=user.id, shift_date=shift_date)
    db.add(attempt)
    db.flush()

    correct_count = 0
    critical_failed = False

    for item in payload.answers:
        question = question_map.get(item.question_id)
        if not question:
            raise HTTPException(status_code=400, detail=f"Неизвестный вопрос: {item.question_id}")

        is_correct = item.answer.strip() == question.correct_answer.strip()
        if is_correct:
            correct_count += 1
        elif question.is_critical:
            critical_failed = True

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
    passed = score >= threshold and not critical_failed
    attempt.score_percent = score
    attempt.passed = passed
    attempt.status = AttemptStatus.ready if passed else AttemptStatus.not_ready
    attempt.finished_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(attempt)

    if passed:
        message = f"Допущен к работе. Результат: {score}%"
    else:
        reason = "критический вопрос" if critical_failed else f"порог {threshold}%"
        message = f"Не допущен к работе ({reason}). Результат: {score}%"

    return TestResultOut(
        attempt_id=attempt.id,
        score_percent=score,
        passed=passed,
        status=attempt.status,
        message=message,
    )

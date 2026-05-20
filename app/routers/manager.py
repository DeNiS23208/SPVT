import json
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.auth import parse_options, require_role
from app.database import get_db
from app.models import (
    Answer,
    AttemptStatus,
    Question,
    QuestionType,
    TestAttempt,
    TestTicket,
    TestType,
    User,
    UserRole,
)
from app.question_answer_utils import serialize_stored_correct
from app.schemas import (
    AttemptSummary,
    DashboardStats,
    ManagerQuestionCreate,
    ManagerQuestionOut,
    TestTicketCreate,
    TestTicketOut,
    TestTypeAdminOut,
    TestTypeCreate,
    TestTypePatch,
    WorkerFilterOptionsOut,
    WorkerFilterTestOption,
    WorkerShiftEntry,
    WorkerShiftListOut,
    WorkerTestLine,
)
from app.seed import today_shift_date
from app.services.export_csv import build_powerbi_csv, fetch_attempts_for_export
from app.services.question_import import build_test_questions_export_xlsx
from app.services.test_tickets import (
    get_ticket_for_test,
    next_ticket_title,
)
from app.services.attempt_tickets import attempt_ticket_label, infer_ticket_id_from_answers
from app.services.test_timing import attempt_time_stats
from app.services.test_types import (
    delete_test_type,
    get_test_type_by_slug,
    list_all_test_types,
    unique_slug,
)

router = APIRouter(prefix="/api/manager", tags=["manager"])


def _attempt_summary(db: Session, attempt: TestAttempt) -> AttemptSummary:
    timing = attempt_time_stats(db, attempt)
    return AttemptSummary(
        attempt_id=attempt.id,
        employee_name=attempt.user.full_name,
        username=attempt.user.username,
        test_title=attempt.test_type.title if attempt.test_type else "—",
        test_slug=attempt.test_type.slug if attempt.test_type else "",
        ticket_label=attempt_ticket_label(db, attempt),
        shift_date=attempt.shift_date,
        started_at=attempt.started_at,
        finished_at=attempt.finished_at,
        score_percent=attempt.score_percent,
        passed=attempt.passed,
        status=attempt.status,
        reset_at=attempt.reset_at,
        can_reset=attempt.status
        in (AttemptStatus.ready, AttemptStatus.not_ready, AttemptStatus.in_progress),
        **timing,
    )


def _test_type_admin_out(db: Session, test_type: TestType) -> TestTypeAdminOut:
    t_count = (
        db.query(func.count(TestTicket.id))
        .filter(TestTicket.test_type_id == test_type.id)
        .scalar()
        or 0
    )
    q_count = (
        db.query(func.count(Question.id))
        .filter(Question.test_type_id == test_type.id, Question.is_active.is_(True))
        .scalar()
        or 0
    )
    return TestTypeAdminOut(
        id=test_type.id,
        slug=test_type.slug,
        title=test_type.title,
        description=test_type.description or "",
        sort_order=test_type.sort_order,
        is_active=test_type.is_active,
        ticket_time_limit_minutes=test_type.ticket_time_limit_minutes,
        question_time_limit_seconds=test_type.question_time_limit_seconds,
        retake_after_days=test_type.retake_after_days,
        tickets_count=int(t_count),
        questions_count=int(q_count),
    )


@router.get("/test-types", response_model=list[TestTypeAdminOut])
def list_test_types(
    _: Annotated[User, Depends(require_role(UserRole.manager, UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
):
    return [_test_type_admin_out(db, tt) for tt in list_all_test_types(db)]


@router.post("/test-types", response_model=TestTypeAdminOut)
def create_test_type(
    payload: TestTypeCreate,
    _: Annotated[User, Depends(require_role(UserRole.manager, UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
):
    title = payload.title.strip()
    description = payload.description.strip()
    if not title or not description:
        raise HTTPException(status_code=400, detail="Заполните название и описание теста")

    max_order = db.query(func.max(TestType.sort_order)).scalar() or 0
    test_type = TestType(
        slug=unique_slug(db, title),
        title=title,
        description=description,
        sort_order=max_order + 1,
        is_active=True,
    )
    db.add(test_type)
    db.commit()
    db.refresh(test_type)
    return _test_type_admin_out(db, test_type)


@router.get("/test-types/{slug}", response_model=TestTypeAdminOut)
def get_test_type(
    slug: str,
    _: Annotated[User, Depends(require_role(UserRole.manager, UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
):
    test_type = get_test_type_by_slug(db, slug, active_only=False)
    if not test_type:
        raise HTTPException(status_code=404, detail="Тест не найден")
    return _test_type_admin_out(db, test_type)


@router.patch("/test-types/{slug}", response_model=TestTypeAdminOut)
def patch_test_type(
    slug: str,
    payload: TestTypePatch,
    _: Annotated[User, Depends(require_role(UserRole.manager, UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
):
    test_type = get_test_type_by_slug(db, slug, active_only=False)
    if not test_type:
        raise HTTPException(status_code=404, detail="Тест не найден")
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Нет данных для обновления")
    ticket_limit = updates.get("ticket_time_limit_minutes")
    if ticket_limit is not None and (ticket_limit < 1 or ticket_limit > 480):
        raise HTTPException(status_code=400, detail="Время на билет: от 1 до 480 минут")
    question_limit = updates.get("question_time_limit_seconds")
    if question_limit is not None and (question_limit < 15 or question_limit > 3600):
        raise HTTPException(
            status_code=400,
            detail="Время на вопрос: от 15 секунд до 60 минут",
        )
    retake_days = updates.get("retake_after_days")
    if retake_days is not None and (retake_days < 1 or retake_days > 3650):
        raise HTTPException(
            status_code=400,
            detail="Таймаут повторной сдачи: от 1 до 3650 дней",
        )
    for key, value in updates.items():
        setattr(test_type, key, value)
    db.commit()
    db.refresh(test_type)
    return _test_type_admin_out(db, test_type)


@router.delete("/test-types/{slug}")
def remove_test_type(
    slug: str,
    _: Annotated[User, Depends(require_role(UserRole.manager, UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
):
    test_type = get_test_type_by_slug(db, slug, active_only=False)
    if not test_type:
        raise HTTPException(status_code=404, detail="Тест не найден")

    title = test_type.title
    delete_test_type(db, test_type)
    return {"deleted": True, "title": title, "message": f"Тест «{title}» удалён"}


@router.get("/test-types/{slug}/questions/export")
def export_questions_excel(
    slug: str,
    _: Annotated[User, Depends(require_role(UserRole.manager, UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
):
    test_type = get_test_type_by_slug(db, slug, active_only=False)
    if not test_type:
        raise HTTPException(status_code=404, detail="Тест не найден")

    content = build_test_questions_export_xlsx(db, test_type.id)
    filename = f"voprosy_{slug}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _manager_question_out(question: Question) -> ManagerQuestionOut:
    return ManagerQuestionOut(
        id=question.id,
        text=question.text,
        question_type=question.question_type,
        options=parse_options(question.options_json),
        correct_answer=question.correct_answer,
        allow_multiple_correct=bool(question.allow_multiple_correct),
        sort_order=question.sort_order,
    )


def _ticket_out(db: Session, ticket: TestTicket) -> TestTicketOut:
    questions = (
        db.query(Question)
        .filter(Question.ticket_id == ticket.id, Question.is_active.is_(True))
        .order_by(Question.sort_order, Question.id)
        .all()
    )
    return TestTicketOut(
        id=ticket.id,
        title=ticket.title,
        sort_order=ticket.sort_order,
        questions=[_manager_question_out(q) for q in questions],
    )


def _validate_manager_question(payload: ManagerQuestionCreate) -> dict:
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Введите текст вопроса")

    options = [opt.strip() for opt in payload.options if opt and str(opt).strip()]
    if len(options) < 2:
        raise HTTPException(status_code=400, detail="Добавьте минимум два варианта ответа")

    allow_multi = bool(payload.allow_multiple_correct)
    if allow_multi:
        raw = payload.correct_answers if payload.correct_answers is not None else []
        answers = [str(a).strip() for a in raw if str(a).strip()]
        if len(answers) < 2:
            raise HTTPException(
                status_code=400,
                detail="Отметьте минимум два правильных варианта",
            )
        if len(set(answers)) != len(answers):
            raise HTTPException(status_code=400, detail="Правильные варианты не должны повторяться")
        for a in answers:
            if a not in options:
                raise HTTPException(
                    status_code=400,
                    detail="Каждый правильный ответ должен совпадать с одним из вариантов",
                )
        stored = serialize_stored_correct(True, answers)
    else:
        correct = (payload.correct_answer or "").strip()
        if not correct:
            raise HTTPException(status_code=400, detail="Отметьте правильный ответ")
        if correct not in options:
            raise HTTPException(status_code=400, detail="Правильный ответ должен совпадать с одним из вариантов")
        stored = serialize_stored_correct(False, [correct])

    return {
        "text": text,
        "options": options,
        "correct_answer": stored,
        "allow_multiple_correct": allow_multi,
    }


@router.get("/test-types/{slug}/tickets", response_model=list[TestTicketOut])
def list_test_tickets(
    slug: str,
    _: Annotated[User, Depends(require_role(UserRole.manager, UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
):
    test_type = get_test_type_by_slug(db, slug, active_only=False)
    if not test_type:
        raise HTTPException(status_code=404, detail="Тест не найден")

    tickets = (
        db.query(TestTicket)
        .filter(TestTicket.test_type_id == test_type.id)
        .order_by(TestTicket.sort_order, TestTicket.id)
        .all()
    )
    return [_ticket_out(db, ticket) for ticket in tickets]


@router.post("/test-types/{slug}/tickets", response_model=TestTicketOut)
def create_test_ticket(
    slug: str,
    payload: TestTicketCreate,
    _: Annotated[User, Depends(require_role(UserRole.manager, UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
):
    test_type = get_test_type_by_slug(db, slug, active_only=False)
    if not test_type:
        raise HTTPException(status_code=404, detail="Тест не найден")

    title = payload.title.strip() or next_ticket_title(db, test_type.id)
    max_order = (
        db.query(func.max(TestTicket.sort_order))
        .filter(TestTicket.test_type_id == test_type.id)
        .scalar()
        or 0
    )
    ticket = TestTicket(
        test_type_id=test_type.id,
        title=title,
        sort_order=max_order + 1,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return _ticket_out(db, ticket)


@router.delete("/test-types/{slug}/tickets/{ticket_id}")
def delete_test_ticket(
    slug: str,
    ticket_id: int,
    _: Annotated[User, Depends(require_role(UserRole.manager, UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
):
    test_type = get_test_type_by_slug(db, slug, active_only=False)
    if not test_type:
        raise HTTPException(status_code=404, detail="Тест не найден")

    ticket = get_ticket_for_test(db, test_type.id, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Билет не найден")

    attempts_count = (
        db.query(func.count(TestAttempt.id))
        .filter(TestAttempt.ticket_id == ticket.id)
        .scalar()
        or 0
    )
    if attempts_count:
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя удалить билет: есть {attempts_count} попыток прохождения. "
            "Сначала сбросьте попытки за нужные даты.",
        )

    db.query(Question).filter(Question.ticket_id == ticket.id).delete(synchronize_session=False)
    db.delete(ticket)
    db.commit()
    return {"deleted": True, "id": ticket_id}


@router.post(
    "/test-types/{slug}/tickets/{ticket_id}/questions",
    response_model=ManagerQuestionOut,
)
def create_ticket_question(
    slug: str,
    ticket_id: int,
    payload: ManagerQuestionCreate,
    _: Annotated[User, Depends(require_role(UserRole.manager, UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
):
    test_type = get_test_type_by_slug(db, slug, active_only=False)
    if not test_type:
        raise HTTPException(status_code=404, detail="Тест не найден")

    ticket = get_ticket_for_test(db, test_type.id, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Билет не найден")

    data = _validate_manager_question(payload)
    max_order = (
        db.query(func.max(Question.sort_order))
        .filter(Question.ticket_id == ticket.id)
        .scalar()
        or 0
    )
    question = Question(
        test_type_id=test_type.id,
        ticket_id=ticket.id,
        text=data["text"],
        question_type=QuestionType.single_choice,
        options_json=json.dumps(data["options"], ensure_ascii=False),
        correct_answer=data["correct_answer"],
        allow_multiple_correct=data["allow_multiple_correct"],
        is_critical=False,
        sort_order=max_order + 1,
        is_active=True,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return _manager_question_out(question)


@router.put(
    "/test-types/{slug}/tickets/{ticket_id}/questions/{question_id}",
    response_model=ManagerQuestionOut,
)
def update_ticket_question(
    slug: str,
    ticket_id: int,
    question_id: int,
    payload: ManagerQuestionCreate,
    _: Annotated[User, Depends(require_role(UserRole.manager, UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
):
    test_type = get_test_type_by_slug(db, slug, active_only=False)
    if not test_type:
        raise HTTPException(status_code=404, detail="Тест не найден")

    ticket = get_ticket_for_test(db, test_type.id, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Билет не найден")

    question = (
        db.query(Question)
        .filter(
            Question.id == question_id,
            Question.ticket_id == ticket.id,
            Question.test_type_id == test_type.id,
        )
        .first()
    )
    if not question:
        raise HTTPException(status_code=404, detail="Вопрос не найден")

    data = _validate_manager_question(payload)
    question.text = data["text"]
    question.question_type = QuestionType.single_choice
    question.options_json = json.dumps(data["options"], ensure_ascii=False)
    question.correct_answer = data["correct_answer"]
    question.allow_multiple_correct = data["allow_multiple_correct"]
    db.commit()
    db.refresh(question)
    return _manager_question_out(question)


@router.delete("/test-types/{slug}/tickets/{ticket_id}/questions/{question_id}")
def delete_ticket_question(
    slug: str,
    ticket_id: int,
    question_id: int,
    _: Annotated[User, Depends(require_role(UserRole.manager, UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
):
    test_type = get_test_type_by_slug(db, slug, active_only=False)
    if not test_type:
        raise HTTPException(status_code=404, detail="Тест не найден")

    ticket = get_ticket_for_test(db, test_type.id, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Билет не найден")

    question = (
        db.query(Question)
        .filter(
            Question.id == question_id,
            Question.ticket_id == ticket.id,
            Question.test_type_id == test_type.id,
        )
        .first()
    )
    if not question:
        raise HTTPException(status_code=404, detail="Вопрос не найден")

    db.delete(question)
    db.commit()
    return {"deleted": True, "id": question_id}


_WORKER_FILTER_TITLES = {
    "all": "Все работники",
    "ready": "Готовы к работе",
    "not_ready": "Не готовы",
    "not_started": "Не проходили тест",
}


def _worker_matches_test_filter(
    user_attempts: list[TestAttempt], filter_key: str, test_slug: str | None
) -> bool:
    if not test_slug:
        return True
    test_attempts = [
        a for a in user_attempts if a.test_type and a.test_type.slug == test_slug
    ]
    if filter_key == "not_started":
        return not any(
            a.status in (AttemptStatus.ready, AttemptStatus.not_ready)
            for a in test_attempts
        )
    if filter_key == "ready":
        return any(a.status == AttemptStatus.ready for a in test_attempts)
    if filter_key == "not_ready":
        return any(a.status == AttemptStatus.not_ready for a in test_attempts)
    return len(test_attempts) > 0


def _apply_worker_list_filters(
    rows: list[WorkerShiftEntry],
    q: str | None,
    department: str | None,
    position: str | None,
) -> list[WorkerShiftEntry]:
    needle = (q or "").strip().casefold()
    dept = (department or "").strip()
    pos = (position or "").strip()
    out: list[WorkerShiftEntry] = []
    for row in rows:
        if needle and needle not in row.full_name.casefold():
            continue
        if dept and row.department != dept:
            continue
        if pos and row.position != pos:
            continue
        out.append(row)
    return out


def _parse_workers_shift_date(shift_date: str | None) -> str | None:
    """None — за всё время; иначе YYYY-MM-DD смены."""
    raw = (shift_date or "").strip()
    if raw.lower() in ("all", "*"):
        return None
    if raw:
        return raw
    return today_shift_date()


def _worker_shift_rows(
    db: Session,
    shift: str | None,
    filter_key: str,
    test_slug: str | None = None,
) -> list[WorkerShiftEntry]:
    workers = (
        db.query(User)
        .filter(User.role == UserRole.worker, User.is_active.is_(True))
        .order_by(User.full_name, User.id)
        .all()
    )
    attempts_q = (
        db.query(TestAttempt)
        .options(joinedload(TestAttempt.test_type), joinedload(TestAttempt.ticket))
        .order_by(TestAttempt.user_id, TestAttempt.shift_date.desc(), TestAttempt.id.desc())
    )
    if shift is not None:
        attempts_q = attempts_q.filter(TestAttempt.shift_date == shift)
    attempts = attempts_q.all()
    by_user: dict[int, list[TestAttempt]] = {}
    for attempt in attempts:
        by_user.setdefault(attempt.user_id, []).append(attempt)

    rows: list[WorkerShiftEntry] = []
    for worker in workers:
        user_attempts = by_user.get(worker.id, [])
        has_ready = any(a.status == AttemptStatus.ready for a in user_attempts)
        has_not_ready = any(a.status == AttemptStatus.not_ready for a in user_attempts)
        has_completed = has_ready or has_not_ready

        if filter_key == "all":
            include = True
        elif filter_key == "ready":
            include = has_ready
        elif filter_key == "not_ready":
            include = has_not_ready
        elif filter_key == "not_started":
            include = not has_completed
        else:
            include = False

        if not include:
            continue

        if not _worker_matches_test_filter(user_attempts, filter_key, test_slug):
            continue

        if filter_key == "not_started":
            relevant_attempts: list[TestAttempt] = []
        elif filter_key == "ready":
            relevant_attempts = [a for a in user_attempts if a.status == AttemptStatus.ready]
        elif filter_key == "not_ready":
            relevant_attempts = [a for a in user_attempts if a.status == AttemptStatus.not_ready]
        else:
            relevant_attempts = user_attempts

        if test_slug:
            relevant_attempts = [
                a
                for a in relevant_attempts
                if a.test_type and a.test_type.slug == test_slug
            ]

        tests = [
            WorkerTestLine(
                test_slug=a.test_type.slug if a.test_type else "",
                test_title=a.test_type.title if a.test_type else "—",
                status=a.status,
                score_percent=a.score_percent,
                ticket_label=attempt_ticket_label(db, a),
                shift_date=a.shift_date or "",
                finished_at=a.finished_at,
                reset_at=a.reset_at,
            )
            for a in relevant_attempts
        ]

        rows.append(
            WorkerShiftEntry(
                user_id=worker.id,
                full_name=worker.full_name,
                username=worker.username,
                position=worker.position or "",
                department=worker.department or "",
                tests=tests,
            )
        )

    return rows


@router.get("/workers/filter-options", response_model=WorkerFilterOptionsOut)
def workers_filter_options(
    _: Annotated[User, Depends(require_role(UserRole.manager, UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
):
    departments = [
        row[0]
        for row in (
            db.query(User.department)
            .filter(
                User.role == UserRole.worker,
                User.is_active.is_(True),
                User.department.isnot(None),
                User.department != "",
            )
            .distinct()
            .order_by(User.department)
            .all()
        )
    ]
    positions = [
        row[0]
        for row in (
            db.query(User.position)
            .filter(
                User.role == UserRole.worker,
                User.is_active.is_(True),
                User.position.isnot(None),
                User.position != "",
            )
            .distinct()
            .order_by(User.position)
            .all()
        )
    ]
    tests = [
        WorkerFilterTestOption(slug=tt.slug, title=tt.title)
        for tt in list_all_test_types(db)
    ]
    return WorkerFilterOptionsOut(
        departments=departments,
        positions=positions,
        tests=tests,
    )


@router.get("/workers", response_model=WorkerShiftListOut)
def list_workers_by_filter(
    _: Annotated[User, Depends(require_role(UserRole.manager, UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
    shift_date: str | None = Query(
        default=None,
        description="YYYY-MM-DD смены; all — за всё время; пусто — сегодня",
    ),
    filter: str = Query(default="all", description="all | ready | not_ready | not_started"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    q: str | None = Query(default=None, description="Поиск по ФИО"),
    department: str | None = Query(default=None),
    position: str | None = Query(default=None),
    test: str | None = Query(default=None, description="slug теста"),
):
    shift = _parse_workers_shift_date(shift_date)
    filter_key = filter.strip().lower()
    if filter_key not in _WORKER_FILTER_TITLES:
        raise HTTPException(status_code=400, detail="Неизвестный фильтр")

    test_slug = (test or "").strip() or None
    all_workers = _worker_shift_rows(db, shift, filter_key, test_slug=test_slug)
    all_workers = _apply_worker_list_filters(all_workers, q, department, position)
    total = len(all_workers)
    start = (page - 1) * page_size
    workers = all_workers[start : start + page_size]
    title = _WORKER_FILTER_TITLES[filter_key]
    if shift is None:
        title = f"{title} (за всё время)"
    return WorkerShiftListOut(
        shift_date=shift or "all",
        filter=filter_key,
        title=title,
        count=total,
        page=page,
        page_size=page_size,
        workers=workers,
    )


def _apply_dashboard_results_filters(
    summaries: list[AttemptSummary],
    *,
    last_name: str | None,
    test_slug: str | None,
    attempt_status_raw: str | None,
) -> list[AttemptSummary]:
    """Фильтры таблицы «Результаты» (до пагинации по сотрудникам)."""
    out = list(summaries)
    ln = (last_name or "").strip().casefold()
    if ln:
        out = [s for s in out if ln in s.employee_name.casefold()]
    ts = (test_slug or "").strip().lower()
    if ts:
        out = [s for s in out if (s.test_slug or "").lower() == ts]
    raw = (attempt_status_raw or "").strip().lower()
    if raw:
        if raw not in ("ready", "not_ready", "reset"):
            raise HTTPException(
                status_code=400,
                detail="Статус: готов, не готов или сброшен",
            )
        want = AttemptStatus(raw)
        out = [s for s in out if s.status == want]
    return out


def _attempt_activity_ts(item: AttemptSummary) -> datetime:
    """Время события для сортировки: сброс / завершение / начало попытки."""
    if item.status == AttemptStatus.reset and item.reset_at is not None:
        dt = item.reset_at
    elif item.finished_at is not None:
        dt = item.finished_at
    else:
        dt = item.started_at
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _paginate_attempts_newest_first(
    summaries: list[AttemptSummary],
    *,
    page: int,
    page_size: int,
) -> tuple[list[AttemptSummary], int]:
    """Страница таблицы: попытки по убыванию даты (свежие сверху)."""
    if not summaries:
        return [], 0
    ordered = sorted(summaries, key=_attempt_activity_ts, reverse=True)
    total = len(ordered)
    start = (page - 1) * page_size
    return ordered[start : start + page_size], total


@router.get("/dashboard", response_model=DashboardStats)
def dashboard(
    _: Annotated[User, Depends(require_role(UserRole.manager, UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
    shift_date: str | None = Query(
        default=None,
        description="YYYY-MM-DD; all — за всё время; пусто — сегодня",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    last_name: str | None = Query(default=None, description="Подстрока в ФИО (фамилия и т.д.)"),
    test: str | None = Query(default=None, description="slug теста"),
    attempt_status: str | None = Query(
        default=None,
        description="ready | not_ready | reset",
    ),
):
    shift = _parse_workers_shift_date(shift_date)
    workers = db.query(User).filter(User.role == UserRole.worker, User.is_active.is_(True)).all()
    attempts_q = (
        db.query(TestAttempt)
        .join(TestAttempt.user)
        .options(
            joinedload(TestAttempt.user),
            joinedload(TestAttempt.test_type),
            joinedload(TestAttempt.ticket),
        )
        .filter(User.is_active.is_(True))
        .order_by(TestAttempt.shift_date.desc(), TestAttempt.id.desc())
    )
    if shift is not None:
        attempts_q = attempts_q.filter(TestAttempt.shift_date == shift)
    attempts = attempts_q.all()

    summaries: list[AttemptSummary] = []
    ready = not_ready = in_progress = completed = 0
    workers_with_attempt: set[int] = set()
    workers_ever_completed: set[int] = set()

    for attempt in attempts:
        if attempt.status == AttemptStatus.in_progress:
            in_progress += 1
        elif attempt.status == AttemptStatus.reset:
            pass
        elif attempt.status in (AttemptStatus.ready, AttemptStatus.not_ready):
            completed += 1
            workers_with_attempt.add(attempt.user_id)
            workers_ever_completed.add(attempt.user_id)
            if attempt.status == AttemptStatus.ready:
                ready += 1
            else:
                not_ready += 1

        summaries.append(_attempt_summary(db, attempt))

    if shift is None:
        not_started = len(workers) - len(workers_ever_completed)
    else:
        not_started = len(workers) - len(workers_with_attempt)

    filtered = _apply_dashboard_results_filters(
        summaries,
        last_name=last_name,
        test_slug=test,
        attempt_status_raw=attempt_status,
    )
    total_pages = max(1, (len(filtered) + page_size - 1) // page_size) if filtered else 1
    safe_page = min(page, total_pages) if filtered else 1
    page_attempts, rows_count = _paginate_attempts_newest_first(
        filtered, page=safe_page, page_size=page_size
    )

    return DashboardStats(
        shift_date=shift or "all",
        total_workers=len(workers),
        completed=completed,
        ready=ready,
        not_ready=not_ready,
        in_progress=in_progress,
        not_started=not_started,
        attempts=page_attempts,
        results_page=safe_page,
        results_page_size=page_size,
        results_people_count=rows_count,
    )


@router.post("/attempts/{attempt_id}/reset", response_model=AttemptSummary)
def reset_single_attempt(
    attempt_id: int,
    _: Annotated[User, Depends(require_role(UserRole.manager, UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
):
    attempt = (
        db.query(TestAttempt)
        .options(
            joinedload(TestAttempt.user),
            joinedload(TestAttempt.test_type),
            joinedload(TestAttempt.ticket),
        )
        .filter(TestAttempt.id == attempt_id)
        .first()
    )
    if not attempt:
        raise HTTPException(status_code=404, detail="Попытка не найдена")
    if attempt.status == AttemptStatus.reset:
        raise HTTPException(status_code=400, detail="Попытка уже сброшена")

    if not attempt.ticket_id:
        ticket_id = infer_ticket_id_from_answers(db, attempt.id)
        if ticket_id:
            attempt.ticket_id = ticket_id

    db.query(Answer).filter(Answer.attempt_id == attempt.id).delete(synchronize_session=False)
    attempt.status = AttemptStatus.reset
    attempt.reset_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(attempt)

    summary = _attempt_summary(db, attempt)
    summary.can_reset = False
    return summary


@router.post("/reset-attempt")
def reset_attempt(
    _: Annotated[User, Depends(require_role(UserRole.manager, UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
    shift_date: str | None = Query(default=None, description="YYYY-MM-DD"),
    username: str | None = Query(default=None, description="Логин работника, пусто = все за дату"),
):
    """Сброс попыток за дату — только для тестирования и пересдачи."""
    shift = _parse_workers_shift_date(shift_date)
    if shift is None:
        raise HTTPException(
            status_code=400,
            detail="Сброс за «всё время» недоступен. Укажите дату смены.",
        )
    query = db.query(TestAttempt).filter(TestAttempt.shift_date == shift)
    if username:
        worker = db.query(User).filter(User.username == username, User.role == UserRole.worker).first()
        if not worker:
            return {"deleted": 0, "message": f"Работник «{username}» не найден"}
        query = query.filter(TestAttempt.user_id == worker.id)

    attempts = query.all()
    deleted = 0
    for attempt in attempts:
        db.query(Answer).filter(Answer.attempt_id == attempt.id).delete()
        db.delete(attempt)
        deleted += 1
    db.commit()
    return {"deleted": deleted, "shift_date": shift, "message": "Попытки сброшены, тест можно пройти снова"}


@router.get("/export/powerbi")
def export_powerbi(
    _: Annotated[User, Depends(require_role(UserRole.manager, UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
    shift_date: str | None = Query(default=None, description="YYYY-MM-DD"),
):
    shift = _parse_workers_shift_date(shift_date)
    attempts = fetch_attempts_for_export(db, shift)
    content = build_powerbi_csv(attempts)
    filename = f"spvt_vyvozka_{shift or 'all'}.csv"
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

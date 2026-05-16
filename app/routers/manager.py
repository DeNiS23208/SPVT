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
from app.services.test_types import (
    delete_test_type,
    get_test_type_by_slug,
    list_all_test_types,
    unique_slug,
)

router = APIRouter(prefix="/api/manager", tags=["manager"])


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
    test_type.is_active = payload.is_active
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

    correct = payload.correct_answer.strip()
    if not correct:
        raise HTTPException(status_code=400, detail="Отметьте правильный ответ")
    if correct not in options:
        raise HTTPException(status_code=400, detail="Правильный ответ должен совпадать с одним из вариантов")

    return {
        "text": text,
        "options": options,
        "correct_answer": correct,
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


def _worker_shift_rows(
    db: Session, shift: str, filter_key: str, test_slug: str | None = None
) -> list[WorkerShiftEntry]:
    workers = (
        db.query(User)
        .filter(User.role == UserRole.worker)
        .order_by(User.full_name, User.id)
        .all()
    )
    attempts = (
        db.query(TestAttempt)
        .options(joinedload(TestAttempt.test_type), joinedload(TestAttempt.ticket))
        .filter(TestAttempt.shift_date == shift)
        .order_by(TestAttempt.user_id, TestAttempt.id.desc())
        .all()
    )
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
            .filter(User.role == UserRole.worker, User.department.isnot(None), User.department != "")
            .distinct()
            .order_by(User.department)
            .all()
        )
    ]
    positions = [
        row[0]
        for row in (
            db.query(User.position)
            .filter(User.role == UserRole.worker, User.position.isnot(None), User.position != "")
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
    shift_date: str | None = Query(default=None, description="YYYY-MM-DD"),
    filter: str = Query(default="all", description="all | ready | not_ready | not_started"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    q: str | None = Query(default=None, description="Поиск по ФИО"),
    department: str | None = Query(default=None),
    position: str | None = Query(default=None),
    test: str | None = Query(default=None, description="slug теста"),
):
    shift = shift_date or today_shift_date()
    filter_key = filter.strip().lower()
    if filter_key not in _WORKER_FILTER_TITLES:
        raise HTTPException(status_code=400, detail="Неизвестный фильтр")

    test_slug = (test or "").strip() or None
    all_workers = _worker_shift_rows(db, shift, filter_key, test_slug=test_slug)
    all_workers = _apply_worker_list_filters(all_workers, q, department, position)
    total = len(all_workers)
    start = (page - 1) * page_size
    workers = all_workers[start : start + page_size]
    return WorkerShiftListOut(
        shift_date=shift,
        filter=filter_key,
        title=_WORKER_FILTER_TITLES[filter_key],
        count=total,
        page=page,
        page_size=page_size,
        workers=workers,
    )


@router.get("/dashboard", response_model=DashboardStats)
def dashboard(
    _: Annotated[User, Depends(require_role(UserRole.manager, UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
    shift_date: str | None = Query(default=None, description="YYYY-MM-DD"),
):
    shift = shift_date or today_shift_date()
    workers = db.query(User).filter(User.role == UserRole.worker).all()
    attempts = (
        db.query(TestAttempt)
        .options(
            joinedload(TestAttempt.user),
            joinedload(TestAttempt.test_type),
            joinedload(TestAttempt.ticket),
        )
        .filter(TestAttempt.shift_date == shift)
        .order_by(TestAttempt.id.desc())
        .all()
    )

    summaries: list[AttemptSummary] = []
    ready = not_ready = in_progress = completed = 0
    workers_with_attempt: set[int] = set()

    for attempt in attempts:
        if attempt.status == AttemptStatus.in_progress:
            in_progress += 1
        elif attempt.status == AttemptStatus.reset:
            pass
        elif attempt.status in (AttemptStatus.ready, AttemptStatus.not_ready):
            completed += 1
            workers_with_attempt.add(attempt.user_id)
            if attempt.status == AttemptStatus.ready:
                ready += 1
            else:
                not_ready += 1

        summaries.append(
            AttemptSummary(
                attempt_id=attempt.id,
                employee_name=attempt.user.full_name,
                username=attempt.user.username,
                test_title=attempt.test_type.title if attempt.test_type else "—",
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
            )
        )

    not_started = len(workers) - len(workers_with_attempt)

    return DashboardStats(
        shift_date=shift,
        total_workers=len(workers),
        completed=completed,
        ready=ready,
        not_ready=not_ready,
        in_progress=in_progress,
        not_started=not_started,
        attempts=summaries,
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

    return AttemptSummary(
        attempt_id=attempt.id,
        employee_name=attempt.user.full_name,
        username=attempt.user.username,
        test_title=attempt.test_type.title if attempt.test_type else "—",
        ticket_label=attempt_ticket_label(db, attempt),
        shift_date=attempt.shift_date,
        started_at=attempt.started_at,
        finished_at=attempt.finished_at,
        score_percent=attempt.score_percent,
        passed=attempt.passed,
        status=attempt.status,
        reset_at=attempt.reset_at,
        can_reset=False,
    )


@router.post("/reset-attempt")
def reset_attempt(
    _: Annotated[User, Depends(require_role(UserRole.manager, UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
    shift_date: str | None = Query(default=None, description="YYYY-MM-DD"),
    username: str | None = Query(default=None, description="Логин работника, пусто = все за дату"),
):
    """Сброс попыток за дату — только для тестирования и пересдачи."""
    shift = shift_date or today_shift_date()
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
    shift = shift_date or today_shift_date()
    attempts = fetch_attempts_for_export(db, shift)
    content = build_powerbi_csv(attempts)
    filename = f"spvt_vyvozka_{shift}.csv"
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

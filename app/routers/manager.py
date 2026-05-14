from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.auth import require_role
from app.database import get_db
from app.models import Answer, AttemptStatus, TestAttempt, User, UserRole
from app.schemas import AttemptSummary, DashboardStats
from app.seed import today_shift_date
from app.services.export_csv import build_powerbi_csv, fetch_attempts_for_export

router = APIRouter(prefix="/api/manager", tags=["manager"])


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
        .options(joinedload(TestAttempt.user))
        .filter(TestAttempt.shift_date == shift)
        .order_by(TestAttempt.id.desc())
        .all()
    )

    latest_by_user: dict[int, TestAttempt] = {}
    for attempt in attempts:
        if attempt.user_id not in latest_by_user:
            latest_by_user[attempt.user_id] = attempt

    summaries: list[AttemptSummary] = []
    ready = not_ready = in_progress = completed = 0

    for worker in workers:
        attempt = latest_by_user.get(worker.id)
        if not attempt:
            continue

        summaries.append(
            AttemptSummary(
                attempt_id=attempt.id,
                employee_name=worker.full_name,
                username=worker.username,
                shift_date=attempt.shift_date,
                started_at=attempt.started_at,
                finished_at=attempt.finished_at,
                score_percent=attempt.score_percent,
                passed=attempt.passed,
                status=attempt.status,
            )
        )

        if attempt.status == AttemptStatus.in_progress:
            in_progress += 1
        else:
            completed += 1
            if attempt.status == AttemptStatus.ready:
                ready += 1
            elif attempt.status == AttemptStatus.not_ready:
                not_ready += 1

    not_started = len(workers) - len(latest_by_user)

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

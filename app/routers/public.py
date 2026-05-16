from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, UserRole
from app.schemas import DepartmentWorkerOut, SiteSettingsOut, WorkerLookupOut
from app.services.site_settings import get_all_settings
from app.services.worker_lookup import find_workers_by_name

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/site-settings", response_model=SiteSettingsOut)
def public_site_settings(db: Annotated[Session, Depends(get_db)]):
    return SiteSettingsOut(**get_all_settings(db))


@router.get("/departments", response_model=list[str])
def list_departments(db: Annotated[Session, Depends(get_db)]):
    rows = (
        db.query(User.department)
        .filter(User.role == UserRole.worker, User.department.isnot(None), User.department != "")
        .distinct()
        .order_by(User.department)
        .all()
    )
    return [row[0] for row in rows if row[0]]


@router.get("/department-workers", response_model=list[DepartmentWorkerOut])
def list_department_workers(
    db: Annotated[Session, Depends(get_db)],
    department: str = Query(min_length=1, description="Название подразделения"),
):
    dept = department.strip()
    workers = (
        db.query(User)
        .filter(
            User.department == dept,
            User.role.in_((UserRole.worker, UserRole.admin)),
        )
        .order_by(User.full_name)
        .all()
    )
    if not workers:
        raise HTTPException(status_code=404, detail="В этом подразделении нет сотрудников")
    return [DepartmentWorkerOut(username=w.username, full_name=w.full_name) for w in workers]


@router.get("/find-workers", response_model=list[WorkerLookupOut])
def find_workers(
    db: Annotated[Session, Depends(get_db)],
    q: str = Query(min_length=2, max_length=120, description="Фамилия, имя или полное ФИО"),
):
    workers = find_workers_by_name(db, q)
    return [
        WorkerLookupOut(
            username=w.username,
            full_name=w.full_name,
            department=w.department or "",
        )
        for w in workers
    ]

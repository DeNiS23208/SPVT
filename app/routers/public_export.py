import os

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.export_csv import (
    build_powerbi_csv,
    build_powerbi_summary_csv,
    fetch_attempts_for_export,
)
from app.seed import today_shift_date

router = APIRouter(prefix="/api/export/public", tags=["public-export"])

_NO_CACHE = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
}


def verify_export_key(key: str | None) -> None:
    expected = os.environ.get("POWERBI_EXPORT_KEY", "")
    if not expected or not key or key != expected:
        raise HTTPException(status_code=403, detail="Неверный или отсутствует ключ доступа")


def _csv_response(content: str) -> Response:
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers=_NO_CACHE,
    )


def _detail_csv(db: Session, shift_date: str | None) -> Response:
    attempts = fetch_attempts_for_export(db, shift_date)
    return _csv_response(build_powerbi_csv(attempts))


def _summary_csv(db: Session, shift_date: str | None) -> Response:
    attempts = fetch_attempts_for_export(db, shift_date)
    return _csv_response(build_powerbi_summary_csv(attempts))


@router.get("/powerbi.csv")
def public_powerbi_csv(
    db: Session = Depends(get_db),
    key: str = Query(description="Секретный ключ для Power BI"),
    shift_date: str | None = Query(default=None, description="YYYY-MM-DD, пусто = все завершённые"),
):
    verify_export_key(key)
    return _detail_csv(db, shift_date)


@router.get("/powerbi-today.csv")
def public_powerbi_today_csv(
    db: Session = Depends(get_db),
    key: str = Query(description="Секретный ключ для Power BI"),
):
    verify_export_key(key)
    return _detail_csv(db, today_shift_date())


@router.get("/powerbi-svodka.csv")
def public_powerbi_summary_csv(
    db: Session = Depends(get_db),
    key: str = Query(description="Секретный ключ для Power BI"),
    shift_date: str | None = Query(default=None, description="YYYY-MM-DD, пусто = все завершённые"),
):
    verify_export_key(key)
    return _summary_csv(db, shift_date)


@router.get("/powerbi-svodka-today.csv")
def public_powerbi_summary_today_csv(
    db: Session = Depends(get_db),
    key: str = Query(description="Секретный ключ для Power BI"),
):
    verify_export_key(key)
    return _summary_csv(db, today_shift_date())


# Ключ в пути — надёжнее для Power BI (коннектор Web иногда теряет ?key= при обновлении).
@router.get("/k/{key}/powerbi.csv")
def public_powerbi_csv_path(
    key: str,
    db: Session = Depends(get_db),
    shift_date: str | None = Query(default=None, description="YYYY-MM-DD, пусто = все завершённые"),
):
    verify_export_key(key)
    return _detail_csv(db, shift_date)


@router.get("/k/{key}/powerbi-today.csv")
def public_powerbi_today_csv_path(key: str, db: Session = Depends(get_db)):
    verify_export_key(key)
    return _detail_csv(db, today_shift_date())


@router.get("/k/{key}/powerbi-svodka.csv")
def public_powerbi_summary_csv_path(
    key: str,
    db: Session = Depends(get_db),
    shift_date: str | None = Query(default=None, description="YYYY-MM-DD, пусто = все завершённые"),
):
    verify_export_key(key)
    return _summary_csv(db, shift_date)


@router.get("/k/{key}/powerbi-svodka-today.csv")
def public_powerbi_summary_today_csv_path(key: str, db: Session = Depends(get_db)):
    verify_export_key(key)
    return _summary_csv(db, today_shift_date())

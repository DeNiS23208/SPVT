import json
import mimetypes
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth import parse_options, require_role
from app.database import get_db
from app.models import Question, User, UserRole
from app.services.test_types import get_test_type_by_slug
from app.schemas import (
    QuestionAdminOut,
    QuestionCreate,
    QuestionUpdate,
    SiteSettingsOut,
    SiteSettingsUpdate,
)
from app.services.image_optimize import optimize_hero_bytes, optimize_logo_bytes
from app.services.site_settings import get_all_settings, set_settings

router = APIRouter(prefix="/api/admin", tags=["admin"])

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
IMAGES_DIR = STATIC_DIR / "images"
ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/jpg", "image/webp"}


def _question_to_admin_out(question: Question) -> QuestionAdminOut:
    slug = question.test_type.slug if question.test_type else "gnvp"
    return QuestionAdminOut(
        id=question.id,
        test_type=slug,
        text=question.text,
        question_type=question.question_type,
        options=parse_options(question.options_json),
        correct_answer=question.correct_answer,
        allow_multiple_correct=bool(question.allow_multiple_correct),
        is_critical=question.is_critical,
        sort_order=question.sort_order,
        is_active=question.is_active,
    )


def _resolve_content_type(file: UploadFile) -> str:
    content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if content_type in ALLOWED_IMAGE_TYPES:
        return content_type
    guessed, _ = mimetypes.guess_type(file.filename or "")
    if guessed in ALLOWED_IMAGE_TYPES:
        return guessed
    raise HTTPException(status_code=400, detail="Допустимы PNG, JPEG или WebP")


def _save_upload(file: UploadFile, prefix: str) -> str:
    content_type = _resolve_content_type(file)
    raw = file.file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Пустой файл")

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    if prefix == "hero-bg":
        filename = f"{prefix}-{uuid4().hex[:10]}.webp"
        try:
            optimized = optimize_hero_bytes(raw)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Не удалось обработать изображение: {exc}") from exc
    elif prefix == "logo":
        filename = f"{prefix}-{uuid4().hex[:10]}.png"
        try:
            optimized = optimize_logo_bytes(raw)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Не удалось обработать изображение: {exc}") from exc
    else:
        ext = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/webp": ".webp",
        }[content_type]
        filename = f"{prefix}-{uuid4().hex[:10]}{ext}"
        optimized = raw

    target = IMAGES_DIR / filename
    with target.open("wb") as buffer:
        buffer.write(optimized)

    return f"/static/images/{filename}"


@router.get("/settings", response_model=SiteSettingsOut)
def read_settings(
    _: Annotated[User, Depends(require_role(UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
):
    data = get_all_settings(db)
    return SiteSettingsOut(**data)


@router.put("/settings", response_model=SiteSettingsOut)
def update_settings(
    payload: SiteSettingsUpdate,
    _: Annotated[User, Depends(require_role(UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
):
    values = {key: value for key, value in payload.model_dump(exclude_none=True).items()}
    if "pass_threshold" in values:
        try:
            threshold = float(values["pass_threshold"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Порог прохождения должен быть числом") from exc
        if not 0 < threshold <= 100:
            raise HTTPException(status_code=400, detail="Порог прохождения: от 1 до 100")
    if "hero_overlay_opacity" in values:
        try:
            opacity = float(values["hero_overlay_opacity"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Прозрачность оверлея должна быть числом") from exc
        if not 0 <= opacity <= 1:
            raise HTTPException(status_code=400, detail="Прозрачность оверлея: от 0 до 1")

    data = set_settings(db, values)
    return SiteSettingsOut(**data)


@router.post("/upload/background", response_model=SiteSettingsOut)
async def upload_background(
    _: Annotated[User, Depends(require_role(UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
):
    url = _save_upload(file, "hero-bg")
    data = set_settings(db, {"hero_background_url": url})
    return SiteSettingsOut(**data)


@router.post("/upload/logo", response_model=SiteSettingsOut)
async def upload_logo(
    _: Annotated[User, Depends(require_role(UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
    file: UploadFile = File(...),
):
    url = _save_upload(file, "logo")
    data = set_settings(db, {"logo_url": url})
    return SiteSettingsOut(**data)


@router.get("/questions", response_model=list[QuestionAdminOut])
def list_questions(
    _: Annotated[User, Depends(require_role(UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
):
    from sqlalchemy.orm import joinedload

    questions = (
        db.query(Question)
        .options(joinedload(Question.test_type))
        .order_by(Question.sort_order, Question.id)
        .all()
    )
    return [_question_to_admin_out(question) for question in questions]


@router.post("/questions", response_model=QuestionAdminOut)
def create_question(
    payload: QuestionCreate,
    _: Annotated[User, Depends(require_role(UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
):
    tt = get_test_type_by_slug(db, payload.test_type)
    if not tt:
        raise HTTPException(status_code=400, detail="Неизвестный тип теста")
    question = Question(
        test_type_id=tt.id,
        text=payload.text,
        question_type=payload.question_type,
        options_json=json.dumps(payload.options, ensure_ascii=False),
        correct_answer=payload.correct_answer,
        allow_multiple_correct=payload.allow_multiple_correct,
        is_critical=False,
        sort_order=payload.sort_order,
        is_active=payload.is_active,
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return _question_to_admin_out(question)


@router.put("/questions/{question_id}", response_model=QuestionAdminOut)
def update_question(
    question_id: int,
    payload: QuestionUpdate,
    _: Annotated[User, Depends(require_role(UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
):
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Вопрос не найден")

    data = payload.model_dump(exclude_none=True)
    data.pop("is_critical", None)
    if "options" in data:
        question.options_json = json.dumps(data.pop("options"), ensure_ascii=False)
    for key, value in data.items():
        setattr(question, key, value)
    question.is_critical = False

    db.commit()
    db.refresh(question)
    return _question_to_admin_out(question)


@router.delete("/questions/{question_id}")
def delete_question(
    question_id: int,
    _: Annotated[User, Depends(require_role(UserRole.admin))],
    db: Annotated[Session, Depends(get_db)],
):
    question = db.query(Question).filter(Question.id == question_id).first()
    if not question:
        raise HTTPException(status_code=404, detail="Вопрос не найден")
    db.delete(question)
    db.commit()
    return {"deleted": True, "id": question_id}

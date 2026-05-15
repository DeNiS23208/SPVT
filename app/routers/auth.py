from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth import authenticate_user, create_access_token, get_current_user
from app.database import get_db
from app.models import User
from app.schemas import TokenResponse, UserInfo

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
    department: Annotated[str | None, Form()] = None,
):
    dept = department.strip() if department else None
    user = authenticate_user(db, form_data.username, form_data.password, department=dept)
    if not user:
        if dept:
            raise HTTPException(
                status_code=401,
                detail="Неверный логин, пароль или сотрудник не относится к выбранному подразделению",
            )
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")

    token = create_access_token({"sub": user.username, "role": user.role.value})
    return TokenResponse(
        access_token=token,
        role=user.role,
        full_name=user.full_name,
    )


@router.get("/me", response_model=UserInfo)
def me(user: Annotated[User, Depends(get_current_user)]):
    return user

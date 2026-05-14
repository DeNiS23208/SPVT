from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models import AttemptStatus, QuestionType, UserRole


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    full_name: str


class UserInfo(BaseModel):
    id: int
    username: str
    role: UserRole
    full_name: str

    model_config = {"from_attributes": True}


class QuestionOut(BaseModel):
    id: int
    text: str
    question_type: QuestionType
    options: list[str]
    sort_order: int

    model_config = {"from_attributes": True}


class AnswerSubmit(BaseModel):
    question_id: int
    answer: str


class TestSubmitRequest(BaseModel):
    answers: list[AnswerSubmit] = Field(min_length=1)


class TestResultOut(BaseModel):
    attempt_id: int
    score_percent: float
    passed: bool
    status: AttemptStatus
    message: str


class AttemptSummary(BaseModel):
    attempt_id: int
    employee_name: str
    username: str
    shift_date: str
    started_at: datetime
    finished_at: datetime | None
    score_percent: float | None
    passed: bool | None
    status: AttemptStatus

    model_config = {"from_attributes": True}


class DashboardStats(BaseModel):
    shift_date: str
    total_workers: int
    completed: int
    ready: int
    not_ready: int
    in_progress: int
    not_started: int
    attempts: list[AttemptSummary]

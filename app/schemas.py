from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_serializer

from app.models import AttemptStatus, QuestionType, UserRole


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: UserRole
    full_name: str
    position: str | None = None


class UserInfo(BaseModel):
    id: int
    username: str
    role: UserRole
    full_name: str
    position: str | None = None

    model_config = {"from_attributes": True}


class DepartmentWorkerOut(BaseModel):
    username: str
    full_name: str


class WorkerLookupOut(BaseModel):
    username: str
    full_name: str
    department: str


class QuestionOut(BaseModel):
    id: int
    text: str
    question_type: QuestionType
    options: list[str]
    sort_order: int
    allow_multiple_correct: bool = False

    model_config = {"from_attributes": True}


class TestQuestionsResponse(BaseModel):
    """Настройки времени только для текущего теста (не глобально)."""

    timer_mode: str | None = None
    question_time_limit_seconds: int | None = None
    ticket_time_limit_minutes: int | None = None
    questions: list[QuestionOut]


class AnswerSubmit(BaseModel):
    question_id: int
    answer: str


class TestCatalogItemOut(BaseModel):
    slug: str
    title: str
    description: str
    shift_date: str
    can_start: bool
    has_attempt_today: bool
    passed_today: bool | None = None
    status_today: AttemptStatus | None = None
    score_percent_today: float | None = None
    last_passed: bool | None = None
    last_status: AttemptStatus | None = None
    last_score_percent: float | None = None
    last_finished_at: datetime | None = None
    last_correct_count: int | None = None
    last_total_questions: int | None = None
    retake_after_days: int | None = None
    next_retake_at: datetime | None = None

    @field_serializer("last_finished_at")
    @classmethod
    def serialize_last_finished_at(cls, value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.isoformat().replace("+00:00", "Z")

    @field_serializer("next_retake_at")
    @classmethod
    def serialize_next_retake_at(cls, value: datetime | None) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.isoformat().replace("+00:00", "Z")


class TestCatalogOut(BaseModel):
    tests: list[TestCatalogItemOut]


class TestTypeAdminOut(BaseModel):
    id: int
    slug: str
    title: str
    description: str
    sort_order: int
    is_active: bool
    ticket_time_limit_minutes: int | None = None
    question_time_limit_seconds: int | None = None
    retake_after_days: int | None = None
    tickets_count: int = 0
    questions_count: int = 0

    model_config = {"from_attributes": True}


class ManagerQuestionOut(BaseModel):
    id: int
    text: str
    question_type: QuestionType
    options: list[str]
    correct_answer: str
    allow_multiple_correct: bool = False
    sort_order: int


class TestTicketOut(BaseModel):
    id: int
    title: str
    sort_order: int
    questions: list[ManagerQuestionOut] = Field(default_factory=list)


class TestTicketCreate(BaseModel):
    title: str = ""


class ManagerQuestionCreate(BaseModel):
    text: str
    options: list[str] = Field(default_factory=list)
    correct_answer: str = ""
    allow_multiple_correct: bool = False
    correct_answers: list[str] | None = None


class TestTypeCreate(BaseModel):
    title: str = Field(min_length=2, max_length=128, description="Название теста")
    description: str = Field(min_length=1, max_length=2000, description="Описание теста")


class TestTypePatch(BaseModel):
    is_active: bool | None = None
    ticket_time_limit_minutes: int | None = None
    question_time_limit_seconds: int | None = None
    retake_after_days: int | None = None


class TestSubmitRequest(BaseModel):
    test_type: str = Field(min_length=1, description="Код теста, например gnvp или pdd")
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
    test_title: str
    test_slug: str = ""
    ticket_label: str = ""
    shift_date: str
    started_at: datetime
    finished_at: datetime | None
    score_percent: float | None
    passed: bool | None
    status: AttemptStatus
    reset_at: datetime | None = None
    can_reset: bool = True
    elapsed_seconds: int | None = None
    allotted_seconds: int | None = None
    time_limit_kind: str | None = None

    model_config = {"from_attributes": True}


class WorkerTestLine(BaseModel):
    test_slug: str = ""
    test_title: str
    status: AttemptStatus
    score_percent: float | None = None
    ticket_label: str = ""
    shift_date: str = ""
    finished_at: datetime | None = None
    reset_at: datetime | None = None


class WorkerShiftEntry(BaseModel):
    user_id: int
    full_name: str
    username: str
    position: str = ""
    department: str = ""
    tests: list[WorkerTestLine] = Field(default_factory=list)


class WorkerShiftListOut(BaseModel):
    shift_date: str
    filter: str
    title: str
    count: int
    page: int
    page_size: int
    workers: list[WorkerShiftEntry]


class WorkerFilterTestOption(BaseModel):
    slug: str
    title: str


class WorkerFilterOptionsOut(BaseModel):
    departments: list[str]
    positions: list[str]
    tests: list[WorkerFilterTestOption]


class DashboardStats(BaseModel):
    shift_date: str
    total_workers: int
    completed: int
    ready: int
    not_ready: int
    in_progress: int
    not_started: int
    attempts: list[AttemptSummary]
    results_page: int = 1
    results_page_size: int = 10
    results_people_count: int = 0


class GlobalTestSettingsOut(BaseModel):
    """Общие настройки прохождения тестов (для всех типов тестов)."""

    question_time_limit_seconds: int | None = None


class GlobalTestSettingsPatch(BaseModel):
    question_time_limit_seconds: int | None = None


class SiteSettingsOut(BaseModel):
    site_title: str
    site_subtitle: str
    hero_background_url: str
    logo_url: str
    hero_overlay_opacity: str
    accent_color: str
    pass_threshold: str
    question_time_limit_seconds: str = ""


class SiteSettingsUpdate(BaseModel):
    site_title: str | None = None
    site_subtitle: str | None = None
    hero_background_url: str | None = None
    logo_url: str | None = None
    hero_overlay_opacity: str | None = None
    accent_color: str | None = None
    pass_threshold: str | None = None
    question_time_limit_seconds: str | None = None


class QuestionAdminOut(BaseModel):
    id: int
    test_type: str
    text: str
    question_type: QuestionType
    options: list[str]
    correct_answer: str
    allow_multiple_correct: bool = False
    is_critical: bool
    sort_order: int
    is_active: bool

    model_config = {"from_attributes": True}


class QuestionCreate(BaseModel):
    text: str
    question_type: QuestionType
    options: list[str] = Field(default_factory=list)
    correct_answer: str
    allow_multiple_correct: bool = False
    is_critical: bool = False
    sort_order: int = 0
    is_active: bool = True
    test_type: str = "gnvp"


class QuestionUpdate(BaseModel):
    text: str | None = None
    question_type: QuestionType | None = None
    options: list[str] | None = None
    correct_answer: str | None = None
    allow_multiple_correct: bool | None = None
    is_critical: bool | None = None
    sort_order: int | None = None
    is_active: bool | None = None

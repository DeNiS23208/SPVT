from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class UserRole(str, enum.Enum):
    worker = "worker"
    manager = "manager"
    admin = "admin"


class QuestionType(str, enum.Enum):
    yes_no = "yes_no"
    single_choice = "single_choice"


class AttemptStatus(str, enum.Enum):
    in_progress = "in_progress"
    ready = "ready"
    not_ready = "not_ready"
    reset = "reset"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole))
    full_name: Mapped[str] = mapped_column(String(128))
    position: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    attempts: Mapped[list["TestAttempt"]] = relationship(back_populates="user")


class TestType(Base):
    __tablename__ = "test_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    ticket_time_limit_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    questions: Mapped[list["Question"]] = relationship(back_populates="test_type")
    attempts: Mapped[list["TestAttempt"]] = relationship(back_populates="test_type")
    tickets: Mapped[list["TestTicket"]] = relationship(back_populates="test_type")


class TestTicket(Base):
    __tablename__ = "test_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    test_type_id: Mapped[int] = mapped_column(ForeignKey("test_types.id"), index=True)
    title: Mapped[str] = mapped_column(String(128))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    test_type: Mapped["TestType"] = relationship(back_populates="tickets")
    questions: Mapped[list["Question"]] = relationship(back_populates="ticket")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    test_type_id: Mapped[int] = mapped_column(ForeignKey("test_types.id"), index=True)
    ticket_id: Mapped[Optional[int]] = mapped_column(ForeignKey("test_tickets.id"), nullable=True, index=True)
    text: Mapped[str] = mapped_column(Text)
    question_type: Mapped[QuestionType] = mapped_column(Enum(QuestionType))
    options_json: Mapped[str] = mapped_column(Text, default="[]")
    correct_answer: Mapped[str] = mapped_column(String(255))
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    test_type: Mapped["TestType"] = relationship(back_populates="questions")
    ticket: Mapped[Optional["TestTicket"]] = relationship(back_populates="questions")


class TestAttempt(Base):
    __tablename__ = "test_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    test_type_id: Mapped[int] = mapped_column(ForeignKey("test_types.id"), index=True)
    ticket_id: Mapped[Optional[int]] = mapped_column(ForeignKey("test_tickets.id"), nullable=True, index=True)
    shift_date: Mapped[str] = mapped_column(String(10), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    score_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    passed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    status: Mapped[AttemptStatus] = mapped_column(
        Enum(AttemptStatus), default=AttemptStatus.in_progress
    )
    reset_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship(back_populates="attempts")
    test_type: Mapped["TestType"] = relationship(back_populates="attempts")
    ticket: Mapped[Optional["TestTicket"]] = relationship()
    answers: Mapped[list["Answer"]] = relationship(back_populates="attempt")


class SiteSetting(Base):
    __tablename__ = "site_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("test_attempts.id"), index=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"), index=True)
    answer_given: Mapped[str] = mapped_column(String(255))
    is_correct: Mapped[bool] = mapped_column(Boolean)

    attempt: Mapped["TestAttempt"] = relationship(back_populates="answers")
    question: Mapped["Question"] = relationship()


def utcnow() -> datetime:
    return datetime.now(timezone.utc)

"""Перенос данных из SQLite spvt.db в PostgreSQL (если файл есть)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import engine as pg_engine
from app.models import Answer, Question, TestAttempt, User


def migrate(sqlite_path: Path) -> None:
    if not sqlite_path.is_file():
        print("SQLite файл не найден, пропуск миграции")
        return
    if not str(pg_engine.url).startswith("postgresql"):
        print("DATABASE_URL не PostgreSQL, пропуск")
        return

    sqlite_url = f"sqlite:///{sqlite_path.resolve()}"
    src = create_engine(sqlite_url, connect_args={"check_same_thread": False})
    SrcSession = sessionmaker(bind=src)
    DstSession = sessionmaker(bind=pg_engine)

    src_db = SrcSession()
    dst_db = DstSession()
    try:
        if dst_db.query(User).count() > 0:
            print("PostgreSQL уже содержит данные, пропуск")
            return

        for row in src_db.query(User).all():
            dst_db.merge(
                User(
                    id=row.id,
                    username=row.username,
                    password_hash=row.password_hash,
                    role=row.role,
                    full_name=row.full_name,
                )
            )
        for row in src_db.query(Question).all():
            dst_db.merge(
                Question(
                    id=row.id,
                    text=row.text,
                    question_type=row.question_type,
                    options_json=row.options_json,
                    correct_answer=row.correct_answer,
                    is_critical=row.is_critical,
                    sort_order=row.sort_order,
                    is_active=row.is_active,
                )
            )
        for row in src_db.query(TestAttempt).all():
            dst_db.merge(
                TestAttempt(
                    id=row.id,
                    user_id=row.user_id,
                    shift_date=row.shift_date,
                    started_at=row.started_at,
                    finished_at=row.finished_at,
                    score_percent=row.score_percent,
                    passed=row.passed,
                    status=row.status,
                )
            )
        for row in src_db.query(Answer).all():
            dst_db.merge(
                Answer(
                    id=row.id,
                    attempt_id=row.attempt_id,
                    question_id=row.question_id,
                    answer_given=row.answer_given,
                    is_correct=row.is_correct,
                )
            )
        dst_db.commit()
        print("Миграция SQLite → PostgreSQL завершена")
    finally:
        src_db.close()
        dst_db.close()


if __name__ == "__main__":
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "/opt/spvt/spvt.db")
    migrate(path)

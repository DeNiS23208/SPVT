import json
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.auth import hash_password
from app.database import Base, SessionLocal, engine
from app.models import Question, QuestionType, User, UserRole
from app.pg_setup import setup_postgresql_extras
from app.schema_migrate import ensure_admin_role_enum, ensure_site_settings_table, ensure_user_profile_columns

PASS_THRESHOLD = 80.0

QUESTIONS = [
    {
        "text": "Имеете ли вы право допуска к работе при повышенной температуре тела (выше 37,0 °C)?",
        "question_type": QuestionType.yes_no,
        "options_json": json.dumps(["Да", "Нет"], ensure_ascii=False),
        "correct_answer": "Нет",
        "is_critical": True,
        "sort_order": 1,
    },
    {
        "text": "Что необходимо сделать перед началом работы на высоте?",
        "question_type": QuestionType.single_choice,
        "options_json": json.dumps(
            [
                "Начать работу сразу, если есть опыт",
                "Пройти инструктаж, проверить страховочную систему и получить наряд-допуск",
                "Попросить коллегу страховать без СИЗ",
            ],
            ensure_ascii=False,
        ),
        "correct_answer": "Пройти инструктаж, проверить страховочную систему и получить наряд-допуск",
        "is_critical": False,
        "sort_order": 2,
    },
    {
        "text": "Согласно правилам предвахтового допуска: в какой срок работник обязан сообщить начальнику смены о несчастном случае или опасной ситуации?",
        "question_type": QuestionType.single_choice,
        "options_json": json.dumps(
            [
                "В конце смены",
                "Немедленно, как только стало известно",
                "На следующий день в письменном виде",
            ],
            ensure_ascii=False,
        ),
        "correct_answer": "Немедленно, как только стало известно",
        "is_critical": False,
        "sort_order": 3,
    },
    {
        "text": "Допускается ли выход на смену при признаках алкогольного или иного опьянения?",
        "question_type": QuestionType.yes_no,
        "options_json": json.dumps(["Да", "Нет"], ensure_ascii=False),
        "correct_answer": "Нет",
        "is_critical": True,
        "sort_order": 4,
    },
    {
        "text": "Обязан ли работник использовать средства индивидуальной защиты (СИЗ), выданные по нормам?",
        "question_type": QuestionType.yes_no,
        "options_json": json.dumps(["Да", "Нет"], ensure_ascii=False),
        "correct_answer": "Да",
        "is_critical": False,
        "sort_order": 5,
    },
]

USERS = [
    {
        "username": "admin",
        "password": "admin123",
        "role": UserRole.admin,
        "full_name": "Администратор системы",
    },
    {
        "username": "manager",
        "password": "manager123",
        "role": UserRole.manager,
        "full_name": "Начальник смены (тест)",
    },
    {
        "username": "worker",
        "password": "worker123",
        "role": UserRole.worker,
        "full_name": "Иванов Иван Иванович (тест)",
    },
    {
        "username": "worker2",
        "password": "worker123",
        "role": UserRole.worker,
        "full_name": "Петров Пётр Петрович (тест)",
    },
    {
        "username": "worker3",
        "password": "worker123",
        "role": UserRole.worker,
        "full_name": "Сидоров Сидор Сидорович (тест)",
    },
]


def ensure_users(db: Session) -> None:
    for item in USERS:
        exists = db.query(User).filter(User.username == item["username"]).first()
        if exists:
            continue
        db.add(
            User(
                username=item["username"],
                password_hash=hash_password(item["password"]),
                role=item["role"],
                full_name=item["full_name"],
            )
        )


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_user_profile_columns()
    ensure_admin_role_enum()
    ensure_site_settings_table()
    db = SessionLocal()
    try:
        ensure_users(db)

        if db.query(Question).count() == 0:
            for item in QUESTIONS:
                db.add(Question(**item))

        db.commit()

        setup_postgresql_extras()
    finally:
        db.close()


def today_shift_date() -> str:
    return date.today().isoformat()

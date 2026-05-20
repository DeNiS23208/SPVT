import json
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine
from app.models import Question, QuestionType, TestAttempt, TestType
from app.admin_account import ensure_single_admin
from app.pg_setup import setup_postgresql_extras
from app.schema_migrate import (
    ensure_admin_role_enum,
    ensure_site_settings_table,
    ensure_attempt_reset_enum,
    ensure_attempt_ticket_columns,
    ensure_question_multiple_correct,
    ensure_test_tickets_schema,
    ensure_test_type_schema,
    ensure_test_type_ticket_time_limit,
    ensure_test_type_question_time_limit,
    ensure_test_type_retake_after_days,
    ensure_user_profile_columns,
    ensure_user_is_active_column,
)
from app.services.attempt_tickets import backfill_attempt_ticket_ids
from app.services.test_tickets import (
    backfill_test_tickets,
    balance_questions_across_tickets,
    default_ticket_for_test,
)

PASS_THRESHOLD = 80.0

QUESTIONS = [
    {
        "text": "Имеете ли вы право допуска к работе при повышенной температуре тела (выше 37,0 °C)?",
        "question_type": QuestionType.yes_no,
        "options_json": json.dumps(["Да", "Нет"], ensure_ascii=False),
        "correct_answer": "Нет",
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
        "sort_order": 3,
    },
    {
        "text": "Допускается ли выход на смену при признаках алкогольного или иного опьянения?",
        "question_type": QuestionType.yes_no,
        "options_json": json.dumps(["Да", "Нет"], ensure_ascii=False),
        "correct_answer": "Нет",
        "sort_order": 4,
    },
    {
        "text": "Обязан ли работник использовать средства индивидуальной защиты (СИЗ), выданные по нормам?",
        "question_type": QuestionType.yes_no,
        "options_json": json.dumps(["Да", "Нет"], ensure_ascii=False),
        "correct_answer": "Да",
        "sort_order": 5,
    },
]

PDD_QUESTIONS = [
    {
        "text": "Разрешено ли движение по встречной полосе на участке с ремонтными работами, если знаки это не предписывают?",
        "question_type": QuestionType.yes_no,
        "options_json": json.dumps(["Да", "Нет"], ensure_ascii=False),
        "correct_answer": "Нет",
        "sort_order": 1,
    },
    {
        "text": "Какое максимальное расстояние допускается между прицепом и тягачом при буксировке на гибкой сцепке в тёмное время суток?",
        "question_type": QuestionType.single_choice,
        "options_json": json.dumps(
            [
                "2 метра",
                "4 метра",
                "6 метров",
            ],
            ensure_ascii=False,
        ),
        "correct_answer": "4 метра",
        "sort_order": 2,
    },
    {
        "text": "Обязан ли водитель спецтехники использовать ремень безопасности при движении по территории предприятия?",
        "question_type": QuestionType.yes_no,
        "options_json": json.dumps(["Да", "Нет"], ensure_ascii=False),
        "correct_answer": "Да",
        "sort_order": 3,
    },
    {
        "text": "Что делать при обнаружении неисправности тормозной системы перед выездом на маршрут?",
        "question_type": QuestionType.single_choice,
        "options_json": json.dumps(
            [
                "Выехать осторожно и проверить в пути",
                "Сообщить механику/начальнику и не эксплуатировать до устранения",
                "Попросить коллегу подстраховать",
            ],
            ensure_ascii=False,
        ),
        "correct_answer": "Сообщить механику/начальнику и не эксплуатировать до устранения",
        "sort_order": 4,
    },
]

TEST_TYPES = [
    {
        "slug": "gnvp",
        "title": "Тест по ГНВП",
        "description": "Предвахтовый инструктаж по газонефтеводопроявлениям и безопасности работ.",
        "sort_order": 1,
    },
    {
        "slug": "pdd",
        "title": "Тест по ПДД",
        "description": "Правила дорожного движения и безопасность при управлении транспортом.",
        "sort_order": 2,
    },
]


def ensure_test_types(db) -> tuple[TestType, TestType]:
    for item in TEST_TYPES:
        row = db.query(TestType).filter(TestType.slug == item["slug"]).first()
        if not row:
            db.add(TestType(**item))
    db.flush()
    gnvp = db.query(TestType).filter(TestType.slug == "gnvp").one()
    pdd = db.query(TestType).filter(TestType.slug == "pdd").one()
    return gnvp, pdd


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_user_profile_columns()
    ensure_user_is_active_column()
    ensure_test_type_schema()
    ensure_test_type_ticket_time_limit()
    ensure_test_type_question_time_limit()
    ensure_test_type_retake_after_days()
    ensure_test_tickets_schema()
    ensure_question_multiple_correct()
    ensure_attempt_reset_enum()
    ensure_attempt_ticket_columns()
    ensure_admin_role_enum()
    ensure_site_settings_table()
    db = SessionLocal()
    try:
        ensure_single_admin(db)
        gnvp, pdd = ensure_test_types(db)

        backfill_test_tickets(db)

        if db.query(Question).count() == 0:
            gnvp_ticket = default_ticket_for_test(db, gnvp.id)
            for item in QUESTIONS:
                db.add(Question(**item, test_type_id=gnvp.id, ticket_id=gnvp_ticket.id))
        else:
            db.query(Question).filter(Question.test_type_id.is_(None)).update(
                {Question.test_type_id: gnvp.id}, synchronize_session=False
            )

        if not db.query(Question).filter(Question.test_type_id == pdd.id).count():
            pdd_ticket = default_ticket_for_test(db, pdd.id)
            for item in PDD_QUESTIONS:
                db.add(Question(**item, test_type_id=pdd.id, ticket_id=pdd_ticket.id))

        backfill_test_tickets(db)
        backfill_attempt_ticket_ids(db)

        for test_type in db.query(TestType).all():
            balance_questions_across_tickets(db, test_type.id)

        db.query(TestAttempt).filter(TestAttempt.test_type_id.is_(None)).update(
            {TestAttempt.test_type_id: gnvp.id}, synchronize_session=False
        )

        db.commit()

        setup_postgresql_extras()
    finally:
        db.close()


def today_shift_date() -> str:
    return date.today().isoformat()

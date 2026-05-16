import os

from sqlalchemy import text

from app.database import engine, is_postgresql

# Представления для Power BI: только русские названия столбцов.
# Данные подтягиваются автоматически при «Обновить» — это обычные VIEW поверх таблиц.
POWERBI_VIEWS_SQL = """
CREATE OR REPLACE VIEW v_powerbi_export AS
SELECT
    ta.id AS "ID попытки",
    u.full_name AS "ФИО",
    u.username AS "Логин",
    u.position AS "Должность",
    u.department AS "Подразделение",
    ta.shift_date AS "Дата смены",
    ta.started_at AS "Начало теста",
    ta.finished_at AS "Окончание теста",
    ta.score_percent AS "Балл %",
    CASE WHEN ta.passed THEN 'Да' ELSE 'Нет' END AS "Тест пройден",
    CASE
        WHEN ta.status::text = 'ready' THEN 'Допущен'
        WHEN ta.status::text = 'not_ready' THEN 'Не допущен'
        ELSE 'В процессе'
    END AS "Статус",
    CASE WHEN ta.status::text = 'ready' THEN 'Готов' ELSE 'Не готов' END AS "Готовность к работе",
    q.id AS "ID вопроса",
    q.text AS "Вопрос",
    a.answer_given AS "Ответ работника",
    q.correct_answer AS "Правильный ответ",
    CASE WHEN a.is_correct THEN 'Да' ELSE 'Нет' END AS "Ответ верный"
FROM test_attempts ta
JOIN users u ON u.id = ta.user_id
LEFT JOIN answers a ON a.attempt_id = ta.id
LEFT JOIN questions q ON q.id = a.question_id
WHERE ta.finished_at IS NOT NULL;

CREATE OR REPLACE VIEW v_sotrudniki AS
SELECT
    id AS "ID",
    username AS "Логин",
    full_name AS "ФИО",
    position AS "Должность",
    department AS "Подразделение",
    CASE role::text
        WHEN 'worker' THEN 'Работник'
        WHEN 'manager' THEN 'Начальник'
        ELSE role::text
    END AS "Роль"
FROM users;

CREATE OR REPLACE VIEW v_voprosy AS
SELECT
    id AS "ID вопроса",
    text AS "Вопрос",
    CASE question_type::text
        WHEN 'yes_no' THEN 'Да / Нет'
        WHEN 'single_choice' THEN 'Выбор варианта'
        ELSE question_type::text
    END AS "Тип вопроса",
    correct_answer AS "Правильный ответ",
    sort_order AS "Порядок",
    CASE WHEN is_active THEN 'Да' ELSE 'Нет' END AS "Активен"
FROM questions;

CREATE OR REPLACE VIEW v_popytki AS
SELECT
    ta.id AS "ID попытки",
    u.full_name AS "ФИО",
    u.username AS "Логин",
    u.position AS "Должность",
    u.department AS "Подразделение",
    ta.shift_date AS "Дата смены",
    ta.started_at AS "Начало теста",
    ta.finished_at AS "Окончание теста",
    ta.score_percent AS "Балл %",
    CASE WHEN ta.passed THEN 'Да' ELSE 'Нет' END AS "Тест пройден",
    CASE
        WHEN ta.status::text = 'ready' THEN 'Допущен'
        WHEN ta.status::text = 'not_ready' THEN 'Не допущен'
        ELSE 'В процессе'
    END AS "Статус",
    CASE WHEN ta.status::text = 'ready' THEN 'Готов' ELSE 'Не готов' END AS "Готовность к работе"
FROM test_attempts ta
JOIN users u ON u.id = ta.user_id;

CREATE OR REPLACE VIEW v_otvety AS
SELECT
    a.id AS "ID ответа",
    a.attempt_id AS "ID попытки",
    u.full_name AS "ФИО",
    u.username AS "Логин",
    u.position AS "Должность",
    u.department AS "Подразделение",
    ta.shift_date AS "Дата смены",
    q.id AS "ID вопроса",
    q.text AS "Вопрос",
    a.answer_given AS "Ответ работника",
    q.correct_answer AS "Правильный ответ",
    CASE WHEN a.is_correct THEN 'Да' ELSE 'Нет' END AS "Ответ верный"
FROM answers a
JOIN test_attempts ta ON ta.id = a.attempt_id
JOIN users u ON u.id = ta.user_id
JOIN questions q ON q.id = a.question_id;
"""

PBI_VIEW_NAMES = (
    "v_powerbi_export",
    "v_sotrudniki",
    "v_voprosy",
    "v_popytki",
    "v_otvety",
)

RAW_TABLES = ("users", "questions", "test_attempts", "answers")


def setup_postgresql_extras() -> None:
    if not is_postgresql():
        return

    pbi_user = os.environ.get("POWERBI_DB_USER", "powerbi_read")

    with engine.begin() as conn:
        for view_name in reversed(PBI_VIEW_NAMES):
            conn.execute(text(f"DROP VIEW IF EXISTS {view_name} CASCADE"))
        conn.execute(text(POWERBI_VIEWS_SQL))
        conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {pbi_user}"))

        for table in RAW_TABLES:
            conn.execute(text(f"REVOKE ALL ON TABLE {table} FROM {pbi_user}"))

        grants = ", ".join(PBI_VIEW_NAMES)
        conn.execute(text(f"GRANT SELECT ON {grants} TO {pbi_user}"))

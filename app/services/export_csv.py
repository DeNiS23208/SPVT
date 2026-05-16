import csv
import io

from sqlalchemy.orm import Session, joinedload

from app.models import Answer, AttemptStatus, TestAttempt


def build_powerbi_csv(attempts: list[TestAttempt]) -> str:
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", lineterminator="\n")
    writer.writerow(
        [
            "ID попытки",
            "ФИО",
            "Логин",
            "Должность",
            "Подразделение",
            "Дата смены",
            "Начало теста",
            "Окончание теста",
            "Балл %",
            "Тест пройден",
            "Статус",
            "Готовность к работе",
            "ID вопроса",
            "Вопрос",
            "Ответ работника",
            "Правильный ответ",
            "Ответ верный",
        ]
    )

    def status_label(status: AttemptStatus) -> str:
        if status == AttemptStatus.ready:
            return "Допущен"
        if status == AttemptStatus.not_ready:
            return "Не допущен"
        return "В процессе"

    for attempt in attempts:
        readiness = "Готов" if attempt.status == AttemptStatus.ready else "Не готов"
        passed_label = "Да" if attempt.passed else "Нет"
        started = attempt.started_at.isoformat() if attempt.started_at else ""
        finished = attempt.finished_at.isoformat() if attempt.finished_at else ""
        status_ru = status_label(attempt.status)

        if not attempt.answers:
            writer.writerow(
                [
                    attempt.id,
                    attempt.user.full_name,
                    attempt.user.username,
                    attempt.user.position or "",
                    attempt.user.department or "",
                    attempt.shift_date,
                    started,
                    finished,
                    attempt.score_percent,
                    passed_label,
                    status_ru,
                    readiness,
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
            )
            continue

        for answer in sorted(attempt.answers, key=lambda a: a.question.sort_order):
            writer.writerow(
                [
                    attempt.id,
                    attempt.user.full_name,
                    attempt.user.username,
                    attempt.user.position or "",
                    attempt.user.department or "",
                    attempt.shift_date,
                    started,
                    finished,
                    attempt.score_percent,
                    passed_label,
                    status_ru,
                    readiness,
                    answer.question_id,
                    answer.question.text,
                    answer.answer_given,
                    answer.question.correct_answer,
                    "Да" if answer.is_correct else "Нет",
                ]
            )

    return "\ufeff" + output.getvalue()


def build_powerbi_summary_csv(attempts: list[TestAttempt]) -> str:
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";", lineterminator="\n")
    writer.writerow(
        [
            "ID попытки",
            "ФИО",
            "Логин",
            "Должность",
            "Подразделение",
            "Дата смены",
            "Начало теста",
            "Окончание теста",
            "Балл %",
            "Тест пройден",
            "Статус",
            "Готовность к работе",
            "Всего ответов",
            "Верных ответов",
        ]
    )

    def status_label(status: AttemptStatus) -> str:
        if status == AttemptStatus.ready:
            return "Допущен"
        if status == AttemptStatus.not_ready:
            return "Не допущен"
        return "В процессе"

    for attempt in attempts:
        correct_count = sum(1 for a in attempt.answers if a.is_correct)
        writer.writerow(
            [
                attempt.id,
                attempt.user.full_name,
                attempt.user.username,
                attempt.user.position or "",
                attempt.user.department or "",
                attempt.shift_date,
                attempt.started_at.isoformat() if attempt.started_at else "",
                attempt.finished_at.isoformat() if attempt.finished_at else "",
                attempt.score_percent,
                "Да" if attempt.passed else "Нет",
                status_label(attempt.status),
                "Готов" if attempt.status == AttemptStatus.ready else "Не готов",
                len(attempt.answers),
                correct_count,
            ]
        )

    return "\ufeff" + output.getvalue()


def fetch_attempts_for_export(db: Session, shift_date: str | None) -> list[TestAttempt]:
    query = (
        db.query(TestAttempt)
        .options(
            joinedload(TestAttempt.user),
            joinedload(TestAttempt.test_type),
            joinedload(TestAttempt.answers).joinedload(Answer.question),
        )
        .filter(TestAttempt.finished_at.isnot(None))
        .order_by(TestAttempt.id)
    )
    if shift_date:
        query = query.filter(TestAttempt.shift_date == shift_date)
    return query.all()

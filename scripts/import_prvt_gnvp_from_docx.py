#!/usr/bin/env python3
"""Импорт теста «ГНВП для ПРВТ» из Word (.docx) с разбивкой вопросов по билетам."""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.models import Question, QuestionType, TestTicket, TestType
from sqlalchemy import func

from app.seed import init_db

TEST_TITLE = "Тест по ГНВП для ПРВТ"
TEST_SLUG = "gnvp_prvt"
TEST_DESCRIPTION = (
    "Предвахтовый инструктаж по газонефтеводопроявлениям (ПРВТ). "
    "Вопросы для допуска работников к смене."
)
DEFAULT_TICKETS = 5
DEFAULT_SEED = 20260516


def _parse_docx(path: Path) -> list[dict]:
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml")
    root = ET.fromstring(xml)
    paras: list[str] = []
    for p in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
        texts = [
            t.text
            for t in p.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t")
            if t.text
        ]
        if texts:
            paras.append("".join(texts))

    merged: list[str] = []
    buf = ""
    for line in paras:
        line = line.strip()
        if not line:
            continue
        if re.match(r"^\d+\.\s", line) or re.match(r"^[\*]?[a-d]\.\s", line, re.I):
            if buf:
                merged.append(buf.strip())
            buf = line
        else:
            buf += " " + line
    if buf:
        merged.append(buf.strip())

    questions: list[dict] = []
    current: dict | None = None
    for line in merged:
        m = re.match(r"^(\d+)\.\s*(.+)$", line)
        if m:
            if current and current.get("options"):
                questions.append(current)
            current = {"num": int(m.group(1)), "text": m.group(2).strip(), "options": []}
            continue
        om = re.match(r"^(\*?)([a-d])\.\s*(.+)$", line, re.I)
        if om and current is not None:
            current["options"].append(
                {"correct_marker": bool(om.group(1)), "text": om.group(3).strip()}
            )
    if current and current.get("options"):
        questions.append(current)

    for q in questions:
        correct = [o for o in q["options"] if o["correct_marker"]]
        if len(correct) != 1:
            raise ValueError(
                f"Вопрос {q['num']}: ожидается ровно один правильный ответ, найдено {len(correct)}"
            )
        opts = [o["text"] for o in q["options"]]
        q["options_list"] = opts
        q["correct_answer"] = correct[0]["text"]

    return questions


def _split_into_tickets(questions: list[dict], tickets_count: int, seed: int) -> list[list[dict]]:
    shuffled = questions[:]
    rng = random.Random(seed)
    rng.shuffle(shuffled)
    n = max(1, tickets_count)
    chunk = math.ceil(len(shuffled) / n)
    return [shuffled[i * chunk : (i + 1) * chunk] for i in range(n) if shuffled[i * chunk : (i + 1) * chunk]]


def import_test(
    docx_path: Path,
    tickets_count: int,
    seed: int,
    replace: bool,
) -> dict:
    parsed = _parse_docx(docx_path)
    if not parsed:
        raise ValueError("В документе не найдено вопросов")

    init_db()
    db = SessionLocal()
    try:
        test_type = db.query(TestType).filter(TestType.slug == TEST_SLUG).first()
        if test_type and not replace:
            raise SystemExit(
                f"Тест «{TEST_TITLE}» (slug={TEST_SLUG}) уже есть. "
                "Укажите --replace для пересоздания вопросов и билетов."
            )

        if not test_type:
            max_order = db.query(func.max(TestType.sort_order)).scalar() or 0
            sort_order = max_order + 1
            test_type = TestType(
                slug=TEST_SLUG,
                title=TEST_TITLE,
                description=TEST_DESCRIPTION,
                sort_order=sort_order,
                is_active=True,
            )
            db.add(test_type)
            db.flush()
        else:
            db.query(Question).filter(Question.test_type_id == test_type.id).delete(
                synchronize_session=False
            )
            db.query(TestTicket).filter(TestTicket.test_type_id == test_type.id).delete(
                synchronize_session=False
            )
            db.flush()

        ticket_groups = _split_into_tickets(parsed, tickets_count, seed)
        tickets_created = 0
        questions_created = 0

        for ticket_idx, group in enumerate(ticket_groups, start=1):
            ticket = TestTicket(
                test_type_id=test_type.id,
                title=f"Билет {ticket_idx}",
                sort_order=ticket_idx,
            )
            db.add(ticket)
            db.flush()
            tickets_created += 1

            for q_idx, q in enumerate(group, start=1):
                db.add(
                    Question(
                        test_type_id=test_type.id,
                        ticket_id=ticket.id,
                        text=q["text"],
                        question_type=QuestionType.single_choice,
                        options_json=json.dumps(q["options_list"], ensure_ascii=False),
                        correct_answer=q["correct_answer"],
                        sort_order=q_idx,
                        is_active=True,
                    )
                )
                questions_created += 1

        db.commit()
        return {
            "slug": test_type.slug,
            "title": test_type.title,
            "tickets": tickets_created,
            "questions": questions_created,
            "seed": seed,
        }
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "docx",
        nargs="?",
        default=str(Path.home() / "Downloads" / "Тесты по ГНВП для ПРВТ(1).docx"),
        help="Путь к .docx",
    )
    parser.add_argument("--tickets", type=int, default=DEFAULT_TICKETS, help="Число билетов")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Seed для разбивки по билетам")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Пересоздать вопросы и билеты, если тест уже существует",
    )
    args = parser.parse_args()

    path = Path(args.docx).expanduser()
    if not path.is_file():
        raise SystemExit(f"Файл не найден: {path}")

    stats = import_test(path, max(1, args.tickets), args.seed, args.replace)
    print(
        f"Готово: {stats['title']} ({stats['slug']}), "
        f"билетов {stats['tickets']}, вопросов {stats['questions']}, seed={stats['seed']}"
    )


if __name__ == "__main__":
    main()

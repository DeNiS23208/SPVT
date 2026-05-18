#!/usr/bin/env python3
"""Импорт теста из «экзамен по ГНВП.txt»: билеты, один/несколько правильных ответов.

Формат файла: блоки «ВОПРОС N», затем текст, «Варианты ответов:» (или «Правильные пары» для Q48),
варианты с отметкой [✓]. Импорт обрывается перед разделом «СВЕРКА».

Пример:
  python scripts/import_gnvp_exam_txt.py
  python scripts/import_gnvp_exam_txt.py "C:/path/экзамен по ГНВП.txt" --replace --tickets 6
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import func

from app.database import SessionLocal
from app.models import Question, QuestionType, TestTicket, TestType
from app.question_answer_utils import serialize_stored_correct
from app.seed import init_db

TEST_SLUG = "gnvp_text_exam"
TEST_TITLE = "Экзамен по ГНВП"
TEST_DESCRIPTION = (
    "Вопросы из текстового файла экзамена по газонефтеводопроявлениям. "
    "Разбивка по билетам и поддержка нескольких правильных ответов."
)
DEFAULT_TICKETS = 6
DEFAULT_SEED = 20260518
QUESTION_HEADER = re.compile(
    r"^ВОПРОС\s+(\d+)(.*)$",
    re.IGNORECASE | re.MULTILINE,
)
CHECK = re.compile(r"\[\s*✓\s*\]")
JUNK_OPTION = re.compile(r"^-{10,}\s*$|^={10,}\s*$", re.MULTILINE)


def _is_junk_option(opt: str) -> bool:
    s = opt.strip()
    if not s:
        return True
    if JUNK_OPTION.match(s):
        return True
    if re.match(r"^ВОПРОС\s+\d+", s, re.IGNORECASE):
        return True
    return False


def _truncate_before_svarka(raw: str) -> str:
    m = re.search(r"\n={20,}\s*\n\s*СВЕРКА\s*:", raw, re.IGNORECASE)
    if m:
        return raw[: m.start()].strip()
    return raw.strip()


def _options_from_variants_blob(blob: str) -> list[tuple[bool, str]]:
    """После «Варианты ответов:» — варианты разделены пустой строкой."""
    if "Варианты ответов:" in blob:
        _, after = blob.split("Варианты ответов:", 1)
    else:
        after = blob

    lines = after.splitlines()
    chunks: list[list[str]] = []
    cur: list[str] = []
    for line in lines:
        if not line.strip():
            if cur:
                chunks.append(cur)
                cur = []
            continue
        cur.append(line)
    if cur:
        chunks.append(cur)

    out: list[tuple[bool, str]] = []
    for ch in chunks:
        correct = any(CHECK.search(li) for li in ch)
        parts: list[str] = []
        for li in ch:
            s = CHECK.sub("", li).strip()
            if s:
                parts.append(s)
        opt = " ".join(parts)
        opt = re.sub(r"\s+", " ", opt).strip()
        if opt and not _is_junk_option(opt):
            out.append((correct, opt))
    return out


def _parse_matching_48(part: str) -> list[dict]:
    """Вопрос 48 (соответствие) → несколько одиночных вопросов с общим контекстом."""
    intro_m = re.search(
        r"^(ВОПРОС\s+48[^\n]*\n-+?\n)(.+?)(?=Правильные пары)",
        part,
        re.DOTALL | re.IGNORECASE,
    )
    intro = (
        "Соотнесите элементы противовыбросового оборудования с их названием "
        "(фрагмент из экзамена по соответствию рисунка и узла)."
    )
    if intro_m:
        body_intro = intro_m.group(2).strip()
        intro = body_intro.split("Варианты ответов:")[0].strip() or intro

    if "Правильные пары" not in part:
        return []

    after = part.split("Правильные пары", 1)[1]
    lines = [ln.rstrip() for ln in after.splitlines()]
    pairs: list[tuple[str, str]] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = re.match(r"^\s*(\d+)\.\s*(.+)$", ln)
        if not m:
            i += 1
            continue
        left_rest = m.group(2).strip()
        if "→" in left_rest and CHECK.search(left_rest):
            la, rb = left_rest.split("→", 1)
            right = CHECK.sub("", rb).strip()
            pairs.append((la.strip(), right))
            i += 1
            continue
        left = left_rest
        i += 1
        if i >= len(lines):
            break
        ln2 = lines[i]
        if "→" not in ln2:
            i -= 1
            continue
        _, rb = ln2.split("→", 1)
        right = CHECK.sub("", rb).strip()
        pairs.append((left.strip(), right))
        i += 1

    all_rights = [p[1] for p in pairs]
    rng = random.Random(48)
    result: list[dict] = []
    for idx, (left, right) in enumerate(pairs, start=1):
        wrong_pool = [x for x in all_rights if x != right]
        rng.shuffle(wrong_pool)
        wrong_take = wrong_pool[: max(0, 3 - 1)]
        opts = [right] + wrong_take
        while len(opts) < 3 and wrong_pool[len(wrong_take) :]:
            for x in wrong_pool[len(wrong_take) :]:
                if x not in opts:
                    opts.append(x)
                if len(opts) >= 3:
                    break
        if len(opts) < 2:
            opts = [right, "— (нет других вариантов в исходнике) —"]
        rng.shuffle(opts)
        text = f"{intro}\n\nЧасть {idx}/{len(pairs)}: {left}"
        result.append(
            {
                "num": 480 + idx,
                "text": text,
                "options": opts,
                "correct": [right],
                "allow_multiple": False,
            }
        )
    return result


def _parse_question_block(block: str) -> list[dict] | None:
    block = block.strip()
    if not block:
        return None
    hm = QUESTION_HEADER.match(block)
    if not hm:
        return None
    num = int(hm.group(1))
    header_rest = (hm.group(2) or "").strip()
    body = QUESTION_HEADER.sub("", block, count=1).strip()
    body = re.sub(r"^-{20,}\s*\n?", "", body, count=1).strip()
    hl = header_rest.lower()

    if num == 48 or ("соответствие" in hl and "изображение" in hl):
        expanded = _parse_matching_48(block)
        return expanded or None

    allow_multiple = (
        "несколько" in hl
        or "все варианты верны" in hl
        or "все варианты" in hl and "верны" in hl
    )

    opts_raw = _options_from_variants_blob(body)
    if len(opts_raw) < 2:
        return None

    options = [t for _, t in opts_raw if not _is_junk_option(t)]
    correct = [t for ok, t in opts_raw if ok and t in options]
    qtext = body
    if "Варианты ответов:" in qtext:
        qtext = qtext.split("Варианты ответов:", 1)[0].strip()
    qtext = re.sub(r"^-{20,}\s*$", "", qtext, flags=re.MULTILINE).strip()

    if not correct:
        return None
    if not allow_multiple and len(correct) != 1:
        allow_multiple = len(correct) > 1
    if allow_multiple and len(correct) < 2:
        allow_multiple = False
        if len(correct) == 1:
            pass
        else:
            return None

    return [
        {
            "num": num,
            "text": qtext,
            "options": options,
            "correct": correct if allow_multiple else [correct[0]],
            "allow_multiple": allow_multiple,
        }
    ]


def split_question_blocks(raw: str) -> list[str]:
    raw = _truncate_before_svarka(raw)
    starts = [m.start() for m in re.finditer(r"^ВОПРОС\s+\d+", raw, re.MULTILINE | re.IGNORECASE)]
    if not starts:
        return []
    blocks: list[str] = []
    for i, start in enumerate(starts):
        end = starts[i + 1] if i + 1 < len(starts) else len(raw)
        blocks.append(raw[start:end].strip())
    return blocks


def parse_exam_txt(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8")
    parts = split_question_blocks(raw)
    questions: list[dict] = []
    for part in parts:
        parsed = _parse_question_block(part)
        if not parsed:
            continue
        questions.extend(parsed)
    questions.sort(key=lambda q: q["num"])
    return questions


def _split_into_tickets(questions: list[dict], tickets_count: int, seed: int) -> list[list[dict]]:
    shuffled = questions[:]
    rng = random.Random(seed)
    rng.shuffle(shuffled)
    n = max(1, tickets_count)
    chunk = math.ceil(len(shuffled) / n)
    return [shuffled[i * chunk : (i + 1) * chunk] for i in range(n) if shuffled[i * chunk : (i + 1) * chunk]]


def import_test(txt_path: Path, tickets_count: int, seed: int, replace: bool) -> dict:
    parsed = parse_exam_txt(txt_path)
    if not parsed:
        raise ValueError("В файле не найдено вопросов (проверьте кодировку и разделители).")

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
            test_type = TestType(
                slug=TEST_SLUG,
                title=TEST_TITLE,
                description=TEST_DESCRIPTION,
                sort_order=max_order + 1,
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
                allow_m = bool(q["allow_multiple"])
                stored = serialize_stored_correct(allow_m, list(q["correct"]))
                db.add(
                    Question(
                        test_type_id=test_type.id,
                        ticket_id=ticket.id,
                        text=q["text"],
                        question_type=QuestionType.single_choice,
                        options_json=json.dumps(q["options"], ensure_ascii=False),
                        correct_answer=stored,
                        allow_multiple_correct=allow_m,
                        is_critical=False,
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
            "source": str(txt_path),
        }
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "txt",
        nargs="?",
        default=str(ROOT / "экзамен по ГНВП.txt"),
        help="Путь к .txt (по умолчанию — экзамен по ГНВП.txt в корне репозитория)",
    )
    parser.add_argument("--tickets", type=int, default=DEFAULT_TICKETS, help="Число билетов")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Seed разбивки по билетам")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Пересоздать вопросы и билеты, если тест уже существует",
    )
    args = parser.parse_args()

    path = Path(args.txt).expanduser()
    if not path.is_file():
        raise SystemExit(f"Файл не найден: {path}")

    stats = import_test(path, max(1, args.tickets), args.seed, args.replace)
    print(
        f"Готово: {stats['title']} ({stats['slug']}), "
        f"билетов {stats['tickets']}, вопросов {stats['questions']}, seed={stats['seed']}\n"
        f"Источник: {stats['source']}"
    )


if __name__ == "__main__":
    main()

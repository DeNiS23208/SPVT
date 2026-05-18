"""Сравнение ответов: один правильный или несколько (JSON в correct_answer)."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import Question


def expected_correct_answers(question: Question) -> list[str]:
    """Список правильных вариантов (строки как в options)."""
    raw = (question.correct_answer or "").strip()
    if getattr(question, "allow_multiple_correct", False):
        try:
            data = json.loads(raw or "[]")
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        return sorted({str(x).strip() for x in data if str(x).strip()})
    return [raw] if raw else []


def serialize_stored_correct(allow_multiple: bool, answers: list[str]) -> str:
    cleaned = sorted({a.strip() for a in answers if a and str(a).strip()})
    if allow_multiple:
        return json.dumps(cleaned, ensure_ascii=False)
    return cleaned[0] if cleaned else ""


def answer_matches_question(question: Question, given_raw: object) -> bool:
    given = (str(given_raw) if given_raw is not None else "").strip()
    if getattr(question, "allow_multiple_correct", False):
        try:
            selected = json.loads(given)
        except json.JSONDecodeError:
            return False
        if not isinstance(selected, list):
            return False
        sel = sorted({str(x).strip() for x in selected if str(x).strip()})
        exp = expected_correct_answers(question)
        return bool(exp) and sel == exp
    return given == (question.correct_answer or "").strip()

"""Генерация логинов кириллицей из ФИО (фамилия_инициалы)."""
from __future__ import annotations

import re

DEFAULT_PASSWORD = "123"

# Только кириллица, цифры и подчёркивание.
_LOGIN_CLEAN = re.compile(r"[^а-яё0-9_]", re.IGNORECASE)


def normalize_login_part(text: str) -> str:
    return _LOGIN_CLEAN.sub("", text.strip().lower().replace("ё", "е"))


def username_from_name(full_name: str, row_num: int, used: set[str]) -> str:
    parts = [part for part in full_name.split() if part]
    if len(parts) >= 3:
        base = f"{normalize_login_part(parts[0])}_{normalize_login_part(parts[1][0])}{normalize_login_part(parts[2][0])}"
    elif len(parts) == 2:
        base = f"{normalize_login_part(parts[0])}_{normalize_login_part(parts[1][0])}"
    else:
        base = f"сотр_{row_num:04d}"

    base = base[:48] or f"сотр_{row_num:04d}"
    candidate = base
    suffix = 2
    while candidate in used:
        candidate = f"{base}_{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate

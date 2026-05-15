"""Нормализация ФИО для сопоставления с Excel."""
from __future__ import annotations

import re


def normalize_name_key(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower().replace("ё", "е"))


def fio_core_key(name: str) -> str:
    """Фамилия + имя + отчество без хвостов вроде 1981 или ББ11."""
    parts = re.sub(r"\s+", " ", name.strip()).split()
    clean: list[str] = []
    for part in parts:
        low = part.lower()
        if re.fullmatch(r"\d{4}", part):
            continue
        if re.fullmatch(r"бб\d+", low):
            continue
        if re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", part):
            continue
        clean.append(part)
    if len(clean) >= 3:
        return normalize_name_key(" ".join(clean[:3]))
    return normalize_name_key(" ".join(clean))

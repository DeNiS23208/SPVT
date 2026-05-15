#!/usr/bin/env python3
"""Анализ коллизий и «проблемных» логинов в БД."""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.models import User, UserRole
from app.usernames import username_from_name


def main() -> None:
    db = SessionLocal()
    try:
        workers = db.query(User).filter(User.role == UserRole.worker).all()
        print(f"Работников в БД: {len(workers)}")

        by_login = Counter(u.username for u in workers)
        dup_logins = [login for login, c in by_login.items() if c > 1]
        print(f"Дубли логинов (ошибка, не должно быть): {len(dup_logins)}")

        # Одинаковое ФИО
        by_name = Counter(u.full_name.strip().lower() for u in workers)
        dup_names = [(n, c) for n, c in by_name.items() if c > 1]
        print(f"Полностью одинаковое ФИО: {len(dup_names)}")
        for name, c in sorted(dup_names, key=lambda x: -x[1])[:10]:
            print(f"  [{c}] {name}")

        # Одинаковые фамилия + инициалы (база логина без суффикса)
        base_to_users: dict[str, list[User]] = defaultdict(list)
        for u in workers:
            used: set[str] = set()
            base = username_from_name(u.full_name, u.id, used)
            # username_from_name adds suffix; get base by stripping _N
            parts = u.username.rsplit("_", 1)
            if len(parts) == 2 and parts[1].isdigit():
                base_guess = parts[0]
            else:
                base_guess = u.username
            base_to_users[base_guess].append(u)

        collisions = {b: us for b, us in base_to_users.items() if len(us) > 1}
        print(f"Групп с одинаковой базой логина (фамилия+инициалы): {len(collisions)}")
        print(f"  людей в таких группах: {sum(len(v) for v in collisions.values())}")

        # Топ коллизий
        top = sorted(collisions.items(), key=lambda x: -len(x[1]))[:15]
        print("\nПримеры (база логина → сколько человек):")
        for base, users in top:
            print(f"  {base} → {len(users)} чел.")
            for u in users[:3]:
                print(f"      логин: {u.username} | {u.full_name[:55]}")
            if len(users) > 3:
                print(f"      ... ещё {len(users) - 3}")

        # Короткое/пустое ФИО
        short = [u for u in workers if len(u.full_name.split()) < 2]
        print(f"\nФИО без отчества/имени (1 слово): {len(short)}")
        for u in short[:5]:
            print(f"  {u.username} | {u.full_name}")

        # Логины с суффиксом _2, _3 ...
        suffixed = [u for u in workers if u.username.rsplit("_", 1)[-1].isdigit() and int(u.username.rsplit("_", 1)[-1]) >= 2]
        print(f"\nЛогины с суффиксом _2, _3, ... (коллизии): {len(suffixed)}")

        # Повтор фамилии (только фамилия)
        surnames = Counter(u.full_name.split()[0].lower() for u in workers if u.full_name.split())
        common_surname = surnames.most_common(10)
        print("\nСамые частые фамилии (не значит одинаковый логин):")
        for s, c in common_surname:
            print(f"  {s}: {c} чел.")
    finally:
        db.close()


if __name__ == "__main__":
    main()

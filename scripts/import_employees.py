#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.employee_import import import_employees_from_xlsx
from app.seed import init_db


def main() -> None:
    parser = argparse.ArgumentParser(description="Импорт сотрудников из Excel в SPVT")
    parser.add_argument("xlsx", help="Путь к файлу Excel (Сотрудник, Должность, Подразделение)")
    parser.add_argument(
        "--password",
        default=None,
        help="Пароль для аккаунтов (по умолчанию 123)",
    )
    parser.add_argument(
        "--no-update",
        action="store_true",
        help="Не обновлять должность/подразделение у уже существующих",
    )
    args = parser.parse_args()

    path = Path(args.xlsx)
    if not path.is_file():
        raise SystemExit(f"Файл не найден: {path}")

    init_db()
    db = SessionLocal()
    try:
        stats = import_employees_from_xlsx(
            db,
            str(path),
            default_password=args.password,
            update_existing=not args.no_update,
        )
    finally:
        db.close()

    print(f"Создано: {stats.created}")
    print(f"Обновлено: {stats.updated}")
    print(f"Без изменений: {stats.skipped}")


if __name__ == "__main__":
    main()

"""Принудительно TEXT для correct_answer (PostgreSQL, с пересозданием VIEW)."""
from sqlalchemy import text

from app.database import engine, is_postgresql
from app.pg_setup import setup_postgresql_extras

_VIEWS_ON_CORRECT_ANSWER = ("v_powerbi_export", "v_voprosy", "v_otvety")


def main() -> None:
    if not is_postgresql():
        print("skip: not postgresql")
        return
    with engine.begin() as conn:
        for view_name in _VIEWS_ON_CORRECT_ANSWER:
            conn.execute(text(f"DROP VIEW IF EXISTS {view_name} CASCADE"))
            print(f"DROP VIEW {view_name}")
        conn.execute(text("ALTER TABLE questions ALTER COLUMN correct_answer TYPE TEXT"))
        print("ALTER correct_answer -> TEXT ok")
    setup_postgresql_extras()
    print("Power BI views recreated")


if __name__ == "__main__":
    main()

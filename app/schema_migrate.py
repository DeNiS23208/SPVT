from sqlalchemy import inspect, text

from app.database import engine, is_postgresql


def ensure_user_profile_columns() -> None:
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    additions = {
        "position": "VARCHAR(255)",
        "department": "VARCHAR(255)",
    }

    with engine.begin() as conn:
        for name, column_type in additions.items():
            if name in columns:
                continue
            if is_postgresql():
                conn.execute(text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {name} {column_type}"))
            else:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {name} {column_type}"))

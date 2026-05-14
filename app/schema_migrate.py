from sqlalchemy import inspect, text

from app.database import engine, is_postgresql


def ensure_admin_role_enum() -> None:
    if not is_postgresql():
        return
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TYPE userrole ADD VALUE 'admin'"))
    except Exception:
        pass


def ensure_site_settings_table() -> None:
    inspector = inspect(engine)
    if "site_settings" in inspector.get_table_names():
        return
    with engine.begin() as conn:
        if is_postgresql():
            conn.execute(
                text(
                    """
                    CREATE TABLE site_settings (
                        key VARCHAR(64) PRIMARY KEY,
                        value TEXT NOT NULL DEFAULT ''
                    )
                    """
                )
            )
        else:
            conn.execute(
                text(
                    """
                    CREATE TABLE site_settings (
                        key VARCHAR(64) PRIMARY KEY,
                        value TEXT NOT NULL DEFAULT ''
                    )
                    """
                )
            )


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

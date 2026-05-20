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


def ensure_user_is_active_column() -> None:
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "is_active" in columns:
        return
    with engine.begin() as conn:
        if is_postgresql():
            conn.execute(
                text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE")
            )
        else:
            conn.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"))


def ensure_test_type_schema() -> None:
    """Таблица test_types и связь вопросов/попыток с типом теста."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        if "test_types" not in tables:
            if is_postgresql():
                conn.execute(
                    text(
                        """
                        CREATE TABLE test_types (
                            id SERIAL PRIMARY KEY,
                            slug VARCHAR(32) NOT NULL UNIQUE,
                            title VARCHAR(128) NOT NULL,
                            description TEXT,
                            sort_order INTEGER NOT NULL DEFAULT 0,
                            is_active BOOLEAN NOT NULL DEFAULT TRUE
                        )
                        """
                    )
                )
            else:
                conn.execute(
                    text(
                        """
                        CREATE TABLE test_types (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            slug VARCHAR(32) NOT NULL UNIQUE,
                            title VARCHAR(128) NOT NULL,
                            description TEXT,
                            sort_order INTEGER NOT NULL DEFAULT 0,
                            is_active BOOLEAN NOT NULL DEFAULT 1
                        )
                        """
                    )
                )

    inspector = inspect(engine)
    for table in ("questions", "test_attempts"):
        if table not in inspector.get_table_names():
            continue
        columns = {column["name"] for column in inspector.get_columns(table)}
        if "test_type_id" in columns:
            continue
        with engine.begin() as conn:
            if is_postgresql():
                conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS test_type_id INTEGER")
                )
            else:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN test_type_id INTEGER"))


def ensure_test_type_ticket_time_limit() -> None:
    """Лимит времени (минут) на прохождение одного билета."""
    inspector = inspect(engine)
    if "test_types" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("test_types")}
    if "ticket_time_limit_minutes" in columns:
        return
    with engine.begin() as conn:
        if is_postgresql():
            conn.execute(
                text(
                    "ALTER TABLE test_types ADD COLUMN IF NOT EXISTS "
                    "ticket_time_limit_minutes INTEGER"
                )
            )
        else:
            conn.execute(
                text("ALTER TABLE test_types ADD COLUMN ticket_time_limit_minutes INTEGER")
            )


def ensure_test_type_retake_after_days() -> None:
    """Через сколько дней после успешной сдачи нужно проходить тест снова."""
    inspector = inspect(engine)
    if "test_types" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("test_types")}
    if "retake_after_days" in columns:
        return
    with engine.begin() as conn:
        if is_postgresql():
            conn.execute(
                text(
                    "ALTER TABLE test_types ADD COLUMN IF NOT EXISTS "
                    "retake_after_days INTEGER"
                )
            )
        else:
            conn.execute(text("ALTER TABLE test_types ADD COLUMN retake_after_days INTEGER"))


def ensure_test_type_question_time_limit() -> None:
    """Лимит времени (секунд) на один вопрос — отдельно для каждого теста."""
    inspector = inspect(engine)
    if "test_types" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("test_types")}
    if "question_time_limit_seconds" in columns:
        return
    with engine.begin() as conn:
        if is_postgresql():
            conn.execute(
                text(
                    "ALTER TABLE test_types ADD COLUMN IF NOT EXISTS "
                    "question_time_limit_seconds INTEGER"
                )
            )
        else:
            conn.execute(
                text("ALTER TABLE test_types ADD COLUMN question_time_limit_seconds INTEGER")
            )


def ensure_test_tickets_schema() -> None:
    """Билеты (наборы вопросов) внутри теста."""
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        if "test_tickets" not in tables:
            if is_postgresql():
                conn.execute(
                    text(
                        """
                        CREATE TABLE test_tickets (
                            id SERIAL PRIMARY KEY,
                            test_type_id INTEGER NOT NULL REFERENCES test_types(id),
                            title VARCHAR(128) NOT NULL,
                            sort_order INTEGER NOT NULL DEFAULT 0
                        )
                        """
                    )
                )
                conn.execute(
                    text("CREATE INDEX IF NOT EXISTS ix_test_tickets_test_type_id ON test_tickets (test_type_id)")
                )
            else:
                conn.execute(
                    text(
                        """
                        CREATE TABLE test_tickets (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            test_type_id INTEGER NOT NULL,
                            title VARCHAR(128) NOT NULL,
                            sort_order INTEGER NOT NULL DEFAULT 0,
                            FOREIGN KEY(test_type_id) REFERENCES test_types(id)
                        )
                        """
                    )
                )

    inspector = inspect(engine)
    if "questions" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("questions")}
    if "ticket_id" in columns:
        return
    with engine.begin() as conn:
        if is_postgresql():
            conn.execute(text("ALTER TABLE questions ADD COLUMN IF NOT EXISTS ticket_id INTEGER"))
        else:
            conn.execute(text("ALTER TABLE questions ADD COLUMN ticket_id INTEGER"))


def ensure_attempt_reset_enum() -> None:
    if not is_postgresql():
        return
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TYPE attemptstatus ADD VALUE IF NOT EXISTS 'reset'"))
    except Exception:
        try:
            with engine.begin() as conn:
                conn.execute(text("ALTER TYPE attemptstatus ADD VALUE 'reset'"))
        except Exception:
            pass


def ensure_attempt_ticket_columns() -> None:
    inspector = inspect(engine)
    if "test_attempts" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("test_attempts")}
    with engine.begin() as conn:
        if "ticket_id" not in columns:
            if is_postgresql():
                conn.execute(text("ALTER TABLE test_attempts ADD COLUMN IF NOT EXISTS ticket_id INTEGER"))
            else:
                conn.execute(text("ALTER TABLE test_attempts ADD COLUMN ticket_id INTEGER"))
        if "reset_at" not in columns:
            if is_postgresql():
                conn.execute(text("ALTER TABLE test_attempts ADD COLUMN IF NOT EXISTS reset_at TIMESTAMP"))
            else:
                conn.execute(text("ALTER TABLE test_attempts ADD COLUMN reset_at TIMESTAMP"))


def ensure_question_multiple_correct() -> None:
    """Флаг «несколько правильных» и TEXT для длинного JSON correct_answer."""
    inspector = inspect(engine)
    if "questions" not in inspector.get_table_names():
        return
    columns = {c["name"]: c for c in inspector.get_columns("questions")}
    with engine.begin() as conn:
        if "allow_multiple_correct" not in columns:
            if is_postgresql():
                conn.execute(
                    text(
                        "ALTER TABLE questions ADD COLUMN IF NOT EXISTS "
                        "allow_multiple_correct BOOLEAN NOT NULL DEFAULT FALSE"
                    )
                )
            else:
                conn.execute(
                    text(
                        "ALTER TABLE questions ADD COLUMN allow_multiple_correct "
                        "BOOLEAN NOT NULL DEFAULT 0"
                    )
                )
    # VIEW v_* ссылаются на correct_answer — без DROP ALTER не проходит.
    if is_postgresql():
        from app.pg_setup import setup_postgresql_extras

        with engine.begin() as conn:
            for view_name in ("v_powerbi_export", "v_voprosy", "v_otvety"):
                conn.execute(text(f"DROP VIEW IF EXISTS {view_name} CASCADE"))
        with engine.begin() as conn:
            try:
                conn.execute(text("ALTER TABLE questions ALTER COLUMN correct_answer TYPE TEXT"))
            except Exception:
                pass
        setup_postgresql_extras()

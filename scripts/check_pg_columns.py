"""Печать типов колонок таблицы questions в PostgreSQL."""
from sqlalchemy import inspect

from app.database import engine

cols = inspect(engine).get_columns("questions")
for c in cols:
    print(c["name"], c["type"])

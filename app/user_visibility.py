"""Видимость сотрудников на экране входа и в отчётах (демо / презентация)."""
from __future__ import annotations

from app.admin_account import _is_designated_admin
from app.models import User, UserRole
from app.name_utils import fio_core_key, normalize_name_key

# Фамилии, которые оставляем видимыми (по одному представителю на фамилию).
_DEMO_KEEP_SURNAMES = frozenset({"декин", "казанков"})

# Один Сарнецкий для демо (разные подразделения уже дают Декин + Казанков).
_DEMO_KEEP_FULL_NAMES = frozenset(
    {
        normalize_name_key("Сарнецкий Константин Петрович"),
        fio_core_key("Сарнецкий Константин Петрович"),
    }
)


def is_demo_visible_worker(user: User) -> bool:
    if user.role != UserRole.worker:
        return False
    key = fio_core_key(user.full_name)
    if key in _DEMO_KEEP_FULL_NAMES or normalize_name_key(user.full_name) in _DEMO_KEEP_FULL_NAMES:
        return True
    parts = key.split()
    if parts and parts[0] in _DEMO_KEEP_SURNAMES:
        return True
    return False


def should_keep_worker_visible(user: User) -> bool:
    if _is_designated_admin(user):
        return True
    return is_demo_visible_worker(user)


def worker_is_login_visible(user: User) -> bool:
    if user.role == UserRole.admin:
        return True
    if user.role != UserRole.worker:
        return False
    return bool(user.is_active)

"""Единственный администратор системы."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import User, UserRole
from app.name_utils import normalize_name_key
from app.usernames import DEFAULT_PASSWORD

ADMIN_FULL_NAME = "Гуляев Денис Михайлович"
ADMIN_USERNAME = "гуляев_дм"
LEGACY_USERNAMES = frozenset({"админ", "начальник"})


def _is_designated_admin(user: User) -> bool:
    name = normalize_name_key(user.full_name or "")
    if name == normalize_name_key(ADMIN_FULL_NAME):
        return True
    return "гуляев" in name and "денис" in name


def ensure_single_admin(db: Session) -> User:
    password_hash = hash_password(DEFAULT_PASSWORD)
    used = {u.username for u in db.query(User).all() if u.username != ADMIN_USERNAME}

    for legacy in LEGACY_USERNAMES:
        user = db.query(User).filter(User.username == legacy).first()
        if user:
            db.delete(user)

    target = db.query(User).filter(User.username == ADMIN_USERNAME).first()
    if not target:
        for user in db.query(User).filter(User.role.in_((UserRole.admin, UserRole.manager, UserRole.worker))).all():
            if _is_designated_admin(user):
                target = user
                break

    if target:
        if not target.department:
            target.department = "Отдел АСУП (месторождение)"
        target.username = ADMIN_USERNAME
        target.full_name = ADMIN_FULL_NAME
        target.role = UserRole.admin
        target.password_hash = password_hash
    else:
        target = User(
            username=ADMIN_USERNAME,
            password_hash=password_hash,
            role=UserRole.admin,
            full_name=ADMIN_FULL_NAME,
        )
        db.add(target)

    for user in db.query(User).filter(User.role.in_((UserRole.admin, UserRole.manager))).all():
        if user.id != target.id:
            user.role = UserRole.worker

    return target

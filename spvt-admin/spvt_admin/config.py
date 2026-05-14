from __future__ import annotations

from PySide6.QtCore import QSettings

ORG = "INK"
APP = "SPVT-Admin"
DEFAULT_SERVER = "https://45-144-220-51.nip.io"


def settings() -> QSettings:
    return QSettings(ORG, APP)


def server_url() -> str:
    return settings().value("server_url", DEFAULT_SERVER, str).rstrip("/")


def save_server_url(url: str) -> None:
    settings().setValue("server_url", url.rstrip("/"))


def saved_username() -> str:
    return settings().value("username", "admin", str)

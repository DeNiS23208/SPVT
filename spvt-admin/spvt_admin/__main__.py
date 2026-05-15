from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from spvt_admin.ui.login_dialog import LoginDialog
from spvt_admin.ui.main_window import MainWindow
from spvt_admin.ui.styles import APP_STYLESHEET


def _app_icon() -> QIcon | None:
    if getattr(sys, "frozen", False) and getattr(sys, "_MEIPASS", None):
        path = Path(sys._MEIPASS) / "assets" / "spvt-admin.ico"
    else:
        path = Path(__file__).resolve().parent.parent / "assets" / "spvt-admin.ico"
    if path.is_file():
        return QIcon(str(path))
    return None


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SPVT Admin")
    app.setOrganizationName("INK")
    app.setStyleSheet(APP_STYLESHEET)

    icon = _app_icon()
    if icon:
        app.setWindowIcon(icon)

    login = LoginDialog()
    if icon:
        login.setWindowIcon(icon)
    if login.exec() != LoginDialog.DialogCode.Accepted:
        return 0

    assert login.client is not None
    assert login.login_result is not None

    window = MainWindow(
        client=login.client,
        full_name=login.login_result.full_name,
        username=login.login_result.username,
        role=login.login_result.role,
    )
    if icon:
        window.setWindowIcon(icon)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from spvt_admin.ui.login_dialog import LoginDialog
from spvt_admin.ui.main_window import MainWindow
from spvt_admin.ui.styles import APP_STYLESHEET


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("SPVT Admin")
    app.setOrganizationName("INK")
    app.setStyleSheet(APP_STYLESHEET)

    login = LoginDialog()
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
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

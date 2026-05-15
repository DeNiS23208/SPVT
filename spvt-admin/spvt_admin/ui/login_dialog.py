from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from spvt_admin.api_client import ApiError, SpvtApiClient
from spvt_admin.config import save_server_url, save_ssl_verify, saved_username, server_url, ssl_verify_enabled


class LoginDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("SPVT Admin — вход")
        self.setModal(True)
        self.resize(480, 420)
        self._client: SpvtApiClient | None = None
        self._login_result = None

        title = QLabel("SPVT Admin")
        title.setObjectName("title")
        subtitle = QLabel("Панель управления SPVT · подключение к серверу")
        subtitle.setObjectName("subtitle")

        self.server_edit = QLineEdit(server_url())
        self.server_edit.setPlaceholderText("https://45-144-220-51.nip.io")

        self.username_edit = QLineEdit(saved_username())
        self.username_edit.setPlaceholderText("гуляев_дм")

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setPlaceholderText("Пароль")

        self.ssl_insecure_cb = QCheckBox("Не проверять SSL-сертификат (небезопасно)")
        self.ssl_insecure_cb.setChecked(not ssl_verify_enabled())
        ssl_hint = QLabel(
            "Если появляется ошибка про certificate / SSL — включите галочку "
            "или обновите Windows; на сервере должен быть полный цепочный сертификат (fullchain)."
        )
        ssl_hint.setWordWrap(True)
        ssl_hint.setObjectName("subtitle")

        form = QFormLayout()
        form.setSpacing(12)
        form.addRow("Сервер", self.server_edit)
        form.addRow("Логин", self.username_edit)
        form.addRow("Пароль", self.password_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Войти")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primary")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(form)
        layout.addWidget(ssl_hint)
        layout.addWidget(self.ssl_insecure_cb)
        layout.addStretch(1)
        layout.addWidget(buttons)

        self.password_edit.returnPressed.connect(self._on_accept)

    @property
    def client(self) -> SpvtApiClient | None:
        return self._client

    @property
    def login_result(self):
        return self._login_result

    def _on_accept(self) -> None:
        base_url = self.server_edit.text().strip()
        username = self.username_edit.text().strip()
        password = self.password_edit.text()

        if not base_url or not username or not password:
            QMessageBox.warning(self, "Вход", "Заполните сервер, логин и пароль.")
            return

        client = SpvtApiClient(base_url, verify_ssl=not self.ssl_insecure_cb.isChecked())
        try:
            result = client.login(username, password)
        except ApiError as exc:
            QMessageBox.critical(self, "Ошибка входа", str(exc))
            return
        except Exception as exc:
            msg = str(exc)
            extra = ""
            if "CERTIFICATE_VERIFY_FAILED" in msg or "SSL" in msg or "certificate" in msg.lower():
                extra = (
                    "\n\nВключите «Не проверять SSL-сертификат» ниже и повторите вход "
                    "(только если доверяете серверу), либо обновите Windows."
                )
            QMessageBox.critical(
                self,
                "Ошибка соединения",
                f"Не удалось подключиться к серверу:\n{msg}{extra}",
            )
            return

        if result.role != "admin":
            QMessageBox.warning(
                self,
                "Доступ запрещён",
                "Доступ имеет только администратор системы.",
            )
            return

        save_server_url(base_url)
        save_ssl_verify(not self.ssl_insecure_cb.isChecked())
        QSettings("INK", "SPVT-Admin").setValue("username", username)

        self._client = client
        self._login_result = result
        self.accept()

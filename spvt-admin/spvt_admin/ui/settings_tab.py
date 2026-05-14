from __future__ import annotations

from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from spvt_admin.api_client import ApiError, SpvtApiClient


class SettingsTab(QWidget):
    def __init__(self, client: SpvtApiClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.client = client
        self._build_ui()
        self.load_settings()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        hint = QLabel("Настройки внешнего вида и параметров теста на сайте")
        hint.setObjectName("subtitle")
        layout.addWidget(hint)

        form = QFormLayout()
        form.setSpacing(12)
        self.title_edit = QLineEdit()
        self.subtitle_edit = QLineEdit()
        self.threshold_edit = QLineEdit()
        self.opacity_edit = QLineEdit()
        self.accent_edit = QLineEdit()
        self.bg_url_edit = QLineEdit()
        self.logo_url_edit = QLineEdit()

        form.addRow("Заголовок сайта", self.title_edit)
        form.addRow("Подзаголовок", self.subtitle_edit)
        form.addRow("Порог прохождения (%)", self.threshold_edit)
        form.addRow("Затемнение фона (0–1)", self.opacity_edit)
        form.addRow("Акцентный цвет", self.accent_edit)
        form.addRow("URL фона", self.bg_url_edit)
        form.addRow("URL логотипа", self.logo_url_edit)
        layout.addLayout(form)

        upload_row = QHBoxLayout()
        bg_btn = QPushButton("Загрузить фон…")
        bg_btn.clicked.connect(self.upload_background)
        logo_btn = QPushButton("Загрузить логотип…")
        logo_btn.clicked.connect(self.upload_logo)
        upload_row.addWidget(bg_btn)
        upload_row.addWidget(logo_btn)
        upload_row.addStretch(1)
        layout.addLayout(upload_row)

        save_btn = QPushButton("Сохранить настройки")
        save_btn.setObjectName("primary")
        save_btn.clicked.connect(self.save_settings)
        layout.addWidget(save_btn)
        layout.addStretch(1)

    def load_settings(self) -> None:
        try:
            data = self.client.get_settings()
        except ApiError as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))
            return
        self.title_edit.setText(data.get("site_title", ""))
        self.subtitle_edit.setText(data.get("site_subtitle", ""))
        self.threshold_edit.setText(data.get("pass_threshold", ""))
        self.opacity_edit.setText(data.get("hero_overlay_opacity", ""))
        self.accent_edit.setText(data.get("accent_color", ""))
        self.bg_url_edit.setText(data.get("hero_background_url", ""))
        self.logo_url_edit.setText(data.get("logo_url", ""))

    def save_settings(self) -> None:
        payload = {
            "site_title": self.title_edit.text().strip(),
            "site_subtitle": self.subtitle_edit.text().strip(),
            "pass_threshold": self.threshold_edit.text().strip(),
            "hero_overlay_opacity": self.opacity_edit.text().strip(),
            "accent_color": self.accent_edit.text().strip(),
            "hero_background_url": self.bg_url_edit.text().strip(),
            "logo_url": self.logo_url_edit.text().strip(),
        }
        try:
            data = self.client.update_settings(payload)
        except ApiError as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))
            return
        self.bg_url_edit.setText(data.get("hero_background_url", ""))
        self.logo_url_edit.setText(data.get("logo_url", ""))
        QMessageBox.information(self, "Готово", "Настройки сохранены на сервере")

    def upload_background(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите изображение фона", "", "Изображения (*.png *.jpg *.jpeg *.webp)"
        )
        if not path:
            return
        try:
            data = self.client.upload_background(path)
        except ApiError as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))
            return
        self.bg_url_edit.setText(data.get("hero_background_url", ""))
        QMessageBox.information(self, "Готово", "Фон загружен")

    def upload_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите логотип", "", "Изображения (*.png *.jpg *.jpeg *.webp)"
        )
        if not path:
            return
        try:
            data = self.client.upload_logo(path)
        except ApiError as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))
            return
        self.logo_url_edit.setText(data.get("logo_url", ""))
        QMessageBox.information(self, "Готово", "Логотип загружен")

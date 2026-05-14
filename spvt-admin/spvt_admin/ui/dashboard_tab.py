from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QDateEdit,
)

from spvt_admin.api_client import ApiError, SpvtApiClient


STATUS_LABELS = {
    "ready": "Допущен",
    "not_ready": "Не допущен",
    "in_progress": "В процессе",
}


class DashboardTab(QWidget):
    def __init__(self, client: SpvtApiClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.client = client
        self._stat_labels: dict[str, QLabel] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Дата смены:"))
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        toolbar.addWidget(self.date_edit)

        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(refresh_btn)

        export_btn = QPushButton("Выгрузить CSV")
        export_btn.setObjectName("success")
        export_btn.clicked.connect(self.export_csv)
        toolbar.addWidget(export_btn)

        reset_btn = QPushButton("Сбросить попытки")
        reset_btn.setObjectName("danger")
        reset_btn.clicked.connect(self.reset_attempts)
        toolbar.addWidget(reset_btn)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        for key, label in [
            ("total_workers", "Всего работников"),
            ("completed", "Прошли тест"),
            ("ready", "Допущены"),
            ("not_ready", "Не допущены"),
            ("not_started", "Не начали"),
            ("in_progress", "В процессе"),
        ]:
            stats_row.addWidget(self._make_stat_card(key, label))
        layout.addLayout(stats_row)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["ФИО", "Логин", "Балл %", "Статус", "Начало", "Окончание", "ID попытки"]
        )
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, stretch=1)

    def _make_stat_card(self, key: str, label: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("statCard")
        frame.setMinimumWidth(130)
        inner = QVBoxLayout(frame)
        inner.setContentsMargins(14, 12, 14, 12)
        value = QLabel("—")
        value.setObjectName("statValue")
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        caption = QLabel(label)
        caption.setObjectName("statLabel")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        caption.setWordWrap(True)
        inner.addWidget(value)
        inner.addWidget(caption)
        self._stat_labels[key] = value
        return frame

    def _shift_date(self) -> str:
        return self.date_edit.date().toString("yyyy-MM-dd")

    def refresh(self) -> None:
        try:
            data = self.client.get_dashboard(self._shift_date())
        except ApiError as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))
            return
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка соединения", str(exc))
            return

        for key in self._stat_labels:
            self._stat_labels[key].setText(str(data.get(key, "—")))

        attempts = data.get("attempts", [])
        self.table.setRowCount(len(attempts))
        for row, item in enumerate(attempts):
            status = STATUS_LABELS.get(item.get("status"), item.get("status", ""))
            score = item.get("score_percent")
            score_text = f"{score:.0f}" if score is not None else "—"
            started = item.get("started_at", "")
            finished = item.get("finished_at") or "—"
            if isinstance(started, str) and "T" in started:
                started = started.replace("T", " ")[:19]
            if isinstance(finished, str) and "T" in finished:
                finished = finished.replace("T", " ")[:19]

            values = [
                item.get("employee_name", ""),
                item.get("username", ""),
                score_text,
                status,
                started,
                finished,
                str(item.get("attempt_id", "")),
            ]
            for col, text in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(text))

    def export_csv(self) -> None:
        default_name = f"spvt_vyvozka_{self._shift_date()}.csv"
        path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить выгрузку CSV", default_name, "CSV (*.csv)"
        )
        if not path:
            return
        try:
            content = self.client.export_powerbi_csv(self._shift_date())
            with open(path, "wb") as file:
                file.write(content)
        except ApiError as exc:
            QMessageBox.critical(self, "Ошибка выгрузки", str(exc))
            return
        except OSError as exc:
            QMessageBox.critical(self, "Ошибка файла", str(exc))
            return
        QMessageBox.information(self, "Готово", f"Файл сохранён:\n{path}")

    def reset_attempts(self) -> None:
        shift = self._shift_date()
        reply = QMessageBox.question(
            self,
            "Сброс попыток",
            f"Сбросить все попытки за {shift}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            result = self.client.reset_attempts(shift_date=shift)
        except ApiError as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))
            return
        QMessageBox.information(self, "Готово", result.get("message", "Попытки сброшены"))
        self.refresh()

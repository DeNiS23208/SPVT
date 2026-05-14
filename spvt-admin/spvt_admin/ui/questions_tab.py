from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from spvt_admin.api_client import ApiError, SpvtApiClient
from spvt_admin.ui.question_dialog import QuestionDialog

TYPE_LABELS = {
    "yes_no": "Да/Нет",
    "single_choice": "Выбор",
}


class QuestionsTab(QWidget):
    def __init__(self, client: SpvtApiClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.client = client
        self._rows: list[dict] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        toolbar = QHBoxLayout()
        add_btn = QPushButton("Добавить")
        add_btn.setObjectName("primary")
        add_btn.clicked.connect(self.add_question)
        edit_btn = QPushButton("Изменить")
        edit_btn.clicked.connect(self.edit_question)
        del_btn = QPushButton("Удалить")
        del_btn.setObjectName("danger")
        del_btn.clicked.connect(self.delete_question)
        refresh_btn = QPushButton("Обновить")
        refresh_btn.clicked.connect(self.refresh)
        toolbar.addWidget(add_btn)
        toolbar.addWidget(edit_btn)
        toolbar.addWidget(del_btn)
        toolbar.addWidget(refresh_btn)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Порядок", "Тип", "Критич.", "Активен", "Текст"]
        )
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

    def refresh(self) -> None:
        try:
            self._rows = self.client.list_questions()
        except ApiError as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))
            return

        self.table.setRowCount(len(self._rows))
        for row, item in enumerate(self._rows):
            values = [
                str(item.get("id", "")),
                str(item.get("sort_order", "")),
                TYPE_LABELS.get(item.get("question_type"), item.get("question_type", "")),
                "Да" if item.get("is_critical") else "Нет",
                "Да" if item.get("is_active", True) else "Нет",
                item.get("text", ""),
            ]
            for col, text in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(text))

    def _selected_question(self) -> dict | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._rows):
            return None
        return self._rows[row]

    def add_question(self) -> None:
        dialog = QuestionDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.client.create_question(dialog.payload())
        except ApiError as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))
            return
        self.refresh()

    def edit_question(self) -> None:
        question = self._selected_question()
        if not question:
            QMessageBox.information(self, "Выбор", "Выберите вопрос в таблице")
            return
        dialog = QuestionDialog(self, question)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.client.update_question(question["id"], dialog.payload())
        except ApiError as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))
            return
        self.refresh()

    def delete_question(self) -> None:
        question = self._selected_question()
        if not question:
            QMessageBox.information(self, "Выбор", "Выберите вопрос в таблице")
            return
        reply = QMessageBox.question(
            self,
            "Удаление",
            f"Удалить вопрос #{question['id']}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.client.delete_question(question["id"])
        except ApiError as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))
            return
        self.refresh()

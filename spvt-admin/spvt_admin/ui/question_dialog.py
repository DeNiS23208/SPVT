from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)


class QuestionDialog(QDialog):
    def __init__(self, parent=None, question: dict | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Вопрос теста")
        self.resize(520, 420)
        self._question = question or {}

        self.text_edit = QTextEdit(self._question.get("text", ""))
        self.type_combo = QComboBox()
        self.type_combo.addItem("Да / Нет", "yes_no")
        self.type_combo.addItem("Один вариант", "single_choice")
        idx = self.type_combo.findData(self._question.get("question_type", "yes_no"))
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)

        self.options_edit = QTextEdit()
        options = self._question.get("options") or []
        self.options_edit.setPlainText("\n".join(options))
        self.options_edit.setPlaceholderText("Каждый вариант с новой строки")

        self.answer_edit = QLineEdit(self._question.get("correct_answer", ""))
        self.sort_spin = QSpinBox()
        self.sort_spin.setRange(0, 9999)
        self.sort_spin.setValue(int(self._question.get("sort_order", 0)))
        self.critical_check = QCheckBox("Критический вопрос")
        self.critical_check.setChecked(bool(self._question.get("is_critical", False)))
        self.active_check = QCheckBox("Активен")
        self.active_check.setChecked(bool(self._question.get("is_active", True)))

        form = QFormLayout()
        form.addRow("Текст", self.text_edit)
        form.addRow("Тип", self.type_combo)
        form.addRow("Варианты", self.options_edit)
        form.addRow("Правильный ответ", self.answer_edit)
        form.addRow("Порядок", self.sort_spin)
        form.addRow("", self.critical_check)
        form.addRow("", self.active_check)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _validate_and_accept(self) -> None:
        if not self.text_edit.toPlainText().strip():
            QMessageBox.warning(self, "Проверка", "Введите текст вопроса")
            return
        if not self.answer_edit.text().strip():
            QMessageBox.warning(self, "Проверка", "Укажите правильный ответ")
            return
        self.accept()

    def payload(self) -> dict:
        options = [line.strip() for line in self.options_edit.toPlainText().splitlines() if line.strip()]
        qtype = self.type_combo.currentData()
        if qtype == "yes_no" and not options:
            options = ["Да", "Нет"]
        return {
            "text": self.text_edit.toPlainText().strip(),
            "question_type": qtype,
            "options": options,
            "correct_answer": self.answer_edit.text().strip(),
            "is_critical": self.critical_check.isChecked(),
            "sort_order": self.sort_spin.value(),
            "is_active": self.active_check.isChecked(),
        }

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QMainWindow, QStatusBar, QTabWidget, QVBoxLayout, QWidget

from spvt_admin.api_client import SpvtApiClient
from spvt_admin.ui.dashboard_tab import DashboardTab
from spvt_admin.ui.questions_tab import QuestionsTab
from spvt_admin.ui.settings_tab import SettingsTab


class MainWindow(QMainWindow):
    def __init__(
        self,
        client: SpvtApiClient,
        full_name: str,
        username: str,
        role: str,
    ) -> None:
        super().__init__()
        self.client = client
        self.role = role

        self.setWindowTitle("SPVT Admin")
        self.resize(1120, 760)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)

        header = QLabel(f"{full_name} · {username} · {role}")
        header.setObjectName("subtitle")
        layout.addWidget(header)

        self.tabs = QTabWidget()
        self.dashboard_tab = DashboardTab(client)
        self.tabs.addTab(self.dashboard_tab, "Сводка")

        if role == "admin":
            self.settings_tab = SettingsTab(client)
            self.questions_tab = QuestionsTab(client)
            self.tabs.addTab(self.settings_tab, "Настройки сайта")
            self.tabs.addTab(self.questions_tab, "Вопросы теста")

        layout.addWidget(self.tabs)
        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(f"Подключено: {client.base_url}")

        self.dashboard_tab.refresh()

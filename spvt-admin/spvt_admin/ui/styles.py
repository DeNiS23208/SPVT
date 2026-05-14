APP_STYLESHEET = """
QWidget {
    background-color: #0f172a;
    color: #f8fafc;
    font-family: -apple-system, "SF Pro Text", "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #0b1220;
}

QDialog {
    background-color: #0f172a;
}

QLabel#title {
    font-size: 22px;
    font-weight: 600;
}

QLabel#subtitle {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#statValue {
    font-size: 24px;
    font-weight: 700;
    color: #38bdf8;
}

QLabel#statLabel {
    color: #94a3b8;
    font-size: 11px;
}

QLineEdit, QDateEdit, QComboBox {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 8px 10px;
    color: #f8fafc;
    min-height: 20px;
}

QLineEdit:focus, QDateEdit:focus, QComboBox:focus {
    border-color: #38bdf8;
}

QPushButton {
    background-color: #334155;
    border: none;
    border-radius: 8px;
    padding: 9px 16px;
    color: #f8fafc;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #475569;
}

QPushButton:pressed {
    background-color: #1e293b;
}

QPushButton#primary {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #38bdf8, stop:1 #0ea5e9);
    color: #0b1220;
}

QPushButton#primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #7dd3fc, stop:1 #38bdf8);
}

QPushButton#success {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #4ade80, stop:1 #22c55e);
    color: #052e16;
}

QPushButton#danger {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #f87171, stop:1 #ef4444);
    color: #450a0a;
}

QFrame#card, QFrame#statCard {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
}

QTableWidget {
    background-color: #1e293b;
    alternate-background-color: #172033;
    border: 1px solid #334155;
    border-radius: 10px;
    gridline-color: #334155;
    selection-background-color: rgba(56, 189, 248, 0.25);
    selection-color: #f8fafc;
}

QHeaderView::section {
    background-color: #0b1220;
    color: #94a3b8;
    padding: 8px;
    border: none;
    border-bottom: 1px solid #334155;
    font-weight: 600;
}

QStatusBar {
    background-color: #0b1220;
    color: #94a3b8;
    border-top: 1px solid #334155;
}

QToolBar {
    background-color: #0b1220;
    border-bottom: 1px solid #334155;
    spacing: 8px;
    padding: 8px;
}

QMessageBox {
    background-color: #1e293b;
}
"""

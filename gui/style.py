"""Reusable style definitions for the MangaPark GUI."""
from PyQt6.QtGui import QColor, QPalette

APP_STYLE = """
QWidget {
    background-color: #0f111a;
    color: #f5f7ff;
    font-family: 'Segoe UI';
    font-size: 14px;
}
QLineEdit, QTextEdit, QListWidget, QComboBox, QSpinBox {
    background-color: #151826;
    border: 1px solid #2a2f42;
    border-radius: 10px;
    padding: 8px 12px;
    selection-background-color: #5468ff;
    selection-color: #ffffff;
}
QLineEdit:focus, QTextEdit:focus, QListWidget:focus, QComboBox:focus, QSpinBox:focus {
    border: 1px solid #7183ff;
}
QPushButton {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #4f8bff, stop:1 #8a6bff);
    border: none;
    border-radius: 12px;
    padding: 10px 18px;
    font-weight: 600;
    color: #ffffff;
}
QPushButton:hover {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #6c9dff, stop:1 #a57cff);
}
QPushButton:pressed {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #3d6fe3, stop:1 #7d57f2);
}
QProgressBar {
    background-color: #141726;
    border: 1px solid #242a3d;
    border-radius: 10px;
    text-align: center;
    height: 18px;
}
QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #50b5ff, stop:1 #7a6bff);
    border-radius: 10px;
}
QScrollBar:vertical, QScrollBar:horizontal {
    background: #141726;
    border-radius: 6px;
    padding: 4px;
}
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: #2d3550;
    border-radius: 6px;
}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
    background: #3b4668;
}
QListWidget::item {
    padding: 10px;
    margin: 4px 6px;
    border-radius: 8px;
}
QListWidget::item:selected {
    background: rgba(111, 135, 255, 0.35);
}
QLabel#TitleLabel {
    font-size: 24px;
    font-weight: 700;
    color: #ffffff;
}
QFrame#Card {
    background-color: rgba(21, 24, 38, 0.85);
    border: 1px solid rgba(84, 105, 255, 0.18);
    border-radius: 18px;
    padding: 18px;
}
QLabel#SectionLabel {
    font-size: 13px;
    font-weight: 600;
    color: #c3c8e0;
    background-color: #1a1e2d;
    border: 1px solid #2a2f42;
    border-radius: 9px;
    padding: 8px 12px;
    margin-right: 8px;
    min-width: 120px;
}
"""

def apply_palette(app):
    """Tweak the base palette so dialogs inherit the dark theme."""
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#0f111a"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#151826"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#1a1e2d"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#f5f7ff"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#4f5dff"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#5468ff"))
    app.setPalette(palette)

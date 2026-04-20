"""Dark trading terminal theme QSS."""

DARK_STYLE = """
QMainWindow, QWidget {
    background-color: #1a1a2e;
    color: #e0e0e0;
    font-family: 'Segoe UI', 'Arial', sans-serif;
    font-size: 13px;
}

QTabWidget::pane {
    border: 1px solid #2a2a4a;
    background-color: #16213e;
    border-radius: 4px;
}

QTabBar::tab {
    background-color: #16213e;
    color: #8888aa;
    padding: 8px 20px;
    margin-right: 2px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}

QTabBar::tab:selected {
    background-color: #0d47a1;
    color: #ffffff;
}

QTabBar::tab:hover:!selected {
    background-color: #1a237e;
    color: #cccccc;
}

QLabel {
    color: #e0e0e0;
}

QLineEdit, QSpinBox, QComboBox {
    background-color: #0f3460;
    color: #e0e0e0;
    border: 1px solid #2a2a4a;
    border-radius: 4px;
    padding: 6px 10px;
    min-height: 20px;
}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #0d47a1;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #0f3460;
    color: #e0e0e0;
    selection-background-color: #0d47a1;
}

QPushButton {
    background-color: #0d47a1;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 8px 20px;
    font-weight: bold;
    min-height: 20px;
}

QPushButton:hover {
    background-color: #1565c0;
}

QPushButton:pressed {
    background-color: #0a3a8a;
}

QPushButton:disabled {
    background-color: #333355;
    color: #666688;
}

QPushButton#btn_stop {
    background-color: #b71c1c;
}

QPushButton#btn_stop:hover {
    background-color: #d32f2f;
}

QPushButton#btn_dryrun {
    background-color: #1b5e20;
}

QPushButton#btn_dryrun:hover {
    background-color: #2e7d32;
}

QPushButton#btn_save {
    background-color: #e65100;
}

QPushButton#btn_save:hover {
    background-color: #f57c00;
}

QSlider::groove:horizontal {
    background: #2a2a4a;
    height: 6px;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #0d47a1;
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}

QSlider::sub-page:horizontal {
    background: #1565c0;
    border-radius: 3px;
}

QProgressBar {
    background-color: #2a2a4a;
    border: none;
    border-radius: 4px;
    text-align: center;
    color: #ffffff;
    min-height: 18px;
}

QProgressBar::chunk {
    background-color: #0d47a1;
    border-radius: 4px;
}

QTableWidget {
    background-color: #16213e;
    color: #e0e0e0;
    gridline-color: #2a2a4a;
    border: 1px solid #2a2a4a;
    border-radius: 4px;
}

QTableWidget::item {
    padding: 4px 8px;
}

QTableWidget::item:selected {
    background-color: #0d47a1;
}

QHeaderView::section {
    background-color: #1a237e;
    color: #e0e0e0;
    padding: 6px;
    border: 1px solid #2a2a4a;
    font-weight: bold;
}

QPlainTextEdit {
    background-color: #0a0a1a;
    color: #e0e0e0;
    border: 1px solid #2a2a4a;
    border-radius: 4px;
    font-family: 'Consolas', 'Courier New', monospace;
    font-size: 12px;
}

QCheckBox {
    color: #e0e0e0;
    spacing: 6px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #2a2a4a;
    border-radius: 3px;
    background-color: #0f3460;
}

QCheckBox::indicator:checked {
    background-color: #0d47a1;
}

QStatusBar {
    background-color: #0a0a1a;
    color: #8888aa;
    border-top: 1px solid #2a2a4a;
}

QGroupBox {
    border: 1px solid #2a2a4a;
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: bold;
    color: #8888aa;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
"""

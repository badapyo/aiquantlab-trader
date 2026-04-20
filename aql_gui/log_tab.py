"""Log viewer tab — real-time trading log display."""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QPushButton, QCheckBox, QLineEdit, QLabel,
)
from PyQt6.QtGui import QTextCharFormat, QColor, QTextCursor


LEVEL_COLORS = {
    'ERROR': '#ff1744',
    'WARNING': '#ffab00',
    'INFO': '#e0e0e0',
    'DEBUG': '#666688',
}


class LogTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        # Toolbar
        toolbar = QHBoxLayout()
        self.cb_autoscroll = QCheckBox("Auto-scroll")
        self.cb_autoscroll.setChecked(True)
        toolbar.addWidget(self.cb_autoscroll)

        toolbar.addWidget(QLabel("Filter:"))
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filter logs...")
        self.filter_input.setMaximumWidth(200)
        toolbar.addWidget(self.filter_input)

        toolbar.addStretch()

        btn_clear = QPushButton("Clear")
        btn_clear.setMaximumWidth(80)
        btn_clear.clicked.connect(self.clear_logs)
        toolbar.addWidget(btn_clear)

        layout.addLayout(toolbar)

        # Log text area
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setMaximumBlockCount(5000)
        layout.addWidget(self.text)

    def append_message(self, msg: str, level: str):
        """Append a log message with color based on level."""
        filter_text = self.filter_input.text()
        if filter_text and filter_text.lower() not in msg.lower():
            return

        fmt = QTextCharFormat()
        color = LEVEL_COLORS.get(level, '#e0e0e0')
        fmt.setForeground(QColor(color))

        cursor = self.text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(msg + '\n', fmt)

        if self.cb_autoscroll.isChecked():
            self.text.setTextCursor(cursor)
            self.text.ensureCursorVisible()

    def clear_logs(self):
        self.text.clear()

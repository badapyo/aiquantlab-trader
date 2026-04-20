"""Logging handler that bridges Python logging → Qt signal for GUI display."""
import logging
from PyQt6.QtCore import QObject, pyqtSignal


class LogSignal(QObject):
    message = pyqtSignal(str, str)  # formatted text, level name


class QtLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.signal_obj = LogSignal()
        self.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

    def emit(self, record):
        msg = self.format(record)
        self.signal_obj.message.emit(msg, record.levelname)

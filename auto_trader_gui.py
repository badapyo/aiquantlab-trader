#!/usr/bin/env python3
"""AIQuantLab Auto Trader — Desktop GUI Launcher"""
import os, sys

# High-DPI scaling
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

from PyQt6.QtWidgets import QApplication
from aql_gui.main_window import MainWindow
from aql_gui.styles import DARK_STYLE


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("AIQuantLab Auto Trader")
    app.setStyleSheet(DARK_STYLE)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()

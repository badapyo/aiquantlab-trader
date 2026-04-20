"""Main window — tabs, status bar, Start/Stop/Dry Run, system tray."""
import sys, os, logging

from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QWidget, QHBoxLayout, QVBoxLayout,
    QPushButton, QCheckBox, QLabel, QMessageBox, QStatusBar,
    QSystemTrayIcon, QMenu,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap, QAction

from .setup_tab import SetupTab
from .dashboard_tab import DashboardTab
from .log_tab import LogTab
from .log_handler import QtLogHandler
from .threads import TradingThread, HeartbeatThread

# Remove auto_trader's StreamHandler so logs don't go to hidden console
_at_logger = logging.getLogger('auto_trader')
for h in _at_logger.handlers[:]:
    if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
        _at_logger.removeHandler(h)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AIQuantLab Auto Trader")
        self.setMinimumSize(720, 600)
        self.resize(820, 700)

        self.trading_thread = None
        self.heartbeat_thread = None

        self._build_ui()
        self._setup_log_handler()
        self._setup_tray()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Tabs
        self.tabs = QTabWidget()
        self.setup_tab = SetupTab()
        self.dashboard_tab = DashboardTab()
        self.log_tab = LogTab()

        self.tabs.addTab(self.setup_tab, "Setup")
        self.tabs.addTab(self.dashboard_tab, "Dashboard")
        self.tabs.addTab(self.log_tab, "Logs")

        layout.addWidget(self.tabs)

        # Bottom control bar
        bottom = QWidget()
        bottom.setFixedHeight(52)
        bottom.setStyleSheet("background-color: #0a0a1a; border-top: 1px solid #2a2a4a;")
        bottom_layout = QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(12, 4, 12, 4)

        self.lbl_status = QLabel("Idle")
        self.lbl_status.setStyleSheet("color: #8888aa; font-size: 13px;")
        bottom_layout.addWidget(self.lbl_status)

        bottom_layout.addStretch()

        self.cb_testnet = QCheckBox("Testnet")
        self.cb_testnet.setStyleSheet("color: #ffab00;")
        bottom_layout.addWidget(self.cb_testnet)

        self.btn_dryrun = QPushButton("Dry Run")
        self.btn_dryrun.setObjectName("btn_dryrun")
        self.btn_dryrun.setFixedWidth(100)
        self.btn_dryrun.clicked.connect(self._on_dryrun)
        bottom_layout.addWidget(self.btn_dryrun)

        self.btn_force = QPushButton("Force Rebal")
        self.btn_force.setObjectName("btn_force")
        self.btn_force.setFixedWidth(110)
        self.btn_force.setToolTip("Re-align all positions to current account balance.\nUse after deposit/withdrawal.")
        self.btn_force.clicked.connect(self._on_force_rebal)
        bottom_layout.addWidget(self.btn_force)

        self.btn_start = QPushButton("Start")
        self.btn_start.setFixedWidth(100)
        self.btn_start.clicked.connect(self._on_start_stop)
        bottom_layout.addWidget(self.btn_start)

        layout.addWidget(bottom)

    def _setup_log_handler(self):
        self.qt_log_handler = QtLogHandler()
        logging.getLogger('auto_trader').addHandler(self.qt_log_handler)
        self.qt_log_handler.signal_obj.message.connect(self.log_tab.append_message)

    def _setup_tray(self):
        # Create a simple icon programmatically
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        from PyQt6.QtGui import QPainter, QBrush
        painter = QPainter(pixmap)
        painter.setBrush(QBrush(Qt.GlobalColor.cyan))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 28, 28)
        painter.end()

        icon = QIcon(pixmap)
        self.setWindowIcon(icon)

        self.tray = QSystemTrayIcon(icon, self)
        menu = QMenu()

        show_action = QAction("Show", self)
        show_action.triggered.connect(self._show_and_raise)
        menu.addAction(show_action)

        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_click)
        self.tray.show()

    # ── Start / Stop ──

    def _is_running(self):
        return self.trading_thread is not None and self.trading_thread.isRunning()

    def _on_start_stop(self):
        if self._is_running():
            self._stop_trading()
        else:
            self._start_trading(dry=False)

    def _on_dryrun(self):
        if self._is_running():
            return
        self._start_trading(dry=True)

    def _on_force_rebal(self):
        if self._is_running():
            return
        reply = QMessageBox.question(
            self, "Force Rebalance",
            "Realign ALL positions to your current account balance?\n\n"
            "Use this after a deposit or withdrawal so allocation matches your new capital.\n"
            "This will place real orders.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._start_trading(dry=False, force=True)

    def _start_trading(self, dry=False, force=False):
        err = self.setup_tab.validate()
        if err:
            QMessageBox.warning(self, "Validation Error", err)
            return

        config = self.setup_tab.get_config()
        config['dry'] = dry
        config['force'] = force
        config['testnet'] = self.cb_testnet.isChecked()

        self.dashboard_tab.reset()
        self.tabs.setCurrentWidget(self.dashboard_tab)

        self.trading_thread = TradingThread(config)
        sigs = self.trading_thread.signals

        sigs.status_changed.connect(self._on_status)
        sigs.auth_result.connect(self._on_auth)
        sigs.session_ready.connect(self._on_session)
        sigs.signals_received.connect(self.dashboard_tab.update_signals)
        sigs.positions_updated.connect(self.dashboard_tab.update_positions)
        sigs.targets_computed.connect(self.dashboard_tab.update_targets)
        sigs.fill_progress.connect(self.dashboard_tab.update_fill_progress)
        sigs.trade_result.connect(self.dashboard_tab.update_result)
        sigs.run_complete.connect(self._on_complete)
        sigs.error_occurred.connect(self._on_error)

        self.trading_thread.start()

        mode = "DRY RUN" if dry else ("FORCE REBAL" if force else "LIVE")
        self._set_running_ui(True, mode)

    def _stop_trading(self):
        if self.trading_thread:
            self.trading_thread.stop()
        self.btn_start.setText("Stopping...")
        self.btn_start.setEnabled(False)

    def _set_running_ui(self, running, mode=""):
        if running:
            self.btn_start.setText("Stop")
            self.btn_start.setObjectName("btn_stop")
            self.btn_start.setStyle(self.btn_start.style())  # force re-apply QSS
            self.btn_dryrun.setEnabled(False)
            self.btn_force.setEnabled(False)
            self.setup_tab.setEnabled(False)
            self.cb_testnet.setEnabled(False)
            self.lbl_status.setText(f"{mode} Running...")
        else:
            self.btn_start.setText("Start")
            self.btn_start.setObjectName("")
            self.btn_start.setStyle(self.btn_start.style())
            self.btn_start.setEnabled(True)
            self.btn_dryrun.setEnabled(True)
            self.btn_force.setEnabled(True)
            self.setup_tab.setEnabled(True)
            self.cb_testnet.setEnabled(True)

    # ── Callbacks ──

    def _on_status(self, status):
        self.lbl_status.setText(status)

    def _on_auth(self, ok, msg):
        if not ok:
            QMessageBox.critical(self, "Auth Failed", msg)

    def _on_session(self, session):
        self.heartbeat_thread = HeartbeatThread(session)
        self.heartbeat_thread.start()

    def _on_complete(self, results):
        if self.heartbeat_thread:
            self.heartbeat_thread.stop()
            self.heartbeat_thread.wait(3000)
            self.heartbeat_thread = None

        self.dashboard_tab.show_results_summary(results)
        self._set_running_ui(False)
        self.lbl_status.setText("Idle")

        if results:
            self.tray.showMessage(
                "AIQuantLab",
                f"Trading complete: {sum(1 for r in results if r.get('ok'))} success",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )

    def _on_error(self, error):
        self.lbl_status.setText(f"Error: {error}")

    # ── Tray ──

    def _show_and_raise(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _on_tray_click(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._show_and_raise()

    def _quit_app(self):
        if self._is_running():
            reply = QMessageBox.question(
                self, "Quit",
                "Trading is in progress. Are you sure you want to quit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            self._stop_trading()
            if self.trading_thread:
                self.trading_thread.wait(5000)

        self.tray.hide()
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()

    def closeEvent(self, event):
        if self._is_running():
            event.ignore()
            self.hide()
            self.tray.showMessage(
                "AIQuantLab",
                "Trading continues in background. Right-click tray to quit.",
                QSystemTrayIcon.MessageIcon.Information,
                3000,
            )
        else:
            self.tray.hide()
            event.accept()

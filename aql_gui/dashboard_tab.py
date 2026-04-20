"""Dashboard tab — positions table, signals, fill progress."""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QProgressBar,
    QGroupBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor

COINS = ['BTC', 'ETH', 'SOL', 'DOGE', 'XRP', 'TRX', 'ADA', 'BCH', 'LINK', 'BNB']
COL_HEADERS = ['Coin', 'Signal', 'Side', 'Notional', 'Status']

COLOR_LONG = QColor('#00c853')
COLOR_SHORT = QColor('#ff1744')
COLOR_FLAT = QColor('#666688')
COLOR_DEFAULT = QColor('#e0e0e0')


class DashboardTab(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Info bar
        info_row = QHBoxLayout()
        self.lbl_signal_date = QLabel("Signal Date: --")
        self.lbl_signal_date.setStyleSheet("font-size: 14px; font-weight: bold;")
        info_row.addWidget(self.lbl_signal_date)

        info_row.addStretch()

        self.lbl_equity = QLabel("Equity: --")
        self.lbl_equity.setStyleSheet("font-size: 14px; font-weight: bold; color: #00c853;")
        info_row.addWidget(self.lbl_equity)

        self.lbl_available = QLabel("Available: --")
        self.lbl_available.setStyleSheet("font-size: 14px; color: #8888aa;")
        info_row.addWidget(self.lbl_available)

        layout.addLayout(info_row)

        # Positions table
        self.table = QTableWidget(len(COINS), len(COL_HEADERS))
        self.table.setHorizontalHeaderLabels(COL_HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 60)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(2, 70)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        # Initialize rows
        for i, coin in enumerate(COINS):
            item = QTableWidgetItem(coin)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 0, item)
            for j in range(1, len(COL_HEADERS)):
                item = QTableWidgetItem("--")
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(i, j, item)

        layout.addWidget(self.table)

        # Fill progress section
        progress_group = QGroupBox("Fill Progress")
        progress_layout = QVBoxLayout(progress_group)

        self.lbl_fill_coin = QLabel("Waiting...")
        self.lbl_fill_coin.setStyleSheet("font-size: 13px;")
        progress_layout.addWidget(self.lbl_fill_coin)

        self.fill_bar = QProgressBar()
        self.fill_bar.setRange(0, 100)
        self.fill_bar.setValue(0)
        progress_layout.addWidget(self.fill_bar)

        layout.addWidget(progress_group)

        # Results summary
        self.lbl_results = QLabel("")
        self.lbl_results.setStyleSheet("font-size: 13px; color: #8888aa;")
        layout.addWidget(self.lbl_results)

    def update_signals(self, signals: dict, date: str):
        self.lbl_signal_date.setText(f"Signal Date: {date}")
        for i, coin in enumerate(COINS):
            if coin in signals:
                sig = signals[coin]
                nr = sig['net_ratio']

                # Signal column
                if nr > 0:
                    text = f"LONG {abs(nr)*100:.0f}%"
                    color = COLOR_LONG
                elif nr < 0:
                    text = f"SHORT {abs(nr)*100:.0f}%"
                    color = COLOR_SHORT
                else:
                    text = "FLAT"
                    color = COLOR_FLAT

                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                item.setForeground(color)
                self.table.setItem(i, 1, item)
            else:
                self._set_cell(i, 1, "--")

    def update_positions(self, positions: dict, equity: float, available: float):
        self.lbl_equity.setText(f"Equity: ${equity:,.2f}")
        self.lbl_available.setText(f"Available: ${available:,.2f}")

        for i, coin in enumerate(COINS):
            if coin in positions:
                pos = positions[coin]
                side = pos['side'].upper()
                color = COLOR_LONG if pos['side'] == 'long' else COLOR_SHORT
                notional = f"${pos['notional']:,.1f}"

                side_item = QTableWidgetItem(side)
                side_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                side_item.setForeground(color)
                self.table.setItem(i, 2, side_item)

                not_item = QTableWidgetItem(notional)
                not_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(i, 3, not_item)
            else:
                self._set_cell(i, 2, "--")
                self._set_cell(i, 3, "--")

    def update_targets(self, targets: dict):
        for i, coin in enumerate(COINS):
            if coin in targets:
                t = targets[coin]
                if t['side']:
                    side = 'LONG' if t['side'] == 'buy' else 'SHORT'
                    color = COLOR_LONG if t['side'] == 'buy' else COLOR_SHORT
                    text = f"{side} ${t['notional']:,.0f}"

                    side_item = QTableWidgetItem(side)
                    side_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    side_item.setForeground(color)
                    self.table.setItem(i, 2, side_item)

                    not_item = QTableWidgetItem(f"${t['notional']:,.0f}")
                    not_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    self.table.setItem(i, 3, not_item)

                    self._set_cell(i, 4, "Target")
                else:
                    self._set_cell(i, 2, "FLAT")
                    self._set_cell(i, 3, "--")
                    self._set_cell(i, 4, "FLAT")

    def update_fill_progress(self, coin: str, filled: float, total: float, round_num: int):
        pct = int((filled / total * 100)) if total > 0 else 0
        self.lbl_fill_coin.setText(f"{coin}  |  Round {round_num}  |  {filled:.6f} / {total:.6f}")
        self.fill_bar.setValue(pct)

        # Update table status
        row = COINS.index(coin) if coin in COINS else -1
        if row >= 0:
            self._set_cell(row, 4, f"Filling R{round_num} ({pct}%)")

    def update_result(self, result: dict):
        coin = result.get('coin', '')
        row = COINS.index(coin) if coin in COINS else -1
        if row >= 0:
            ok = result.get('ok', False)
            action = result.get('action', '')
            color = COLOR_LONG if ok else COLOR_SHORT
            item = QTableWidgetItem(action)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setForeground(color)
            self.table.setItem(row, 4, item)

    def show_results_summary(self, results: list):
        if not results:
            return
        ok = sum(1 for r in results if r.get('ok'))
        fail = sum(1 for r in results if not r.get('ok'))
        self.lbl_results.setText(f"Results: {ok} success, {fail} failed")
        self.lbl_fill_coin.setText("Complete")
        self.fill_bar.setValue(100)

    def reset(self):
        self.lbl_signal_date.setText("Signal Date: --")
        self.lbl_equity.setText("Equity: --")
        self.lbl_available.setText("Available: --")
        self.lbl_results.setText("")
        self.lbl_fill_coin.setText("Waiting...")
        self.fill_bar.setValue(0)
        for i in range(len(COINS)):
            for j in range(1, len(COL_HEADERS)):
                self._set_cell(i, j, "--")

    def _set_cell(self, row, col, text):
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        item.setForeground(COLOR_DEFAULT)
        self.table.setItem(row, col, item)

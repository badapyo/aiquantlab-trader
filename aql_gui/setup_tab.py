"""Setup tab — token, exchange, API keys, leverage, coin allocation."""
import sys, os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QComboBox, QSpinBox, QSlider, QPushButton,
    QProgressBar, QMessageBox, QScrollArea,
)
from PyQt6.QtCore import Qt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import auto_trader

COINS = ['BTC', 'ETH', 'SOL', 'DOGE', 'XRP', 'TRX', 'ADA', 'BCH', 'LINK', 'BNB']


class NoWheelSpinBox(QSpinBox):
    """QSpinBox that ignores mouse wheel — prevents accidental value changes while scrolling."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event):
        event.ignore()


class NoWheelSlider(QSlider):
    """QSlider that ignores mouse wheel unless focused."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def wheelEvent(self, event):
        if self.hasFocus():
            super().wheelEvent(event)
        else:
            event.ignore()


class SetupTab(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()
        self._load_config()

    def _build_ui(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # === Connection Group ===
        conn_group = QGroupBox("Connection")
        conn_form = QFormLayout(conn_group)
        conn_form.setSpacing(8)

        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("Subscription token")
        self.token_input.setEchoMode(QLineEdit.EchoMode.Password)
        conn_form.addRow("Token:", self.token_input)

        layout.addWidget(conn_group)

        # === Exchange Group ===
        ex_group = QGroupBox("Exchange")
        ex_form = QFormLayout(ex_group)
        ex_form.setSpacing(8)

        self.exchange_combo = QComboBox()
        self.exchange_combo.addItems(['bybit', 'bitget', 'binance', 'coinbase'])
        self.exchange_combo.currentTextChanged.connect(self._on_exchange_changed)
        ex_form.addRow("Exchange:", self.exchange_combo)

        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("API Key")
        ex_form.addRow("API Key:", self.api_key_input)

        self.api_secret_input = QLineEdit()
        self.api_secret_input.setPlaceholderText("API Secret")
        self.api_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        ex_form.addRow("API Secret:", self.api_secret_input)

        self.passphrase_label = QLabel("Passphrase:")
        self.passphrase_input = QLineEdit()
        self.passphrase_input.setPlaceholderText("Bitget passphrase")
        self.passphrase_input.setEchoMode(QLineEdit.EchoMode.Password)
        ex_form.addRow(self.passphrase_label, self.passphrase_input)
        self.passphrase_label.setVisible(False)
        self.passphrase_input.setVisible(False)

        self.leverage_spin = NoWheelSpinBox()
        self.leverage_spin.setRange(1, 10)
        self.leverage_spin.setValue(3)
        ex_form.addRow("Leverage:", self.leverage_spin)

        layout.addWidget(ex_group)

        # === Coin Allocation Group ===
        alloc_group = QGroupBox("Coin Allocation (%)")
        alloc_layout = QVBoxLayout(alloc_group)
        alloc_layout.setSpacing(6)

        self.coin_sliders = {}
        self.coin_spins = {}

        for coin in COINS:
            row = QHBoxLayout()
            label = QLabel(f"{coin}")
            label.setFixedWidth(45)
            label.setStyleSheet("font-weight: bold;")
            row.addWidget(label)

            slider = NoWheelSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 50)
            slider.setValue(10)
            row.addWidget(slider)

            spin = NoWheelSpinBox()
            spin.setRange(0, 50)
            spin.setValue(10)
            spin.setSuffix("%")
            spin.setFixedWidth(90)
            row.addWidget(spin)

            # Sync slider <-> spin
            slider.valueChanged.connect(spin.setValue)
            spin.valueChanged.connect(slider.setValue)
            slider.valueChanged.connect(self._update_total)

            self.coin_sliders[coin] = slider
            self.coin_spins[coin] = spin
            alloc_layout.addLayout(row)

        # Total bar
        total_row = QHBoxLayout()
        total_row.addWidget(QLabel("Total:"))
        self.total_bar = QProgressBar()
        self.total_bar.setRange(0, 100)
        self.total_bar.setValue(100)
        self.total_label = QLabel("100%")
        self.total_label.setFixedWidth(50)
        total_row.addWidget(self.total_bar)
        total_row.addWidget(self.total_label)
        alloc_layout.addLayout(total_row)

        layout.addWidget(alloc_group)

        # === Buttons ===
        btn_row = QHBoxLayout()
        btn_save = QPushButton("Save Config")
        btn_save.setObjectName("btn_save")
        btn_save.clicked.connect(self._save_config)
        btn_row.addWidget(btn_save)

        btn_load = QPushButton("Reload Config")
        btn_load.clicked.connect(self._load_config)
        btn_row.addWidget(btn_load)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        layout.addStretch()

        scroll.setWidget(container)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def _on_exchange_changed(self, exchange):
        is_bitget = exchange == 'bitget'
        self.passphrase_label.setVisible(is_bitget)
        self.passphrase_input.setVisible(is_bitget)

    def _update_total(self):
        total = sum(s.value() for s in self.coin_sliders.values())
        self.total_bar.setValue(min(total, 100))
        self.total_label.setText(f"{total}%")
        if total > 100:
            self.total_bar.setStyleSheet("QProgressBar::chunk { background-color: #ff1744; }")
            self.total_label.setStyleSheet("color: #ff1744; font-weight: bold;")
        else:
            self.total_bar.setStyleSheet("")
            self.total_label.setStyleSheet("")

    def _load_config(self):
        cfg = auto_trader.load_config()
        if not cfg:
            return

        self.token_input.setText(cfg.get('token', ''))

        ex = cfg.get('exchange', 'bybit')
        idx = self.exchange_combo.findText(ex)
        if idx >= 0:
            self.exchange_combo.setCurrentIndex(idx)

        self.api_key_input.setText(cfg.get('api_key', ''))
        self.api_secret_input.setText(cfg.get('api_secret', ''))
        self.passphrase_input.setText(cfg.get('passphrase', ''))
        self.leverage_spin.setValue(cfg.get('leverage', 3))

        alloc = cfg.get('allocation', {})
        for coin in COINS:
            val = alloc.get(coin, 10)
            self.coin_sliders[coin].setValue(val)

    def _save_config(self):
        total = sum(s.value() for s in self.coin_sliders.values())
        if total > 100:
            QMessageBox.warning(self, "Error", f"Total allocation is {total}%. Must be 100% or less.")
            return

        cfg = {
            'token': self.token_input.text().strip(),
            'exchange': self.exchange_combo.currentText(),
            'api_key': self.api_key_input.text().strip(),
            'api_secret': self.api_secret_input.text().strip(),
            'leverage': self.leverage_spin.value(),
            'allocation': {coin: s.value() for coin, s in self.coin_sliders.items()},
        }

        if self.exchange_combo.currentText() == 'bitget':
            cfg['passphrase'] = self.passphrase_input.text().strip()

        auto_trader.save_config(cfg)
        QMessageBox.information(self, "Saved", f"Config saved to {auto_trader.CONFIG_PATH}")

    def get_config(self) -> dict:
        """Return current config from UI widgets."""
        cfg = {
            'token': self.token_input.text().strip(),
            'exchange': self.exchange_combo.currentText(),
            'api_key': self.api_key_input.text().strip(),
            'api_secret': self.api_secret_input.text().strip(),
            'leverage': self.leverage_spin.value(),
            'allocation': {coin: s.value() for coin, s in self.coin_sliders.items()},
        }
        if self.exchange_combo.currentText() == 'bitget':
            cfg['passphrase'] = self.passphrase_input.text().strip()
        return cfg

    def validate(self) -> str | None:
        """Return error message or None if valid."""
        if not self.token_input.text().strip():
            return "Token is required."
        if not self.api_key_input.text().strip():
            return "API Key is required."
        if not self.api_secret_input.text().strip():
            return "API Secret is required."
        if self.exchange_combo.currentText() == 'bitget' and not self.passphrase_input.text().strip():
            return "Passphrase is required for Bitget."
        total = sum(s.value() for s in self.coin_sliders.values())
        if total > 100:
            return f"Total allocation is {total}%. Must be 100% or less."
        if total == 0:
            return "At least one coin must have allocation > 0%."
        return None

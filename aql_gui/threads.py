"""Background threads for trading execution and heartbeat."""
import sys, os, threading, time, traceback

from PyQt6.QtCore import QThread, QObject, pyqtSignal

# Add parent dir to path so auto_trader can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import auto_trader


class TradingSignals(QObject):
    status_changed = pyqtSignal(str)
    auth_result = pyqtSignal(bool, str)
    session_ready = pyqtSignal(object)  # ServerSession
    signals_received = pyqtSignal(dict, str)  # signals, date
    positions_updated = pyqtSignal(dict, float, float)  # positions, equity, available
    targets_computed = pyqtSignal(dict)
    fill_progress = pyqtSignal(str, float, float, int)  # coin, filled, total, round
    trade_result = pyqtSignal(dict)
    run_complete = pyqtSignal(list)
    error_occurred = pyqtSignal(str)


class TradingThread(QThread):
    def __init__(self, config: dict):
        super().__init__()
        self.config = config
        self._stop_event = threading.Event()
        self.signals = TradingSignals()

    def run(self):
        callbacks = {
            'should_stop': self._stop_event.is_set,
            'on_status': lambda s: self.signals.status_changed.emit(s),
            'on_auth': lambda ok, msg: self.signals.auth_result.emit(ok, msg),
            'on_session': lambda s: self.signals.session_ready.emit(s),
            'on_signals': lambda s, d: self.signals.signals_received.emit(s, d),
            'on_positions': lambda p, e, a: self.signals.positions_updated.emit(p, e, a),
            'on_targets': lambda t: self.signals.targets_computed.emit(t),
            'on_fill_progress': lambda *a: self.signals.fill_progress.emit(*a),
            'on_result': lambda r: self.signals.trade_result.emit(r),
            'on_complete': lambda r: self.signals.run_complete.emit(r),
            'on_error': lambda e: self.signals.error_occurred.emit(e),
        }
        try:
            auto_trader.run(
                token=self.config['token'],
                exchange_name=self.config['exchange'],
                api_key=self.config['api_key'],
                api_secret=self.config['api_secret'],
                passphrase=self.config.get('passphrase'),
                leverage=self.config.get('leverage', 3),
                dry=self.config.get('dry', False),
                testnet=self.config.get('testnet', False),
                allocation=self.config.get('allocation'),
                callbacks=callbacks,
                force=self.config.get('force', False),
            )
        except Exception as e:
            self.signals.error_occurred.emit(str(e))
            traceback.print_exc()
        finally:
            self.signals.status_changed.emit('Idle')
            self.signals.run_complete.emit([])

    def stop(self):
        self._stop_event.set()


class HeartbeatThread(QThread):
    def __init__(self, session):
        super().__init__()
        self.session = session
        self._stop_event = threading.Event()

    def run(self):
        while not self._stop_event.is_set():
            try:
                self.session.heartbeat()
            except Exception:
                pass
            self._stop_event.wait(auto_trader.HEARTBEAT_SEC)

    def stop(self):
        self._stop_event.set()

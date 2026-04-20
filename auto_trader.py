"""
AIQuantLab Auto Trader Client
Receive signals from server → local auto-trading on Bybit/Bitget/Binance/Coinbase
Security: HMAC + JWT + HWID binding + AES encrypted signals

Usage: python auto_trader.py --token <TOKEN> --exchange bybit [--leverage 3] [--dry]
"""
import os, sys, time, json, math, logging, argparse, atexit, signal as sig_module
import hashlib, hmac as hmac_mod, base64, platform, uuid
from datetime import datetime, timezone

import ccxt
import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ══════════════════════════════════════════
# Config
# ══════════════════════════════════════════
SERVER_URL = "https://aiquantlab.io"
CONFIG_PATH = os.path.expanduser("~/.aiquantlab/config.json")
LOG_PATH = os.path.expanduser("~/.aiquantlab/trader.log")
STATE_PATH = os.path.expanduser("~/.aiquantlab/state.json")

ALLOC_PER_COIN = 0.10
FILL_CHECK_SEC = 5
HEARTBEAT_SEC = 120

# Order modes: 'market' | '1m_refill' | 'daily_limit'
DEFAULT_ENTRY_MODE = '1m_refill'
DEFAULT_CLOSE_MODE = '1m_refill'
MAX_1M_ROUNDS = 300
DAILY_LIMIT_DEADLINE = 23

COIN_SYMBOLS = {
    'BTC':  {'bybit': 'BTC/USDT:USDT',  'bitget': 'BTC/USDT:USDT',  'binance': 'BTC/USDT:USDT',  'coinbase': 'BTC/USDT'},
    'ETH':  {'bybit': 'ETH/USDT:USDT',  'bitget': 'ETH/USDT:USDT',  'binance': 'ETH/USDT:USDT',  'coinbase': 'ETH/USDT'},
    'SOL':  {'bybit': 'SOL/USDT:USDT',  'bitget': 'SOL/USDT:USDT',  'binance': 'SOL/USDT:USDT',  'coinbase': 'SOL/USDT'},
    'DOGE': {'bybit': 'DOGE/USDT:USDT', 'bitget': 'DOGE/USDT:USDT', 'binance': 'DOGE/USDT:USDT', 'coinbase': 'DOGE/USDT'},
    'XRP':  {'bybit': 'XRP/USDT:USDT',  'bitget': 'XRP/USDT:USDT',  'binance': 'XRP/USDT:USDT',  'coinbase': 'XRP/USDT'},
    'TRX':  {'bybit': 'TRX/USDT:USDT',  'bitget': 'TRX/USDT:USDT',  'binance': 'TRX/USDT:USDT',  'coinbase': 'TRX/USDT'},
    'ADA':  {'bybit': 'ADA/USDT:USDT',  'bitget': 'ADA/USDT:USDT',  'binance': 'ADA/USDT:USDT',  'coinbase': 'ADA/USDT'},
    'BCH':  {'bybit': 'BCH/USDT:USDT',  'bitget': 'BCH/USDT:USDT',  'binance': 'BCH/USDT:USDT',  'coinbase': 'BCH/USDT'},
    'LINK': {'bybit': 'LINK/USDT:USDT', 'bitget': 'LINK/USDT:USDT', 'binance': 'LINK/USDT:USDT', 'coinbase': 'LINK/USDT'},
    'BNB':  {'bybit': 'BNB/USDT:USDT',  'bitget': 'BNB/USDT:USDT',  'binance': 'BNB/USDT:USDT',  'coinbase': 'BNB/USDT'},
}

SUPPORTED_EXCHANGES = ['bybit', 'bitget', 'binance', 'coinbase']

# HMAC is dynamic:
#   - Bootstrap key (for /api/trader/auth only) is derived from the subscription
#     token the user pastes during setup, so no shared secret ships with the binary.
#   - Post-auth, the server returns a random per-session HMAC key used for
#     every subsequent request.
_BOOT_HMAC_PREFIX = b"aql_hmac_v1:"

# Log directory
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger('auto_trader')


# ══════════════════════════════════════════
# Config file (API keys)
# ══════════════════════════════════════════
def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return {}


def save_config(cfg):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, 'w') as f:
        json.dump(cfg, f, indent=2)


def setup_wizard():
    """Setup wizard — token + exchange API keys"""
    cfg = load_config()
    print("\n═══ AIQuantLab Auto Trader Setup ═══\n")

    cfg['token'] = input("Token: ").strip()
    print()

    exchange = input("Exchange (bybit/bitget/binance/coinbase): ").strip().lower()
    if exchange not in SUPPORTED_EXCHANGES:
        print(f"Unsupported exchange: {exchange}")
        sys.exit(1)
    cfg['exchange'] = exchange

    print(f"\n{exchange.upper()} Enter API keys:")
    cfg['api_key'] = input("  API Key: ").strip()
    cfg['api_secret'] = input("  API Secret: ").strip()

    if exchange == 'bitget':
        cfg['passphrase'] = input("  Passphrase: ").strip()

    leverage = input("\nLeverage (default 3): ").strip()
    cfg['leverage'] = int(leverage) if leverage else 3

    # Coin allocation
    print("\n── Coin Allocation (%) ──")
    print("Set weight per coin. Total must not exceed 100%.")
    print("Enter 0 to exclude a coin. Press Enter for default (10%).\n")

    coins = ['BTC', 'ETH', 'SOL', 'DOGE', 'XRP', 'TRX', 'ADA', 'BCH', 'LINK', 'BNB']
    alloc = {}
    total = 0
    for coin in coins:
        while True:
            val = input(f"  {coin} (default 10%): ").strip()
            if val == '':
                w = 10
            else:
                try:
                    w = int(val)
                except ValueError:
                    print("    Enter a number.")
                    continue
            if w < 0:
                print("    Cannot be negative.")
                continue
            if total + w > 100:
                print(f"    Total would be {total + w}%. Cannot exceed 100%.")
                continue
            break
        alloc[coin] = w
        total += w
        if w == 0:
            print(f"    {coin}: excluded")

    cfg['allocation'] = alloc
    print(f"\n  Total allocation: {total}%")
    if total < 100:
        print(f"  Remaining {100 - total}% will stay as cash.")

    save_config(cfg)
    print(f"\n✅ Config saved: {CONFIG_PATH}")
    return cfg


# ══════════════════════════════════════════
# Security: HWID + HMAC + AES
# ══════════════════════════════════════════
def get_hwid():
    """Device unique ID — MAC + platform hash"""
    raw = f"{uuid.getnode()}:{platform.node()}:{platform.machine()}:{platform.system()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def derive_boot_hmac(subscription_token):
    """Bootstrap HMAC key = sha256('aql_hmac_v1:' + subscription_token).
    Matches server-side derivation for /api/trader/auth."""
    return hashlib.sha256(_BOOT_HMAC_PREFIX + subscription_token.encode()).digest()


def sign_request(body_dict, hmac_key):
    """HMAC-SHA256 Add signature → insert timestamp + signature into body.
    Signing target: timestamp + ':' + body(excluding signature, sorted JSON).
    `hmac_key` is either the boot key (derived from subscription token) or the
    per-session key returned by /api/trader/auth."""
    ts = str(int(time.time()))
    body_dict['timestamp'] = ts
    # Serialize without signature field for signing
    sign_body = {k: v for k, v in body_dict.items() if k != 'signature'}
    sign_json = json.dumps(sign_body, separators=(',', ':'), sort_keys=True)
    sig = hmac_mod.new(hmac_key, f"{ts}:{sign_json}".encode(), hashlib.sha256).hexdigest()
    body_dict['signature'] = sig
    return body_dict


def decrypt_payload(encrypted_b64, aes_key_b64):
    """AES-GCM decryption"""
    aes_key = base64.b64decode(aes_key_b64)
    raw = base64.b64decode(encrypted_b64)
    nonce = raw[:12]
    ciphertext = raw[12:]
    aesgcm = AESGCM(aes_key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return json.loads(plaintext)


# ══════════════════════════════════════════
# Server communication (secured)
# ══════════════════════════════════════════
class ServerSession:
    """Server session manager — JWT auto-refresh"""

    def __init__(self, token):
        self.token = token
        self.hwid = get_hwid()
        self.access_token = None
        self.refresh_token = None
        self.aes_key = None
        self.session_hmac_key = None  # per-session key from /api/trader/auth
        self.access_expires = 0

    def auth(self):
        """Auth + JWT issue"""
        boot_key = derive_boot_hmac(self.token)
        body = sign_request({"token": self.token, "hwid": self.hwid}, boot_key)
        try:
            r = requests.post(f"{SERVER_URL}/api/trader/auth", json=body, timeout=15)
            data = r.json()
            if not data.get('ok'):
                err = data.get('error', 'unknown')
                msgs = {
                    'invalid_token': "Invalid token.",
                    'no_subscription': "No active subscription. Annual subscription required.",
                    'device_mismatch': (
                        "Already running on another device.\n\n"
                        "If you just closed it normally: try again.\n"
                        "If the previous app crashed / the PC shut down unexpectedly: "
                        "please wait about 5 minutes and try again — the server will "
                        "automatically release the old session."
                    ),
                    'invalid_signature': "Request signature error. Please reinstall.",
                    'blocked': "Too many requests. Please retry later.",
                    'rate_limited': "Rate limit exceeded. Please retry later.",
                }
                log.error(f"❌ {msgs.get(err, f'Auth failed: {err}')}")
                return False
            self.access_token = data['access_token']
            self.refresh_token = data['refresh_token']
            self.aes_key = data['aes_key']
            self.session_hmac_key = base64.b64decode(data['hmac_key'])
            self.access_expires = time.time() + data.get('access_ttl', 600) - 30  # 30s buffer
            return True
        except requests.ConnectionError:
            log.error("❌ Server connection failed. Check your internet.")
            return False
        except Exception as e:
            log.error(f"❌ Auth error: {e}")
            return False

    def _ensure_access(self):
        """Auto-refresh on access token expiry"""
        if time.time() < self.access_expires:
            return True
        if not self.session_hmac_key:
            return self.auth()
        body = sign_request({"refresh_token": self.refresh_token}, self.session_hmac_key)
        try:
            r = requests.post(f"{SERVER_URL}/api/trader/refresh", json=body, timeout=15)
            data = r.json()
            if data.get('ok'):
                self.access_token = data['access_token']
                self.access_expires = time.time() + data.get('access_ttl', 600) - 30
                return True
            else:
                log.warning(f"JWT refresh failed: {data.get('error')} — Re-auth attempt")
                return self.auth()
        except Exception as e:
            log.warning(f"JWT refresh error: {e}")
            return self.auth()

    def heartbeat(self):
        """Heartbeat"""
        if not self._ensure_access():
            return
        # Heartbeat endpoint uses JWT only (no HMAC), so we send plain.
        body = {"access_token": self.access_token}
        try:
            requests.post(f"{SERVER_URL}/api/trader/heartbeat", json=body, timeout=10)
        except:
            pass

    def disconnect(self):
        """Disconnect session"""
        body = {"access_token": self.access_token or "", "token": self.token}
        try:
            requests.post(f"{SERVER_URL}/api/trader/disconnect", json=body, timeout=10)
        except:
            pass

    def fetch_signals(self):
        """Fetch signals (AES decrypted)"""
        if not self._ensure_access():
            return None, None
        body = sign_request({"access_token": self.access_token}, self.session_hmac_key)
        try:
            r = requests.post(f"{SERVER_URL}/api/trader/signals", json=body, timeout=15)
            data = r.json()
            if not data.get('ok'):
                err = data.get('error', '')
                if err == 'token_expired':
                    if self._ensure_access():
                        return self.fetch_signals()  # 1 retry
                log.error(f"Signal fetch failed: {err}")
                return None, None

            # AES decryption
            decrypted = decrypt_payload(data['data'], self.aes_key)
            signals = {}
            date = None
            for s in decrypted['signals']:
                signals[s['coin']] = {
                    'net_signal': s['net_signal'],
                    'net_ratio': s['net_ratio'],
                    'price': s['price'],
                }
                date = s['date']
            return signals, date

        except Exception as e:
            log.error(f"Signal fetch error: {e}")
            return None, None


# ══════════════════════════════════════════
# Exchange connection
# ══════════════════════════════════════════
def create_exchange(exchange_name, api_key, api_secret, passphrase=None, testnet=False):
    """Create exchange CCXT instance"""
    config = {
        'apiKey': api_key,
        'secret': api_secret,
        'enableRateLimit': True,
        'options': {'defaultType': 'linear', 'adjustForTimeDifference': True},
    }

    if exchange_name == 'bybit':
        ex = ccxt.bybit(config)
    elif exchange_name == 'bitget':
        config['password'] = passphrase
        ex = ccxt.bitget(config)
    elif exchange_name == 'binance':
        ex = ccxt.binance(config)
    elif exchange_name == 'coinbase':
        ex = ccxt.coinbase(config)
    else:
        raise ValueError(f"Unsupported exchange: {exchange_name}")

    if testnet:
        ex.sandbox = True

    ex.load_markets()
    return ex


def get_symbol(coin, exchange_name):
    return COIN_SYMBOLS[coin][exchange_name]


# ══════════════════════════════════════════
# 5min candle close
# ══════════════════════════════════════════
def get_1m_close(ex, symbol):
    """Latest completed 1m candle close"""
    candles = ex.fetch_ohlcv(symbol, '1m', limit=2)
    if len(candles) >= 2:
        return float(candles[-2][4])
    return float(candles[-1][4])


# ══════════════════════════════════════════
# Position query
# ══════════════════════════════════════════
def get_current_positions(ex, exchange_name):
    positions = {}
    for p in ex.fetch_positions():
        symbol = p['symbol']
        coin = symbol.split('/')[0]
        if coin not in COIN_SYMBOLS:
            continue
        size = float(p['contracts'] or 0)
        if size > 0:
            positions[coin] = {
                'side': p['side'],
                'size': size,
                'notional': float(p['notional'] or 0),
                'entry_price': float(p['entryPrice'] or 0),
            }
    return positions


def set_leverage_safe(ex, symbol, leverage):
    try:
        ex.set_leverage(leverage, symbol)
    except ccxt.ExchangeError as e:
        if 'not modified' not in str(e).lower():
            log.warning(f"Set leverage {symbol} {leverage}x: {e}")


def set_position_mode_safe(ex):
    try:
        ex.set_position_mode(hedged=False)
    except ccxt.ExchangeError:
        pass


# ══════════════════════════════════════════
# Order execution — 3 modes
# ══════════════════════════════════════════
def place_limit_order(ex, symbol, side, qty, price, reduce_only=False):
    price = float(ex.price_to_precision(symbol, price))
    try:
        order = ex.create_order(
            symbol=symbol, type='limit', side=side, amount=qty, price=price,
            params={'reduceOnly': reduce_only},
        )
        log.info(f"  📝 LIMIT {side.upper()} {qty} @ ${price:,.4f}")
        return order
    except ccxt.InsufficientFunds as e:
        log.error(f"  ❌ Insufficient funds: {e}")
        return None
    except Exception as e:
        log.error(f"  ❌ Order error: {e}")
        return None


def place_market_order(ex, symbol, side, qty, reduce_only=False):
    for attempt in range(1, 4):
        try:
            order = ex.create_order(
                symbol=symbol, type='market', side=side, amount=qty,
                params={'reduceOnly': reduce_only},
            )
            avg = float(order.get('average', 0) or 0)
            log.info(f"  ⚡ MARKET {side.upper()} {qty} @ ~${avg:,.4f}")
            return order
        except ccxt.InsufficientFunds as e:
            log.error(f"  ❌ Insufficient funds: {e}")
            return None
        except (ccxt.NetworkError, ccxt.ExchangeNotAvailable) as e:
            log.warning(f"  ⚠️ Market order attempt {attempt}/3: {e}")
            if attempt < 3:
                time.sleep(3)
            else:
                return None
        except ccxt.ExchangeError as e:
            log.error(f"  ❌ Market order error: {e}")
            return None
    return None


def cancel_order_safe(ex, order_id, symbol):
    try:
        ex.cancel_order(order_id, symbol)
    except ccxt.OrderNotFound:
        pass
    except Exception as e:
        log.warning(f"  Cancel error {order_id}: {e}")


def execute_order(ex, coin, exchange_name, side, total_qty, initial_price, mode='1m_refill', reduce_only=False):
    """
    Unified order execution with 3 modes:
      market      — immediate market order
      1m_refill   — limit at 1m close, cancel & retry every 1 min
      daily_limit — limit at 1m close, wait until 23:00 UTC, cancel if unfilled
    """
    symbol = get_symbol(coin, exchange_name)
    market_info = ex.market(symbol)
    min_qty = market_info.get('limits', {}).get('amount', {}).get('min', 0) or 0

    total_qty = float(ex.amount_to_precision(symbol, total_qty))
    if total_qty < min_qty:
        log.info(f"  {coin}: qty {total_qty} < min {min_qty}, skip")
        return {'filled_qty': 0, 'avg_price': 0, 'rounds': 0, 'complete': False}

    # ── MODE: market ──
    if mode == 'market':
        order = place_market_order(ex, symbol, side, total_qty, reduce_only)
        if order:
            filled = float(order.get('filled', total_qty))
            avg = float(order.get('average', initial_price) or initial_price)
            return {'filled_qty': filled, 'avg_price': avg, 'rounds': 1, 'complete': True}
        return {'filled_qty': 0, 'avg_price': 0, 'rounds': 1, 'complete': False}

    # ── MODE: 1m_refill / daily_limit ──
    max_rounds = MAX_1M_ROUNDS if mode == '1m_refill' else 9999
    remaining = total_qty
    total_filled = 0.0
    total_cost = 0.0
    rounds = 0
    price = initial_price

    while remaining > 0 and rounds < max_rounds:
        rounds += 1

        # daily_limit: check deadline
        if mode == 'daily_limit':
            now_utc = datetime.now(timezone.utc)
            if now_utc.hour >= DAILY_LIMIT_DEADLINE:
                log.info(f"    {coin}: daily deadline {DAILY_LIMIT_DEADLINE}:00 UTC reached, stopping")
                break

        remaining = float(ex.amount_to_precision(symbol, remaining))
        if remaining < min_qty:
            log.info(f"    {coin}: remaining {remaining} < min {min_qty}, done")
            break

        order = place_limit_order(ex, symbol, side, remaining, price, reduce_only)
        if not order:
            break

        order_id = order['id']

        # Wait 1 minute, checking fill every FILL_CHECK_SEC
        wait_until = time.time() + 60
        filled_this_round = False

        while time.time() < wait_until:
            time.sleep(FILL_CHECK_SEC)
            try:
                status = ex.fetch_order(order_id, symbol)
                filled = float(status.get('filled', 0))
                avg = float(status.get('average', price) or price)

                if status.get('status') == 'closed':
                    total_cost += filled * avg
                    total_filled += filled
                    remaining -= filled
                    log.info(f"    ✅ {coin} R{rounds} Filled: {filled} @ ${avg:,.4f}")
                    filled_this_round = True
                    break

                if status.get('status') == 'canceled':
                    log.warning(f"    {coin} R{rounds} Externally cancelled")
                    filled_this_round = True
                    break
            except Exception as e:
                log.warning(f"    Fill check error: {e}")

        if not filled_this_round:
            # 1 min passed, check partial fill then cancel
            try:
                status = ex.fetch_order(order_id, symbol)
                filled = float(status.get('filled', 0))
                avg = float(status.get('average', price) or price)

                if filled > 0:
                    total_cost += filled * avg
                    total_filled += filled
                    remaining -= filled
                    log.info(f"    ⚡ {coin} R{rounds} Partial: {filled} (left {remaining:.6f})")

                if status.get('status') != 'closed':
                    cancel_order_safe(ex, order_id, symbol)
                    if mode == 'daily_limit':
                        log.info(f"    {coin} R{rounds} Re-order (daily_limit mode)")
                    else:
                        log.info(f"    🔄 {coin} R{rounds} Cancel → re-order at new 1m close")
                else:
                    break
            except Exception as e:
                log.error(f"    {coin} R{rounds} Status error: {e}")
                cancel_order_safe(ex, order_id, symbol)

            if remaining > 0:
                price = get_1m_close(ex, symbol)
                log.info(f"    {coin} New 1m close: ${price:,.4f}")

        if remaining <= 0:
            break

    avg_price = (total_cost / total_filled) if total_filled > 0 else 0
    complete = remaining <= 0 or remaining < min_qty

    if not complete:
        log.warning(f"  ⚠️ {coin} Not fully filled after {rounds} rounds, remaining {remaining:.6f}")

    return {'filled_qty': total_filled, 'avg_price': avg_price, 'rounds': rounds, 'complete': complete}


def close_position(ex, coin, exchange_name, current_pos, mode='1m_refill'):
    """Close position using specified mode"""
    symbol = get_symbol(coin, exchange_name)
    size = current_pos['size']
    close_side = 'sell' if current_pos['side'] == 'long' else 'buy'
    price = get_1m_close(ex, symbol)

    log.info(f"  🔄 {coin} CLOSE {current_pos['side']} {size} ({mode})")
    return execute_order(ex, coin, exchange_name, close_side, size, price,
                         mode=mode, reduce_only=True)


# ══════════════════════════════════════════
# Target position calculation
# ══════════════════════════════════════════
def calc_target_positions(signals, equity, leverage, allocation=None):
    targets = {}
    for coin, sig in signals.items():
        nr = sig['net_ratio']
        # Custom allocation: 0 = excluded
        alloc_pct = (allocation or {}).get(coin, 10) / 100
        if alloc_pct <= 0 or abs(nr) < 0.01:
            targets[coin] = {'side': None, 'notional': 0, 'net_ratio': nr}
        else:
            side = 'buy' if nr > 0 else 'sell'
            notional = equity * alloc_pct * abs(nr) * leverage
            targets[coin] = {'side': side, 'notional': notional, 'net_ratio': nr}
    return targets


# ══════════════════════════════════════════
# State management
# ══════════════════════════════════════════
def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH) as f:
            return json.load(f)
    return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, 'w') as f:
        json.dump(state, f, indent=2)


# ══════════════════════════════════════════
# Main execution
# ══════════════════════════════════════════
def run(token, exchange_name, api_key, api_secret, passphrase=None,
        leverage=3, dry=False, testnet=False, allocation=None, callbacks=None,
        entry_mode=None, close_mode=None, force=False):
    entry_mode = entry_mode or DEFAULT_ENTRY_MODE
    close_mode = close_mode or DEFAULT_CLOSE_MODE
    cb = callbacks or {}
    def _cb(name, *args):
        fn = cb.get(name)
        if fn:
            fn(*args)

    log.info(f"\n{'='*50}")
    log.info(f"AIQuantLab Auto Trader | {exchange_name.upper()} | {leverage}x")
    log.info(f"Entry: {entry_mode} | Close: {close_mode}")
    log.info(f"HWID: {get_hwid()[:12]}...")
    log.info(f"{'='*50}")

    _cb('on_status', 'Authenticating...')

    # 1. Server auth (JWT + HWID + HMAC)
    log.info("Authenticating...")
    session = ServerSession(token)
    if not session.auth():
        _cb('on_auth', False, 'Auth failed')
        return

    log.info("✅ Auth success")
    _cb('on_auth', True, 'Auth success')
    _cb('on_session', session)

    # Cleanup session on exit
    def cleanup():
        session.disconnect()
        log.info("Session closed")

    if not callbacks:
        atexit.register(cleanup)
        sig_module.signal(sig_module.SIGTERM, lambda s, f: sys.exit(0))
        sig_module.signal(sig_module.SIGINT, lambda s, f: sys.exit(0))

    # 2. Fetch signals (AES encrypted)
    _cb('on_status', 'Fetching signals...')
    signals, signal_date = session.fetch_signals()
    if not signals:
        log.error("Cannot fetch signals.")
        _cb('on_error', 'Cannot fetch signals')
        return

    log.info(f"Signal date: {signal_date} | Coins: {len(signals)}")
    _cb('on_signals', signals, signal_date)

    # Prevent duplicate (skip on force rebalance)
    state = load_state()
    if state.get('last_traded_date') == signal_date and not dry and not force:
        log.info(f"Already traded for {signal_date}. Wait for next signal.")
        return
    if force:
        log.info("⚠️  FORCE REBALANCE — realigning all positions to current capital")

    # Check should_stop
    if cb.get('should_stop') and cb['should_stop']():
        cleanup()
        return

    # 3. Dry run
    if dry:
        log.info("\n── Target Positions (DRY RUN) ──")
        for coin, sig in sorted(signals.items()):
            nr = sig['net_ratio']
            d = f"LONG {abs(nr)*100:.0f}%" if nr > 0 else (f"SHORT {abs(nr)*100:.0f}%" if nr < 0 else "FLAT")
            log.info(f"  {coin:5s} {d:15s} | ${sig['price']:>10,.2f}")

        log.info(f"\n  (Leverage {leverage}x, equity $10k)")
        for coin, sig in sorted(signals.items()):
            nr = sig['net_ratio']
            alloc_pct = (allocation or {}).get(coin, 10) / 100
            if abs(nr) > 0.01 and alloc_pct > 0:
                notional = 10000 * alloc_pct * abs(nr) * leverage
                side = "LONG" if nr > 0 else "SHORT"
                log.info(f"  {coin:5s} {side:5s} ${notional:>8,.1f} (alloc {alloc_pct*100:.0f}%)")
            elif alloc_pct <= 0:
                log.info(f"  {coin:5s} SKIP  (excluded)")
        return

    # 4. Exchange connection
    _cb('on_status', f'Connecting to {exchange_name.upper()}...')
    log.info(f"{exchange_name.upper()} Connecting...")
    ex = create_exchange(exchange_name, api_key, api_secret, passphrase, testnet)
    set_position_mode_safe(ex)

    balance = ex.fetch_balance()
    equity = float(balance['total'].get('USDT', 0))
    available = float(balance['free'].get('USDT', 0))
    log.info(f"Balance: ${equity:,.2f} | Available: ${available:,.2f}")

    if equity < 10:
        log.error("USDT balance under $10. Deposit and retry.")
        _cb('on_error', 'USDT balance under $10')
        return

    # 5. Current positions
    current = get_current_positions(ex, exchange_name)
    log.info(f"Current positions: {len(current)}")
    for coin, pos in current.items():
        log.info(f"  {coin}: {pos['side']} {pos['size']} (${pos['notional']:,.1f})")

    _cb('on_positions', current, equity, available)

    # 6. Target positions
    targets = calc_target_positions(signals, equity, leverage, allocation)
    _cb('on_targets', targets)

    # 7. Execute orders
    results = []
    pending_fills = []

    _cb('on_status', 'Executing orders...')
    for coin in list(COIN_SYMBOLS.keys()):
        if cb.get('should_stop') and cb['should_stop']():
            log.info("Stop requested, aborting orders")
            break
        if coin not in signals:
            continue

        target = targets[coin]
        cur = current.get(coin)
        symbol = get_symbol(coin, exchange_name)

        set_leverage_safe(ex, symbol, leverage)
        time.sleep(0.1)

        cur_side = cur['side'] if cur else None
        target_side = target['side']
        target_notional = target['notional']
        target_dir = 'long' if target_side == 'buy' else ('short' if target_side == 'sell' else None)
        cur_dir = cur_side

        # FLAT conversion (close)
        if cur and not target_dir:
            result = close_position(ex, coin, exchange_name, cur, mode=close_mode)
            ok = result and result.get('complete', False)
            results.append({'coin': coin, 'action': f'CLOSE {cur_dir} ({close_mode})', 'ok': ok})
            continue

        # Direction change (close → open)
        if cur and target_dir and cur_dir != target_dir:
            result = close_position(ex, coin, exchange_name, cur, mode=close_mode)
            if not result or not result.get('complete', False):
                results.append({'coin': coin, 'action': 'CLOSE_FAILED', 'ok': False})
                continue
            results.append({'coin': coin, 'action': f'CLOSE {cur_dir} ({close_mode})', 'ok': True})
            time.sleep(0.3)
            price = get_1m_close(ex, symbol)
            qty = target_notional / price
            qty = float(ex.amount_to_precision(symbol, qty))
            pending_fills.append({
                'coin': coin, 'side': target_side, 'qty': qty,
                'price': price, 'notional': target_notional, 'reduce_only': False,
            })
            continue

        # Same direction size adjustment
        if cur and target_dir and cur_dir == target_dir:
            cur_notional = cur['notional']
            diff = target_notional - cur_notional
            threshold = equity * 0.01

            if abs(diff) < threshold:
                log.info(f"  {coin}: hold (diff ${diff:,.0f})")
                results.append({'coin': coin, 'action': 'hold', 'ok': True})
                continue

            price = get_1m_close(ex, symbol)

            if diff > 0:
                qty = abs(diff) / price
                qty = float(ex.amount_to_precision(symbol, qty))
                pending_fills.append({
                    'coin': coin, 'side': target_side, 'qty': qty,
                    'price': price, 'notional': abs(diff), 'reduce_only': False,
                })
            else:
                qty = abs(diff) / price
                qty = float(ex.amount_to_precision(symbol, qty))
                reduce_side = 'sell' if cur_dir == 'long' else 'buy'
                pending_fills.append({
                    'coin': coin, 'side': reduce_side, 'qty': qty,
                    'price': price, 'notional': abs(diff), 'reduce_only': True,
                })
            continue

        # New position
        if not cur and target_dir:
            price = get_1m_close(ex, symbol)
            qty = target_notional / price
            qty = float(ex.amount_to_precision(symbol, qty))
            pending_fills.append({
                'coin': coin, 'side': target_side, 'qty': qty,
                'price': price, 'notional': target_notional, 'reduce_only': False,
            })
            continue

        # Both empty
        if not cur and not target_dir:
            log.info(f"  {coin}: FLAT")
            results.append({'coin': coin, 'action': 'flat', 'ok': True})

    # 8. Execute pending orders
    if pending_fills:
        log.info(f"\n── Orders ({len(pending_fills)}, entry={entry_mode}) ──")
        for pf in pending_fills:
            coin = pf['coin']
            mode = close_mode if pf['reduce_only'] else entry_mode
            log.info(f"  {coin}: {pf['side'].upper()} {pf['qty']} @ ${pf['price']:,.4f} ({mode})")

            session.heartbeat()

            fill = execute_order(
                ex, coin, exchange_name, pf['side'], pf['qty'], pf['price'],
                mode=mode, reduce_only=pf['reduce_only'],
            )

            action = f"{'REDUCE' if pf['reduce_only'] else 'OPEN'} {pf['side'].upper()} ${pf['notional']:,.0f}"
            if fill['complete']:
                action += f" R{fill['rounds']} avg ${fill['avg_price']:,.4f}"
                r = {'coin': coin, 'action': action, 'ok': True}
            else:
                action += f" partial {fill['filled_qty']:.6f}/{pf['qty']:.6f}"
                r = {'coin': coin, 'action': action, 'ok': False}
            results.append(r)
            _cb('on_result', r)

    # 9. Results
    ok_count = sum(1 for r in results if r['ok'])
    fail_count = sum(1 for r in results if not r['ok'])

    log.info(f"\n── Results ──")
    log.info(f"Success: {ok_count} | Failed: {fail_count}")
    for r in results:
        s = "✅" if r['ok'] else "❌"
        log.info(f"  {s} {r['coin']:5s} {r['action']}")

    # 10. Save state
    state['last_traded_date'] = signal_date
    state['last_run'] = datetime.now(timezone.utc).isoformat()
    state['exchange'] = exchange_name
    state['results'] = [{'coin': r['coin'], 'action': r['action'], 'ok': r['ok']} for r in results]
    save_state(state)

    log.info("\ndone!\n")
    cleanup()
    _cb('on_status', 'Idle')
    _cb('on_complete', results)


# ══════════════════════════════════════════
# CLI
# ══════════════════════════════════════════
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='AIQuantLab Auto Trader')
    parser.add_argument('--setup', action='store_true', help='Run setup wizard')
    parser.add_argument('--token', type=str, help='Auth token')
    parser.add_argument('--exchange', type=str, choices=SUPPORTED_EXCHANGES, help='Exchange')
    parser.add_argument('--api-key', type=str, help='Exchange API Key')
    parser.add_argument('--api-secret', type=str, help='Exchange API Secret')
    parser.add_argument('--passphrase', type=str, help='Bitget Passphrase')
    parser.add_argument('--leverage', type=int, default=3, help='Leverage (default 3)')
    parser.add_argument('--entry-mode', type=str, choices=['market', '1m_refill', 'daily_limit'], help='Entry order mode')
    parser.add_argument('--close-mode', type=str, choices=['market', '1m_refill', 'daily_limit'], help='Close order mode')
    parser.add_argument('--dry', action='store_true', help='Dry run')
    parser.add_argument('--testnet', action='store_true', help='Test net')
    args = parser.parse_args()

    # Setup wizard
    if args.setup:
        cfg = setup_wizard()
        print("\nRun again to start auto-trading.")
        sys.exit(0)

    # Load config (CLI args > config file)
    cfg = load_config()
    token = args.token or cfg.get('token')
    exchange = args.exchange or cfg.get('exchange')
    api_key = args.api_key or cfg.get('api_key')
    api_secret = args.api_secret or cfg.get('api_secret')
    passphrase = args.passphrase or cfg.get('passphrase')
    leverage = args.leverage or cfg.get('leverage', 3)

    if not token:
        print("No token. Use --setup or --token.")
        sys.exit(1)

    if not exchange or not api_key or not api_secret:
        print("No exchange config. Use --setup.")
        sys.exit(1)

    run(
        token=token,
        exchange_name=exchange,
        api_key=api_key,
        api_secret=api_secret,
        passphrase=passphrase,
        leverage=leverage,
        dry=args.dry,
        testnet=args.testnet,
        allocation=cfg.get('allocation'),
        entry_mode=args.entry_mode or cfg.get('entry_mode'),
        close_mode=args.close_mode or cfg.get('close_mode'),
    )

# AIQuantLab Auto Trader

Desktop client for AIQuantLab 360-day subscribers. Receives daily signals from the AIQuantLab server and places orders on your exchange account automatically.

## Supported exchanges

Bybit · Bitget · Binance · Coinbase (USDT-margined perpetual futures)

## Install

Download the build for your OS from the [Releases](../../releases) page or the latest [Actions](../../actions) run:

- **Windows:** `AIQuantLab_Trader.exe`
- **macOS:** `AIQuantLab_Trader`
- **Linux:** `AIQuantLab_Trader`

No Python install required — single executable.

## First run

1. Launch the app
2. Enter your subscription token (from the AIQuantLab Telegram bot)
3. Pick your exchange and enter read/trade API keys (**disable withdrawal permission, enable IP whitelist**)
4. Set leverage (1x/3x/5x/10x) and coin allocation (% per coin, total ≤ 100%)
5. Keep the app running — it reads signals at 00:00 UTC daily

## Security

- API keys stored locally, AES-GCM encrypted, bound to your machine (HWID)
- Server communication: JWT + HMAC signed, 60-second replay window
- Zero algorithm data leaves the server — client only receives final allocation directives

## Build from source

```bash
pip install -r requirements.txt
pyinstaller --clean --noconfirm auto_trader_gui.spec
# output: dist/AIQuantLab_Trader[.exe]
```

## Support

Website: [aiquantlab.io](https://aiquantlab.io) · Bot: [@AIQuantLabBot](https://t.me/AIQuantLabBot)

# Money Agent — tastytrade × Claude

Automated stock trading bot that:
1. Screens a small universe of liquid US stocks/ETFs daily.
2. Asks **Claude** to approve or veto each candidate.
3. Places approved orders on **tastytrade** (sandbox by default).
4. Manages stops and profit targets on open positions.

## Architecture

```
yfinance ── screener.py ── candidates ──▶ claude_filter.py (approve/veto)
                                                 │
                                                 ▼
                                          executor.py ──▶ tastytrade
                                                 ▲
                                          monitor.py (stops/targets)
```

## Safety defaults

- `TASTYTRADE_ENV=sandbox` — paper trading until you flip it.
- `DRY_RUN=true` — don't actually place orders.
- 1% account risk per trade, max 3 trades/day, max 5 open positions.
- 5% intra-day loss → trading halts automatically.
- Claude must approve every order, or it doesn't go.
- `v1` only goes long. Shorts are blocked.

## Setup

```bash
# 1. Clone & enter
git clone <this-repo> && cd tradingview

# 2. Create a virtualenv
python3 -m venv .venv && source .venv/bin/activate

# 3. Install deps
pip install -r requirements.txt

# 4. Create .env
cp .env.example .env
#    -> open .env in an editor and fill in real values
```

## First run

```bash
# 1. Verify auth works
python main.py auth

# 2. See what the screener finds (no trading)
python main.py screen

# 3. End-to-end pipeline with DRY_RUN forced on
python main.py dry-run

# 4. Once you're happy: set DRY_RUN=false in .env, then
python main.py trade

# 5. Each day:
python main.py full     # monitor + trade
```

## Going from sandbox to live

1. Watch DRY_RUN behaviour for a day or two.
2. Set `DRY_RUN=false` in sandbox; place real (paper) orders.
3. Watch sandbox trades for ~2 weeks. Make sure win/loss looks reasonable.
4. **Only then:** change `TASTYTRADE_ENV=live` and update username/password to your real tastytrade login.
5. Start with small position sizes by lowering `RISK_PER_TRADE_PCT`.

## Files

| File | Purpose |
|---|---|
| `config.py` | Loads `.env`, defines universe, risk limits |
| `tastytrade_client.py` | Auth + REST client |
| `screener.py` | Scans universe, scores candidates |
| `claude_filter.py` | Claude approval/veto |
| `executor.py` | Sizing, risk checks, order placement |
| `monitor.py` | Closes positions on stop/target |
| `state.py` | Persists positions + daily counters |
| `main.py` | CLI |

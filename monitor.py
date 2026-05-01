"""Watch open positions, close on stop / target."""
from typing import List

import pandas as pd
import yfinance as yf

import config
import state
from tastytrade_client import TastytradeClient, TastytradeError


def _last_price(symbol: str) -> float | None:
    """Most-recent quote: latest 1-minute bar, falling back to daily close.

    1-minute bars give intraday hits for stops and targets while the market
    is open. The daily fallback covers weekends and any case where the
    intraday feed is empty (low-volume names, just-after-open, etc.).
    """
    for period, interval in (("1d", "1m"), ("5d", "1d")):
        try:
            df = yf.download(
                symbol,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=True,
            )
        except Exception:
            continue
        if df is None or df.empty:
            continue
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return float(df["Close"].iloc[-1])
    return None


def run_monitor(client: TastytradeClient) -> List[dict]:
    """Check every open position; close any that hit stop or target."""
    closed = []
    for pos in list(state.open_positions()):
        sym = pos["symbol"]
        last = _last_price(sym)
        if last is None:
            print(f"[monitor] {sym}: could not fetch price, skipping")
            continue

        direction = pos["direction"]
        stop = pos["stop_price"]
        target = pos["target_price"]
        entry = pos["entry_price"]
        qty = pos["quantity"]

        hit_stop = (direction == "long" and last <= stop) or (direction == "short" and last >= stop)
        hit_target = (direction == "long" and last >= target) or (direction == "short" and last <= target)

        if not (hit_stop or hit_target):
            pnl_pct = (last - entry) / entry * 100 * (1 if direction == "long" else -1)
            print(f"[monitor] {sym}: ${last:.2f} (entry ${entry:.2f}, {pnl_pct:+.2f}%) — holding")
            continue

        reason = "stop" if hit_stop else "target"
        action = "Sell to Close" if direction == "long" else "Buy to Close"
        print(f"[monitor] {sym}: hit {reason} at ${last:.2f} -> {action} {qty}")

        if config.DRY_RUN:
            print(f"[monitor] DRY_RUN — would close {qty} {sym}")
        else:
            try:
                client.place_equity_order(sym, qty, action)
            except TastytradeError as e:
                print(f"[monitor] {sym}: close failed: {e}")
                continue

        pnl_dollars = (last - entry) * qty * (1 if direction == "long" else -1)
        pnl_pct = (last - entry) / entry * 100 * (1 if direction == "long" else -1)
        state.remove_position(sym)
        closed.append({
            "symbol": sym,
            "direction": direction,
            "exit_price": last,
            "exit_reason": reason,
            "pnl_dollars": round(pnl_dollars, 2),
            "pnl_pct": round(pnl_pct, 2),
        })

    return closed


def print_summary() -> None:
    positions = state.open_positions()
    print("\n=== Portfolio Summary ===")
    print(f"Mode:           {config.TASTYTRADE_ENV.upper()}  DRY_RUN={config.DRY_RUN}")
    print(f"Open positions: {len(positions)} / {config.MAX_OPEN_POSITIONS}")
    print(f"Trades today:   {state.trades_today()} / {config.MAX_TRADES_PER_DAY}")
    if not positions:
        print("(no open positions)")
        return
    for p in positions:
        last = _last_price(p["symbol"])
        if last is None:
            print(f"  {p['symbol']:6s} {p['direction']:5s} qty={p['quantity']}  entry=${p['entry_price']:.2f}  (no quote)")
            continue
        pnl_pct = (last - p["entry_price"]) / p["entry_price"] * 100 * (1 if p["direction"] == "long" else -1)
        print(f"  {p['symbol']:6s} {p['direction']:5s} qty={p['quantity']}  "
              f"entry=${p['entry_price']:.2f}  last=${last:.2f}  ({pnl_pct:+.2f}%)  "
              f"stop=${p['stop_price']:.2f}  target=${p['target_price']:.2f}")

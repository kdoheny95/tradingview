"""Watch open positions, close on stop / target."""
import time
from typing import List

import yfinance as yf

import config
import history
import state
from tastytrade_client import TastytradeClient, TastytradeError


def _last_price(symbol: str) -> float | None:
    """Fetch the latest close. Tries two yfinance endpoints with retries.

    yfinance's per-symbol calls get rate-limited periodically; falling back
    between Ticker.history (chart endpoint) and yf.download (download endpoint)
    plus a couple of retries works around most transient failures.
    """
    for attempt in range(3):
        try:
            df = yf.Ticker(symbol).history(period="5d", interval="1d", auto_adjust=True)
            if df is not None and not df.empty:
                return float(df["Close"].iloc[-1])
        except Exception:
            pass
        try:
            df = yf.download(symbol, period="5d", interval="1d", progress=False, auto_adjust=True)
            if df is not None and not df.empty:
                return float(df["Close"].iloc[-1])
        except Exception:
            pass
        if attempt < 2:
            time.sleep(1 + attempt)
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
        history.record_closed_trade(
            symbol=sym,
            direction=direction,
            quantity=qty,
            entry_price=entry,
            stop_price=stop,
            target_price=target,
            entry_date=pos.get("opened_on", ""),
            exit_price=last,
            exit_reason=reason,
            pnl_dollars=pnl_dollars,
            pnl_pct=pnl_pct,
        )
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
    # Fetch prices once and reuse for both portfolio totals and the per-position lines.
    pos_prices = {p["symbol"]: _last_price(p["symbol"]) for p in positions}

    starting = float(config.NOTIONAL_ACCOUNT_SIZE)
    realized = sum(t["pnl_dollars"] for t in history.all_trades())
    unrealized = 0.0
    for p in positions:
        last = pos_prices[p["symbol"]]
        if last is None:
            continue
        sign = 1 if p["direction"] == "long" else -1
        unrealized += (last - p["entry_price"]) * p["quantity"] * sign
    total = starting + realized + unrealized
    pct = (total - starting) / starting * 100 if starting > 0 else 0.0

    print("\n=== Portfolio Summary ===")
    print(f"Mode:            {config.TASTYTRADE_ENV.upper()}  DRY_RUN={config.DRY_RUN}")
    print(f"Starting equity: ${starting:,.2f}")
    print(f"Realized P&L:    ${realized:+,.2f}")
    print(f"Unrealized P&L:  ${unrealized:+,.2f}")
    print(f"Total worth:     ${total:,.2f}  ({pct:+.2f}%)")
    print(f"Open positions:  {len(positions)} / {config.MAX_OPEN_POSITIONS}")
    print(f"Trades today:    {state.trades_today()} / {config.MAX_TRADES_PER_DAY}")
    if not positions:
        print("(no open positions)")
        return
    for p in positions:
        last = pos_prices[p["symbol"]]
        if last is None:
            print(f"  {p['symbol']:6s} {p['direction']:5s} qty={p['quantity']}  entry=${p['entry_price']:.2f}  (no quote)")
            continue
        pnl_pct = (last - p["entry_price"]) / p["entry_price"] * 100 * (1 if p["direction"] == "long" else -1)
        print(f"  {p['symbol']:6s} {p['direction']:5s} qty={p['quantity']}  "
              f"entry=${p['entry_price']:.2f}  last=${last:.2f}  ({pnl_pct:+.2f}%)  "
              f"stop=${p['stop_price']:.2f}  target=${p['target_price']:.2f}")

"""Position sizing, risk checks, Claude approval, order placement."""
import math
from dataclasses import dataclass
from typing import Optional

import config
import state
from claude_filter import review
from screener import Candidate
from tastytrade_client import TastytradeClient, TastytradeError


@dataclass
class TradeResult:
    placed: bool
    symbol: str
    direction: str
    quantity: int
    entry_price: float
    stop_price: float
    target_price: float
    reason: str


def _account_equity(client: TastytradeClient) -> float:
    """In live mode, read the real balance. In sandbox, use NOTIONAL_ACCOUNT_SIZE."""
    if config.TASTYTRADE_ENV == "live":
        try:
            bal = client.get_balance()
            return float(bal.get("net-liquidating-value") or bal.get("equity-buying-power") or config.NOTIONAL_ACCOUNT_SIZE)
        except TastytradeError:
            return config.NOTIONAL_ACCOUNT_SIZE
    return config.NOTIONAL_ACCOUNT_SIZE


def _size_position(equity: float, entry: float, stop: float) -> int:
    """Risk-based position sizing.

    risk_dollars = equity * RISK_PER_TRADE_PCT/100
    quantity     = floor(risk_dollars / |entry - stop|)
    """
    risk_dollars = equity * (config.RISK_PER_TRADE_PCT / 100.0)
    per_share_risk = abs(entry - stop)
    if per_share_risk <= 0:
        return 0
    qty = math.floor(risk_dollars / per_share_risk)
    # Don't allocate more than 25% of equity to one position
    max_qty_by_capital = math.floor((equity * 0.25) / entry)
    return max(0, min(qty, max_qty_by_capital))


def _stop_and_target(direction: str, entry: float, atr: float) -> tuple[float, float]:
    """Stop = 1.5 ATR away, target = 2x risk (R:R = 2:1)."""
    risk = max(0.01, 1.5 * atr)
    if direction == "long":
        stop = round(entry - risk, 2)
        target = round(entry + 2 * risk, 2)
    else:
        stop = round(entry + risk, 2)
        target = round(entry - 2 * risk, 2)
    return stop, target


def _check_daily_halts(equity: float) -> Optional[str]:
    """Return a reason string if trading should halt today, else None."""
    if state.trades_today() >= config.MAX_TRADES_PER_DAY:
        return f"daily trade cap reached ({config.MAX_TRADES_PER_DAY})"
    if len(state.open_positions()) >= config.MAX_OPEN_POSITIONS:
        return f"max open positions reached ({config.MAX_OPEN_POSITIONS})"
    start = state.starting_equity()
    if start and start > 0:
        drawdown_pct = (start - equity) / start * 100
        if drawdown_pct >= config.DAILY_LOSS_HALT_PCT:
            return f"daily loss halt: -{drawdown_pct:.1f}% (limit {config.DAILY_LOSS_HALT_PCT}%)"
    return None


def execute_candidate(candidate: Candidate, client: TastytradeClient) -> TradeResult:
    """End-to-end: risk-check -> Claude review -> size -> place order."""
    equity = _account_equity(client)
    state.get_state(current_equity=equity)  # ensure day rollover

    halt = _check_daily_halts(equity)
    if halt:
        return TradeResult(False, candidate.symbol, candidate.direction, 0, 0, 0, 0, halt)

    # Don't double up on a symbol we already hold
    if any(p["symbol"] == candidate.symbol for p in state.open_positions()):
        return TradeResult(False, candidate.symbol, candidate.direction, 0, 0, 0, 0,
                           "already have an open position in this symbol")

    entry = candidate.last_price
    atr = float(candidate.indicators.get("atr14", entry * 0.02))
    stop, target = _stop_and_target(candidate.direction, entry, atr)
    qty = _size_position(equity, entry, stop)

    if qty < 1:
        return TradeResult(False, candidate.symbol, candidate.direction, 0, entry, stop, target,
                           "position size rounded to 0 (account too small for this stop distance)")

    # Claude check
    try:
        verdict = review(candidate, market_context=f"sandbox={config.TASTYTRADE_ENV != 'live'}")
    except Exception as e:
        return TradeResult(False, candidate.symbol, candidate.direction, qty, entry, stop, target,
                           f"Claude review failed: {type(e).__name__}: {e}")
    if not verdict.approve:
        return TradeResult(False, candidate.symbol, candidate.direction, qty, entry, stop, target,
                           f"Claude vetoed (conf {verdict.confidence}): {verdict.reason}")

    print(f"[executor] Claude approved {candidate.symbol} (conf {verdict.confidence}): {verdict.reason}")

    # Shorting equities requires margin & locate; v1 only goes long.
    if candidate.direction == "short":
        return TradeResult(False, candidate.symbol, candidate.direction, qty, entry, stop, target,
                           "short selling disabled in v1 (cash account)")

    action = "Buy to Open"

    if config.DRY_RUN:
        print(f"[executor] DRY_RUN — would BUY {qty} {candidate.symbol} @ ~${entry:.2f} "
              f"(stop ${stop:.2f}, target ${target:.2f})")
        # Validate via tastytrade dry-run endpoint as a real-API sanity check
        try:
            client.dry_run_equity_order(candidate.symbol, qty, action)
            print(f"[executor] tastytrade dry-run validation OK")
        except TastytradeError as e:
            return TradeResult(False, candidate.symbol, candidate.direction, qty, entry, stop, target,
                               f"dry-run rejected: {e}")
        state.record_trade(candidate.symbol, candidate.direction, qty, entry, stop, target)
        return TradeResult(True, candidate.symbol, candidate.direction, qty, entry, stop, target,
                           "DRY_RUN ok")

    # Live order placement
    try:
        client.place_equity_order(candidate.symbol, qty, action)
    except TastytradeError as e:
        return TradeResult(False, candidate.symbol, candidate.direction, qty, entry, stop, target,
                           f"order rejected: {e}")

    state.record_trade(candidate.symbol, candidate.direction, qty, entry, stop, target)
    return TradeResult(True, candidate.symbol, candidate.direction, qty, entry, stop, target,
                       "order placed")

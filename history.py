"""Append-only logs for closed trades, daily equity snapshots, and failed runs.

Used by weekly_summary.py to compute the go-live readiness scorecard.
Files are JSONL — one record per line, easy to inspect with `cat`.
"""
import json
import os
from datetime import date, datetime, timedelta, timezone
from typing import Optional

TRADE_HISTORY_FILE = "trade_history.jsonl"
EQUITY_HISTORY_FILE = "equity_history.jsonl"
FAILED_RUNS_FILE = "failed_runs.jsonl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _append(path: str, record: dict) -> None:
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


def _read_all(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def record_closed_trade(
    symbol: str,
    direction: str,
    quantity: int,
    entry_price: float,
    stop_price: float,
    target_price: float,
    entry_date: str,
    exit_price: float,
    exit_reason: str,
    pnl_dollars: float,
    pnl_pct: float,
) -> None:
    if direction == "long":
        per_share_risk = max(entry_price - stop_price, 1e-9)
        r_multiple = (exit_price - entry_price) / per_share_risk
    else:
        per_share_risk = max(stop_price - entry_price, 1e-9)
        r_multiple = (entry_price - exit_price) / per_share_risk

    _append(TRADE_HISTORY_FILE, {
        "symbol": symbol,
        "direction": direction,
        "quantity": quantity,
        "entry_price": round(entry_price, 4),
        "stop_price": round(stop_price, 4),
        "target_price": round(target_price, 4),
        "entry_date": entry_date,
        "exit_price": round(exit_price, 4),
        "exit_reason": exit_reason,
        "exit_date": date.today().isoformat(),
        "exit_time_utc": _utc_now(),
        "pnl_dollars": round(pnl_dollars, 2),
        "pnl_pct": round(pnl_pct, 2),
        "r_multiple": round(r_multiple, 3),
    })


def record_equity_snapshot(equity: float, open_positions: int, mode: str) -> None:
    """Idempotent for the day — only writes once per local date."""
    today = date.today().isoformat()
    for rec in _read_all(EQUITY_HISTORY_FILE):
        if rec.get("date") == today:
            return
    _append(EQUITY_HISTORY_FILE, {
        "date": today,
        "equity": round(equity, 2),
        "open_positions": open_positions,
        "mode": mode,
    })


def record_failed_run(exit_status: int, log_tail: str) -> None:
    _append(FAILED_RUNS_FILE, {
        "timestamp": _utc_now(),
        "exit_status": int(exit_status),
        "log_tail": log_tail[-2000:],
    })


def all_trades() -> list[dict]:
    return _read_all(TRADE_HISTORY_FILE)


def trades_in_week(end_date: date) -> list[dict]:
    start = end_date - timedelta(days=6)
    out = []
    for t in all_trades():
        try:
            ed = date.fromisoformat(t.get("exit_date", ""))
        except ValueError:
            continue
        if start <= ed <= end_date:
            out.append(t)
    return out


def all_equity_snapshots() -> list[dict]:
    return _read_all(EQUITY_HISTORY_FILE)


def failed_runs_count() -> int:
    return len(_read_all(FAILED_RUNS_FILE))

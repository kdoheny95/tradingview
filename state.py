"""Local persistence of bot state (open positions, daily counters)."""
import json
import os
from datetime import date
from typing import Optional

import config


def _load() -> dict:
    if not os.path.exists(config.POSITIONS_FILE):
        return {"positions": [], "day": "", "trades_today": 0, "starting_equity": None}
    try:
        with open(config.POSITIONS_FILE) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"positions": [], "day": "", "trades_today": 0, "starting_equity": None}


def _save(state: dict) -> None:
    with open(config.POSITIONS_FILE, "w") as f:
        json.dump(state, f, indent=2)


def _roll_day_if_needed(state: dict, current_equity: Optional[float]) -> dict:
    today = date.today().isoformat()
    if state.get("day") != today:
        state["day"] = today
        state["trades_today"] = 0
        state["starting_equity"] = current_equity
    elif state.get("starting_equity") is None and current_equity is not None:
        state["starting_equity"] = current_equity
    return state


def get_state(current_equity: Optional[float] = None) -> dict:
    state = _load()
    state = _roll_day_if_needed(state, current_equity)
    _save(state)
    return state


def record_trade(symbol: str, direction: str, quantity: int, entry_price: float,
                 stop_price: float, target_price: float) -> None:
    state = _load()
    state["trades_today"] = int(state.get("trades_today", 0)) + 1
    state.setdefault("positions", []).append({
        "symbol": symbol,
        "direction": direction,
        "quantity": quantity,
        "entry_price": entry_price,
        "stop_price": stop_price,
        "target_price": target_price,
        "opened_on": date.today().isoformat(),
    })
    _save(state)


def remove_position(symbol: str) -> None:
    state = _load()
    state["positions"] = [p for p in state.get("positions", []) if p["symbol"] != symbol]
    _save(state)


def open_positions() -> list:
    return _load().get("positions", [])


def trades_today() -> int:
    return int(_load().get("trades_today", 0))


def starting_equity() -> Optional[float]:
    return _load().get("starting_equity")

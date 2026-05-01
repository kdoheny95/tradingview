"""Simple screener: scores each symbol in the universe 0-100.

This is intentionally lightweight. Claude is the smart filter; this just
surfaces candidates that look interesting based on price action.
"""
from dataclasses import dataclass
from typing import List, Optional

import pandas as pd
import yfinance as yf

import config


@dataclass
class Candidate:
    symbol: str
    direction: str  # "long" or "short"
    score: int      # 0-100
    last_price: float
    rationale: str  # short, machine-generated reason
    indicators: dict


def _fetch(symbol: str) -> Optional[pd.DataFrame]:
    """Get ~6 months of daily bars."""
    try:
        df = yf.download(
            symbol,
            period="6mo",
            interval="1d",
            progress=False,
            auto_adjust=True,
        )
    except Exception:
        return None
    if df is None or df.empty or len(df) < 50:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df


def _score(df: pd.DataFrame) -> Candidate:
    """Score one symbol. Caller guarantees df has >=50 rows (see _fetch)."""
    close = df["Close"].astype(float)
    sma20 = close.rolling(20).mean()
    sma50 = close.rolling(50).mean()
    last = float(close.iloc[-1])
    last_sma20 = float(sma20.iloc[-1])
    last_sma50 = float(sma50.iloc[-1])

    # RSI (14)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, 1e-9)
    rsi = (100 - 100 / (1 + rs)).iloc[-1]
    rsi = float(rsi) if pd.notna(rsi) else 50.0

    # 5-day return
    ret_5d = float((last / float(close.iloc[-6]) - 1) * 100) if len(close) > 6 else 0.0

    # ATR(14) for sizing
    high = df["High"].astype(float)
    low = df["Low"].astype(float)
    tr = pd.concat(
        [
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = float(tr.rolling(14).mean().iloc[-1])

    # ---- scoring ----
    score = 0
    direction = "long"
    reasons = []

    if last > last_sma20 > last_sma50:
        score += 30
        reasons.append("uptrend (price > SMA20 > SMA50)")
        direction = "long"
    elif last < last_sma20 < last_sma50:
        score += 30
        reasons.append("downtrend (price < SMA20 < SMA50)")
        direction = "short"

    if direction == "long":
        if 40 <= rsi <= 65:
            score += 25
            reasons.append(f"RSI healthy ({rsi:.0f})")
        elif rsi < 35:
            score += 15
            reasons.append(f"RSI oversold ({rsi:.0f}) — possible bounce")
        if 1 < ret_5d < 8:
            score += 20
            reasons.append(f"5d momentum +{ret_5d:.1f}%")
    else:
        if 35 <= rsi <= 60:
            score += 25
            reasons.append(f"RSI bearish range ({rsi:.0f})")
        if -8 < ret_5d < -1:
            score += 20
            reasons.append(f"5d momentum {ret_5d:.1f}%")

    # Liquidity bonus
    avg_vol = float(df["Volume"].tail(20).mean())
    if avg_vol > 1_000_000:
        score += 15
        reasons.append("liquid (avg vol > 1M)")

    score = max(0, min(100, score))

    return Candidate(
        symbol="",  # filled by caller
        direction=direction,
        score=score,
        last_price=round(last, 2),
        rationale="; ".join(reasons),
        indicators={
            "sma20": round(last_sma20, 2),
            "sma50": round(last_sma50, 2),
            "rsi14": round(rsi, 1),
            "ret_5d_pct": round(ret_5d, 2),
            "atr14": round(atr, 2),
            "avg_vol_20d": int(avg_vol),
        },
    )


def run_screener(min_score: Optional[int] = None) -> List[Candidate]:
    """Score every symbol in the universe; return those above threshold."""
    threshold = min_score if min_score is not None else config.MIN_SCORE
    out: List[Candidate] = []
    for sym in config.UNIVERSE:
        df = _fetch(sym)
        if df is None:
            print(f"[screener] {sym}: no data, skipped")
            continue
        cand = _score(df)
        cand.symbol = sym
        flag = "✓" if cand.score >= threshold else " "
        print(
            f"[screener] {flag} {sym:6s} {cand.direction:5s} "
            f"score={cand.score:3d}  ${cand.last_price:7.2f}  "
            f"RSI={cand.indicators['rsi14']:.0f}  5d={cand.indicators['ret_5d_pct']:+.1f}%"
        )
        if cand.score >= threshold:
            out.append(cand)
    out.sort(key=lambda c: c.score, reverse=True)
    return out

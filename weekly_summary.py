"""Weekly summary + go-live readiness scorecard.

Run on Fridays after market close. Prints a report to stdout — the cron
wrapper forwards it to ntfy.
"""
from datetime import date

import config
import history


REQ_DAYS = 10
REQ_TRADES = 10
REQ_WIN_RATE = 0.40
REQ_EXPECTANCY_R = 0.0
REQ_MAX_DRAWDOWN_PCT = 5.0
REQ_FAILED_RUNS = 0


def _max_drawdown_pct(equity_series: list[float]) -> float:
    if not equity_series:
        return 0.0
    peak = equity_series[0]
    max_dd = 0.0
    for v in equity_series:
        peak = max(peak, v)
        dd = (peak - v) / peak * 100 if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
    return max_dd


def build_report() -> str:
    today = date.today()
    all_t = history.all_trades()
    week_t = history.trades_in_week(today)
    snaps = history.all_equity_snapshots()
    failed = history.failed_runs_count()

    wk_wins = sum(1 for t in week_t if t["pnl_dollars"] > 0)
    wk_losses = sum(1 for t in week_t if t["pnl_dollars"] <= 0)
    wk_pnl = sum(t["pnl_dollars"] for t in week_t)
    wk_pnl_pct = 0.0
    if snaps:
        # Reference equity at the start of the week (or earliest snapshot we have).
        idx = max(0, len(snaps) - 5)
        start_eq = snaps[idx]["equity"]
        if start_eq > 0:
            wk_pnl_pct = wk_pnl / start_eq * 100

    days_running = len(snaps)
    n_trades = len(all_t)
    wins = [t for t in all_t if t["pnl_dollars"] > 0]
    losses = [t for t in all_t if t["pnl_dollars"] <= 0]
    win_rate = len(wins) / n_trades if n_trades else 0.0
    avg_winner = sum(t["pnl_dollars"] for t in wins) / len(wins) if wins else 0.0
    avg_loser = sum(t["pnl_dollars"] for t in losses) / len(losses) if losses else 0.0
    expectancy_r = sum(t["r_multiple"] for t in all_t) / n_trades if n_trades else 0.0
    max_dd = _max_drawdown_pct([s["equity"] for s in snaps])

    gates = [
        ("Trading days",   days_running >= REQ_DAYS,                f"{days_running} / {REQ_DAYS}"),
        ("Closed trades",  n_trades >= REQ_TRADES,                  f"{n_trades} / {REQ_TRADES}"),
        ("Win rate",       win_rate >= REQ_WIN_RATE,                f"{win_rate*100:.0f}% (need {REQ_WIN_RATE*100:.0f}%+)"),
        ("Expectancy",     expectancy_r > REQ_EXPECTANCY_R,         f"{expectancy_r:+.2f}R"),
        ("Max drawdown",   max_dd <= REQ_MAX_DRAWDOWN_PCT,          f"{max_dd:.1f}% (limit {REQ_MAX_DRAWDOWN_PCT:.0f}%)"),
        ("Failed runs",    failed <= REQ_FAILED_RUNS,               f"{failed}"),
    ]
    passed = sum(1 for _, ok, _ in gates if ok)
    ready = passed == len(gates)

    lines = []
    lines.append(f"=== Week ending {today.isoformat()} ===")
    lines.append(f"Trades this week:  {len(week_t)} ({wk_wins}W / {wk_losses}L)")
    lines.append(f"Realized P&L:      ${wk_pnl:+.2f} ({wk_pnl_pct:+.2f}%)")
    lines.append("")
    lines.append("--- Cumulative ---")
    for name, ok, display in gates:
        mark = "PASS" if ok else "FAIL"
        lines.append(f"  [{mark}] {name:14s} {display}")
    lines.append("")
    lines.append(f"Avg winner / loser:  ${avg_winner:+.2f} / ${avg_loser:+.2f}")
    lines.append(f"Mode:                {config.TASTYTRADE_ENV.upper()}  DRY_RUN={config.DRY_RUN}")
    lines.append("")
    lines.append(f"--- Go-Live Readiness: {passed} / {len(gates)} ---")
    if ready:
        lines.append("Status: READY")
    else:
        missing = [name for name, ok, _ in gates if not ok]
        lines.append("Status: NOT READY")
        lines.append(f"Failing: {', '.join(missing)}")
    return "\n".join(lines)


def main() -> None:
    print(build_report())


if __name__ == "__main__":
    main()

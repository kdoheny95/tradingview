"""CLI entry point.

Usage:
  python main.py auth        — log in to tastytrade, save session
  python main.py screen      — show candidates, no trading
  python main.py dry-run     — full pipeline, no real orders (DRY_RUN forced on)
  python main.py trade       — full pipeline, place orders (respects DRY_RUN env)
  python main.py monitor     — manage open positions
  python main.py full        — monitor + trade
  python main.py summary     — portfolio status
"""
import sys

import config
import state
from executor import execute_candidate
from monitor import print_summary, run_monitor
from screener import run_screener
from tastytrade_client import TastytradeClient


def cmd_auth():
    client = TastytradeClient()
    client.login()
    print(f"[auth] logged in to {config.TASTYTRADE_ENV}; session cached.")
    print(f"[auth] account: {client.get_account_number()}")


def cmd_screen():
    candidates = run_screener()
    print(f"\n[screen] {len(candidates)} candidate(s) above MIN_SCORE={config.MIN_SCORE}")
    for c in candidates:
        print(f"  {c.symbol} {c.direction} score={c.score} — {c.rationale}")


def cmd_trade(force_dry: bool = False):
    if force_dry:
        config.DRY_RUN = True
        print("[main] DRY_RUN forced on for this run.")
    client = TastytradeClient()
    client.login()
    candidates = run_screener()
    if not candidates:
        print("[main] no candidates above threshold.")
        return
    for c in candidates:
        result = execute_candidate(c, client)
        prefix = "✅" if result.placed else "⏭️"
        print(f"{prefix} {result.symbol}: {result.reason}")


def cmd_monitor():
    client = TastytradeClient()
    client.login()
    closed = run_monitor(client)
    if closed:
        print(f"\n[monitor] closed {len(closed)} position(s):")
        for c in closed:
            print(f"  {c['symbol']} {c['direction']}: ${c['pnl_dollars']:+.2f} "
                  f"({c['pnl_pct']:+.2f}%) [{c['exit_reason']}]")


def cmd_full():
    client = TastytradeClient()
    client.login()
    print("[full] managing existing positions...")
    run_monitor(client)
    print("\n[full] scanning for new setups...")
    candidates = run_screener()
    if not candidates:
        print("[main] no candidates above threshold.")
    else:
        for c in candidates:
            result = execute_candidate(c, client)
            prefix = "✅" if result.placed else "⏭️"
            print(f"{prefix} {result.symbol}: {result.reason}")
    print_summary()


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "full"
    try:
        if mode == "auth":
            cmd_auth()
        elif mode == "screen":
            cmd_screen()
        elif mode == "dry-run":
            cmd_trade(force_dry=True)
        elif mode == "trade":
            cmd_trade()
        elif mode == "monitor":
            cmd_monitor()
        elif mode == "summary":
            print_summary()
        elif mode == "full":
            cmd_full()
        else:
            print(f"unknown mode: {mode}")
            print(__doc__)
            sys.exit(1)
    except Exception as e:
        print(f"[main] ERROR: {type(e).__name__}: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

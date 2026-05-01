#!/bin/bash
# Daily trader run wrapper. Invoked by cron.
# Posts a run summary to ntfy, records equity snapshot, logs failed runs.
set -u
TOPIC=$(cat /root/.ntfy_topic)
cd /root/tradingview
LOG=$(mktemp)
.venv/bin/python main.py full > "$LOG" 2>&1
STATUS=$?
SUMMARY=$(.venv/bin/python main.py summary 2>&1)

# Daily equity snapshot (idempotent per local date).
.venv/bin/python -c "
import config, state, history
realized = sum(t['pnl_dollars'] for t in history.all_trades())
equity = config.NOTIONAL_ACCOUNT_SIZE + realized
history.record_equity_snapshot(equity, len(state.open_positions()), config.TASTYTRADE_ENV)
" >> "$LOG" 2>&1 || true

if [ "$STATUS" -ne 0 ]; then
  TAIL=$(tail -50 "$LOG")
  printf '%s' "$TAIL" | .venv/bin/python -c "
import history, sys
history.record_failed_run(${STATUS}, sys.stdin.read())
" >> "$LOG" 2>&1 || true
  TITLE="Trader FAILED exit=$STATUS"
else
  TITLE="Trader OK $(date +%H:%M\ %Z)"
fi

{
  echo "$SUMMARY"
  echo "----- run log (tail) -----"
  tail -30 "$LOG"
} | curl -sS -H "Title: $TITLE" --data-binary @- "https://ntfy.sh/$TOPIC" > /dev/null
rm -f "$LOG"

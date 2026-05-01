#!/bin/bash
# Friday weekly summary wrapper. Invoked by cron.
set -u
TOPIC=$(cat /root/.ntfy_topic)
cd /root/tradingview
REPORT=$(.venv/bin/python weekly_summary.py 2>&1)
TITLE="Weekly summary $(date +%Y-%m-%d)"
echo "$REPORT" | curl -sS -H "Title: $TITLE" --data-binary @- "https://ntfy.sh/$TOPIC" > /dev/null

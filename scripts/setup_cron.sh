#!/bin/bash
SCRIPT="$(cd "$(dirname "$0")" && pwd)/run_update.sh"
chmod +x "$SCRIPT"
LOG="$(cd "$(dirname "$0")/.." && pwd)/cron.log"
(crontab -l 2>/dev/null | grep -v run_update; echo "5 16 * * 1-5 $SCRIPT >> $LOG 2>&1") | crontab -
echo "cron 등록 완료:"
crontab -l | grep run_update

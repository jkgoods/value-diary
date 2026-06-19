#!/bin/bash
SCRIPT="$(cd "$(dirname "$0")" && pwd)/run_update.sh"
chmod +x "$SCRIPT"
(crontab -l 2>/dev/null | grep -v run_update; echo "35 6 * * 1-5 $SCRIPT >> /root/value-diary/cron.log 2>&1") | crontab -
echo "cron 등록 완료:"
crontab -l | grep run_update

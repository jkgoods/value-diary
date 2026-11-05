#!/bin/bash
set -e
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
cd "$(dirname "$0")/.."
git pull
"$(pwd)/.venv/bin/python" scripts/update_prices.py
git add index.html portfolio.html data/history.json
git diff --staged --quiet || (git commit -m "Auto: 현재가 갱신 $(TZ=Asia/Seoul date +%Y.%m.%d)" && git push)

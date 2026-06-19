#!/bin/bash
set -e
cd "$(dirname "$0")/.."
git pull
python3 scripts/update_prices.py
git add index.html portfolio.html
git diff --staged --quiet || (git commit -m "Auto: 현재가 갱신 $(TZ=Asia/Seoul date +%Y.%m.%d)" && git push)

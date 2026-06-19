import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

KST = timezone(timedelta(hours=9))


def price_to_date():
    """장 마감(15:30 KST) 이후면 오늘, 이전이면 어제까지 조회."""
    now = datetime.now(KST)
    close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    if now >= close:
        return now.date().strftime("%Y%m%d")
    return (now.date() - timedelta(days=1)).strftime("%Y%m%d")

try:
    from pykrx import stock as krx
except ImportError:
    print("ERROR: pykrx not installed. Run: pip install pykrx")
    sys.exit(1)

ROOT = Path(__file__).parent.parent
DATA_FILE = ROOT / "data" / "stocks.json"
INDEX_HTML = ROOT / "index.html"
PORTFOLIO_HTML = ROOT / "portfolio.html"


def get_latest_price(ticker):
    """Returns (price, date_str "YYYY.MM.DD") or (None, None)."""
    to_date = price_to_date()
    from_date = (date.fromisoformat(f"{to_date[:4]}-{to_date[4:6]}-{to_date[6:]}") - timedelta(days=7)).strftime("%Y%m%d")
    try:
        df = krx.get_market_ohlcv_by_date(from_date, to_date, ticker)
        if not df.empty:
            price_date = df.index[-1].strftime("%Y.%m.%d")
            return int(df["종가"].iloc[-1]), price_date
    except Exception as e:
        print(f"  WARN: {ticker} 조회 실패 — {e}")
    return None, None


def fmt_return(pct, valid=True):
    if not valid:
        return "—", "#ccc"
    if pct > 0:
        return f"+{pct:.1f}%", "#d00000"
    elif pct < 0:
        return f"{pct:.1f}%", "#1060c0"
    return "0.0%", "#aaa"


def bar_style(pct, valid=True):
    if not valid:
        return "width:2%;background:#ddd"
    width = max(2, min(100, int(abs(pct) * 5)))
    color = "#d00000" if pct > 0 else "#1060c0" if pct < 0 else "#ddd"
    return f"width:{width}%;background:{color}"


def main():
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    stocks = data["stocks"]
    total_invested = data["total_invested"]
    round_label = data["round"]

    results = []
    total_eval = 0
    price_date = None

    for s in stocks:
        price, pd = get_latest_price(s["ticker"])
        if price is None:
            print(f"  {s['name']} 현재가 조회 실패 — 매수가 유지")
            price = s["buy_price"]
        else:
            price_date = pd

        eval_amount = price * s["shares"]
        total_eval += eval_amount
        pct = (price - s["buy_price"]) / s["buy_price"] * 100
        # 종가 기준일이 매수일보다 이전이면 수익률 미표시
        valid = (pd is not None) and (pd.replace(".", "-") >= s["buy_date"].replace(".", "-"))
        ret_str, ret_color = fmt_return(pct, valid)

        results.append({**s, "current_price": price, "eval_amount": eval_amount,
                        "pct": pct, "ret_str": ret_str, "ret_color": ret_color, "valid": valid})
        print(f"  {s['name']} ({s['ticker']}): {price:,}원  {ret_str}")

    total_pct = (total_eval - total_invested) / total_invested * 100
    all_valid = all(r["valid"] for r in results)
    total_ret_str, total_ret_color = fmt_return(total_pct, all_valid)
    print(f"\n총 평가: {total_eval:,}원  {total_ret_str}  ({price_date} 종가 기준)")

    _update_index(results, total_invested, total_eval, total_ret_str, total_ret_color, round_label, price_date, all_valid)
    _update_portfolio(results, total_invested, total_eval, total_ret_str, total_ret_color, round_label, price_date)
    print("완료.")


def _update_index(results, total_invested, total_eval, total_ret_str, total_ret_color, round_label, price_date, all_valid):
    html = INDEX_HTML.read_text(encoding="utf-8")

    # Stats cards
    start_date = min(r["buy_date"] for r in results)
    num_stocks = len(results)
    round_num = round_label.split("·")[1].strip() if "·" in round_label else round_label
    ret_accent = total_ret_color if all_valid else "#e2e8f0"

    stats_block = (
        "<!-- STATS_CARD_START -->\n"
        f'  <div class="stat-card" id="card-start" style="--accent:#3b82f6"><div class="stat-label">매수 시작일</div><div class="stat-value">{start_date}</div><div class="stat-sub"></div></div>\n'
        f'  <div class="stat-card" style="--accent:#8b5cf6"><div class="stat-label">보유 종목</div><div class="stat-value">{num_stocks}종목</div></div>\n'
        f'  <div class="stat-card" id="card-round" style="--accent:#06b6d4"><div class="stat-label">진행 회차</div><div class="stat-value">{round_num}</div><div class="stat-sub"></div></div>\n'
        f'  <div class="stat-card" style="--accent:#f59e0b"><div class="stat-label">총 투자금</div><div class="stat-value">{total_invested:,}원</div></div>\n'
        f'  <div class="stat-card" style="--accent:#10b981"><div class="stat-label">평가금액</div><div class="stat-value">{total_eval:,}원</div></div>\n'
        f'  <div class="stat-card" style="--accent:{ret_accent}"><div class="stat-label">전체 수익률</div><div class="stat-value" style="color:{total_ret_color}">{total_ret_str}</div></div>\n'
        "  <!-- STATS_CARD_END -->"
    )

    html = re.sub(
        r"<!-- STATS_CARD_START -->.*?<!-- STATS_CARD_END -->",
        stats_block,
        html,
        flags=re.DOTALL,
    )

    items = ""
    for r in results:
        items += (
            f'      <div class="stock-item">\n'
            f'        <div class="stock-name-wrap">'
            f'<div class="sname">{r["name"]}</div>'
            f'<div class="scode">{r["ticker"]} · {r["buy_date"]} 매수</div></div>\n'
            f'        <div class="stock-bar-wrap">'
            f'<div class="stock-bar" style="{bar_style(r["pct"], r["valid"])}"></div></div>\n'
            f'        <div class="stock-right" style="color:{r["ret_color"]}">{r["ret_str"]}</div>\n'
            f'      </div>\n'
        )

    date_note = f' &nbsp;<span style="font-size:11px;color:#ccc">{price_date} 종가 기준</span>' if price_date else ""
    summary = (
        f'총 투자금 {total_invested:,}원 · 평가 {total_eval:,}원 · '
        f'{total_ret_str} · 5종목 · {round_label}{date_note}'
    )

    new_block = (
        "<!-- PORTFOLIO_STRIP_START -->\n"
        "    <div class=\"stock-list\">\n"
        f"{items}"
        "    </div>\n"
        f'    <div class="portfolio-summary">{summary}</div>\n'
        "    <!-- PORTFOLIO_STRIP_END -->"
    )

    html = re.sub(
        r"<!-- PORTFOLIO_STRIP_START -->.*?<!-- PORTFOLIO_STRIP_END -->",
        new_block,
        html,
        flags=re.DOTALL,
    )
    INDEX_HTML.write_text(html, encoding="utf-8")


def _update_portfolio(results, total_invested, total_eval, total_ret_str, total_ret_color, round_label, price_date):
    html = PORTFOLIO_HTML.read_text(encoding="utf-8")

    date_note = f' &nbsp;·&nbsp; <span style="font-size:11px;color:#ccc">{price_date} 종가 기준</span>' if price_date else ""
    new_summary = (
        "<!-- SUMMARY_START -->\n"
        "  <div class=\"summary-row\">\n"
        f'    총 투자 <span class="highlight">{total_invested:,}원</span> &nbsp;·&nbsp; '
        f'평가금액 <span class="highlight">{total_eval:,}원</span> &nbsp;·&nbsp; '
        f'수익률 <span style="color:{total_ret_color};font-weight:600">{total_ret_str}</span> &nbsp;·&nbsp; '
        f'보유 <span class="highlight">{len(results)}종목</span>{date_note}\n'
        "  </div>\n"
        "  <!-- SUMMARY_END -->"
    )

    html = re.sub(
        r"<!-- SUMMARY_START -->.*?<!-- SUMMARY_END -->",
        new_summary,
        html,
        flags=re.DOTALL,
    )

    rows = ""
    for r in results:
        rows += (
            f"        <tr>\n"
            f'          <td><div class="sname">{r["name"]}</div>'
            f'<div class="scode">{r["ticker"]}</div></td>\n'
            f'          <td><span class="buy-date">{r["buy_date"]}</span></td>\n'
            f"          <td>{r['buy_price']:,}원</td>\n"
            f"          <td>{r['shares']}주</td>\n"
            f"          <td>{r['buy_amount']:,}원</td>\n"
            f'          <td style="color:{r["ret_color"]}">{r["ret_str"]}</td>\n'
            f"        </tr>\n"
        )

    new_tbody = (
        "<!-- TBODY_START -->\n"
        "      <tbody>\n"
        f"{rows}"
        "      </tbody>\n"
        "      <!-- TBODY_END -->"
    )

    html = re.sub(
        r"<!-- TBODY_START -->.*?<!-- TBODY_END -->",
        new_tbody,
        html,
        flags=re.DOTALL,
    )
    PORTFOLIO_HTML.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()

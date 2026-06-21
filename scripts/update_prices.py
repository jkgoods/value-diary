import json
import math
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
HISTORY_FILE = ROOT / "data" / "history.json"
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
        return "—", "#8a8f98"
    if pct > 0:
        return f"+{pct:.1f}%", "#df2c2c"
    elif pct < 0:
        return f"{pct:.1f}%", "#2563eb"
    return "0.0%", "#8a8f98"


def bar_style(pct, valid=True):
    if not valid:
        return "width:2%;background:#e5e7eb"
    width = max(2, min(100, int(abs(pct) * 5)))
    color = "#df2c2c" if pct > 0 else "#2563eb" if pct < 0 else "#e5e7eb"
    return f"width:{width}%;background:{color}"


def main():
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    stocks = data["stocks"]
    total_invested = sum(s["buy_amount"] for s in stocks)

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
        print(f"  [{s.get('round_label','?')}] {s['name']} ({s['ticker']}): {price:,}원  {ret_str}")

    total_pct = (total_eval - total_invested) / total_invested * 100
    all_valid = all(r["valid"] for r in results)
    total_ret_str, total_ret_color = fmt_return(total_pct, all_valid)

    # 최신 회차 라벨 (round 번호 최대값 기준)
    latest_round = max(r.get("round", 1) for r in results)
    round_label = next(
        r["round_label"] for r in results if r.get("round", 1) == latest_round
    )
    print(f"\n총 평가: {total_eval:,}원  {total_ret_str}  ({price_date} 종가 기준)")

    # 히스토리 업데이트 — 실제 거래일(price_date) 기준으로 중복 방지
    history_data = json.loads(HISTORY_FILE.read_text(encoding="utf-8")) if HISTORY_FILE.exists() else {"history": []}
    existing = {h["date"] for h in history_data["history"]}
    if price_date and price_date not in existing:
        history_data["history"].append({
            "date": price_date,
            "day": len(history_data["history"]) + 1,
            "return_pct": round(total_pct, 2) if all_valid else None,
        })
        HISTORY_FILE.write_text(json.dumps(history_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  히스토리 추가: {price_date} {total_pct:+.2f}%")
    elif price_date:
        print(f"  히스토리 스킵: {price_date} 이미 존재 (주말·공휴일 이후 재실행)")

    _update_index(results, total_invested, total_eval, total_ret_str, total_ret_color, round_label, price_date, all_valid, history_data)
    _update_portfolio(results, total_invested, total_eval, total_ret_str, total_ret_color, round_label, price_date, history_data)
    print("완료.")


def _build_index_trend_html(history_data):
    """index.html 수익률 추세 차트.
    30일 이내: X축 D+1~D+30 고정, 데이터가 왼쪽부터 채워짐.
    30일 초과: 전체 기간 표시, 최신 데이터가 맨 오른쪽.
    """
    WINDOW = 30
    history = history_data.get("history", [])
    valid = [h for h in history if h.get("return_pct") is not None]

    if history:
        start_str = history[0]["date"].replace(".", "-")
        today_kst = datetime.now(KST).date()
        days_held = (today_kst - date.fromisoformat(start_str)).days + 1
    else:
        days_held = 1

    is_early = days_held <= WINDOW
    last_r = valid[-1]["return_pct"] if valid else None
    color = "#df2c2c" if (last_r is not None and last_r > 0.05) else \
            "#2563eb" if (last_r is not None and last_r < -0.05) else "#8a8f98"
    border_color = color if valid else "#e5e7eb"

    if not valid:
        return (
            "<!-- TREND_CHART_START -->\n"
            f'  <div class="trend-chart-section" style="border-left:3px solid {border_color};padding-left:16px">\n'
            '    <div class="trend-chart-header">\n'
            '      <span class="trend-chart-label">수익률 추세</span>\n'
            f'      <span class="trend-chart-badge">D+{days_held}</span>\n'
            '    </div>\n'
            '    <p style="font-size:13px;color:#ccc;padding:16px 0">첫 종가 반영 후 표시됩니다.</p>\n'
            '  </div>\n'
            "  <!-- TREND_CHART_END -->"
        )

    W, H = 600, 130
    PL, PR, PT, PB = 44, 20, 22, 30
    CW = W - PL - PR
    CH = H - PT - PB

    rv = [h["return_pct"] for h in valid]
    r_min = min(min(rv), 0.0)
    r_max = max(max(rv), 0.0)
    span = max(r_max - r_min, 2.0)
    y_min_v = r_min - span * 0.22
    y_max_v = r_max + span * 0.22
    y_span = y_max_v - y_min_v

    def to_y(r):
        return PT + CH * (y_max_v - r) / y_span

    zero_y = to_y(0.0)

    # X축 계산
    if is_early:
        # 30일 고정 창: D+1이 맨 왼쪽, D+30이 맨 오른쪽
        def to_x(day_num):
            return PL + CW * (day_num - 1) / (WINDOW - 1)
    else:
        # 전체 기간: 첫 데이터부터 최신까지
        min_day = valid[0]["day"]
        max_day = valid[-1]["day"]
        day_span = max(max_day - min_day, 1)
        def to_x(d):
            return PL + CW * (d - min_day) / day_span

    pts = [(to_x(h["day"]), to_y(h["return_pct"])) for h in valid]
    last_x, last_y = pts[-1]
    n = len(valid)

    # Y축 그리드
    raw_step = span / 2.0
    grid_step = next((s for s in [0.5, 1, 2, 5, 10] if s >= raw_step), 10)
    grids = []
    gv = math.floor(y_min_v / grid_step) * grid_step
    while gv <= math.ceil(y_max_v / grid_step) * grid_step + 0.001:
        gy = to_y(gv)
        if PT - 1 <= gy <= PT + CH + 1:
            grids.append((round(gv, 4), gy))
        gv = round(gv + grid_step, 6)

    els = []

    # 30일 이내: 미래 영역 (매우 연한 배경 + 점선 구분선)
    if is_early:
        fw = PL + CW - last_x
        if fw > 2:
            els.append(
                f'<rect x="{last_x:.1f}" y="{PT}" width="{fw:.1f}" height="{CH}" '
                f'fill="#f5f5f5"/>'
            )
        els.append(
            f'<line x1="{last_x:.1f}" y1="{PT}" x2="{last_x:.1f}" y2="{PT+CH}" '
            f'stroke="#d8d8d8" stroke-width="1" stroke-dasharray="4,3"/>'
        )

    # Y축 그리드라인
    for gv, gy in grids:
        is_zero = abs(gv) < 0.001
        if is_zero:
            els.append(
                f'<line x1="{PL}" y1="{gy:.1f}" x2="{PL+CW}" y2="{gy:.1f}" '
                f'stroke="#c8c8c8" stroke-width="1.5"/>'
            )
            els.append(
                f'<text x="{PL-6}" y="{gy+4:.1f}" text-anchor="end" '
                f'font-size="10" fill="#bbb">0%</text>'
            )
        else:
            els.append(
                f'<line x1="{PL}" y1="{gy:.1f}" x2="{PL+CW}" y2="{gy:.1f}" '
                f'stroke="#ececec" stroke-width="1" stroke-dasharray="3,4"/>'
            )
            els.append(
                f'<text x="{PL-6}" y="{gy+4:.1f}" text-anchor="end" '
                f'font-size="10" fill="#ddd">{gv:+.0f}%</text>'
            )

    # 필 영역 + 라인 (2점 이상)
    if n >= 2:
        fill_pts = (
            f"{pts[0][0]:.1f},{zero_y:.1f} "
            + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
            + f" {last_x:.1f},{zero_y:.1f}"
        )
        els.append(f'<polygon points="{fill_pts}" fill="{color}" fill-opacity="0.15"/>')
        path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        els.append(
            f'<path d="{path_d}" fill="none" stroke="{color}" stroke-width="2.5" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
        )

    # 현재 값 도트 (흰 링 + 컬러)
    els.append(f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="8" fill="white"/>')
    els.append(f'<circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="5" fill="{color}"/>')

    # 현재 값 레이블 — 도트 옆에 크게
    if last_x > PL + CW - 70:
        la, lx = "end", last_x - 14
    else:
        la, lx = "start", last_x + 14
    els.append(
        f'<text x="{lx:.1f}" y="{last_y - 5:.1f}" text-anchor="{la}" '
        f'font-size="15" fill="{color}" font-weight="700">{last_r:+.1f}%</text>'
    )

    # X축 레이블
    if is_early:
        els.append(
            f'<text x="{PL}" y="{H}" text-anchor="start" font-size="10" fill="#ccc">D+1</text>'
        )
        els.append(
            f'<text x="{PL+CW}" y="{H}" text-anchor="end" font-size="10" fill="#ccc">D+{WINDOW}</text>'
        )
        # 현재 날짜 레이블 (도트 아래, 충분한 공간이 있을 때)
        if last_x > PL + 24:
            cur_date = valid[-1]["date"][5:]
            els.append(
                f'<text x="{last_x:.1f}" y="{H}" text-anchor="middle" '
                f'font-size="10" fill="{color}">{cur_date}</text>'
            )
    else:
        first_date = valid[0]["date"][5:]
        last_date = valid[-1]["date"][5:]
        els.append(
            f'<text x="{PL}" y="{H}" text-anchor="start" font-size="10" fill="#ccc">{first_date}</text>'
        )
        els.append(
            f'<text x="{PL+CW}" y="{H}" text-anchor="end" font-size="10" fill="#ccc">{last_date}</text>'
        )

    svg = (
        f'<svg width="100%" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" '
        'style="overflow:visible;display:block">\n'
        + "".join(f"  {e}\n" for e in els)
        + "</svg>"
    )

    return (
        "<!-- TREND_CHART_START -->\n"
        f'  <div class="trend-chart-section" style="border-left:3px solid {border_color};padding-left:16px">\n'
        '    <div class="trend-chart-header">\n'
        '      <span class="trend-chart-label">수익률 추세</span>\n'
        f'      <span class="trend-chart-badge">D+{days_held}</span>\n'
        '    </div>\n'
        f'    {svg}\n'
        '  </div>\n'
        "  <!-- TREND_CHART_END -->"
    )


def _update_index(results, total_invested, total_eval, total_ret_str, total_ret_color, round_label, price_date, all_valid, history_data):
    html = INDEX_HTML.read_text(encoding="utf-8")

    # Stats cards
    start_date = min(r["buy_date"] for r in results)
    num_stocks = len(results)
    round_num = round_label.split("·")[1].strip() if "·" in round_label else round_label
    ret_accent = total_ret_color if all_valid else "#e2e8f0"

    stats_block = (
        "<!-- STATS_CARD_START -->\n"
        f'  <div class="stat-card" id="card-start" style="--accent:#3b82f6">\n'
        f'    <div class="stat-card-header"><span class="stat-label">매수 시작일</span><svg class="stat-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="4" rx="2" ry="2"/><line x1="16" x2="16" y1="2" y2="6"/><line x1="8" x2="8" y1="2" y2="6"/><line x1="3" x2="21" y1="10" y2="10"/></svg></div>\n'
        f'    <div class="stat-value">{start_date}</div>\n'
        f'    <div class="stat-sub"></div>\n'
        f'  </div>\n'
        f'  <div class="stat-card" style="--accent:#8b5cf6">\n'
        f'    <div class="stat-card-header"><span class="stat-label">보유 종목</span><svg class="stat-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/><rect width="20" height="14" x="2" y="6" rx="2"/></svg></div>\n'
        f'    <div class="stat-value">{num_stocks}종목</div>\n'
        f'    <div class="stat-sub"></div>\n'
        f'  </div>\n'
        f'  <div class="stat-card" id="card-round" style="--accent:#06b6d4">\n'
        f'    <div class="stat-card-header"><span class="stat-label">진행 회차</span><svg class="stat-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275Z"/></svg></div>\n'
        f'    <div class="stat-value">{round_num}</div>\n'
        f'    <div class="stat-sub"></div>\n'
        f'  </div>\n'
        f'  <div class="stat-card" style="--accent:#f59e0b">\n'
        f'    <div class="stat-card-header"><span class="stat-label">총 투자금</span><svg class="stat-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12V7H5a2 2 0 0 1 0-4h14v4"/><path d="M3 5v14a2 2 0 0 0 2 2h16v-5"/><path d="M16 12h5v4h-5z"/></svg></div>\n'
        f'    <div class="stat-value">{total_invested:,}원</div>\n'
        f'    <div class="stat-sub"></div>\n'
        f'  </div>\n'
        f'  <div class="stat-card" style="--accent:#10b981">\n'
        f'    <div class="stat-card-header"><span class="stat-label">평가금액</span><svg class="stat-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" x2="18" y1="20" y2="10"/><line x1="12" x2="12" y1="20" y2="4"/><line x1="6" x2="6" y1="20" y2="14"/></svg></div>\n'
        f'    <div class="stat-value">{total_eval:,}원</div>\n'
        f'    <div class="stat-sub"></div>\n'
        f'  </div>\n'
        f'  <div class="stat-card" style="--accent:{ret_accent}">\n'
        f'    <div class="stat-card-header"><span class="stat-label">전체 수익률</span><svg class="stat-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg></div>\n'
        f'    <div class="stat-value" style="color:{total_ret_color}">{total_ret_str}</div>\n'
        f'    <div class="stat-sub"></div>\n'
        f'  </div>\n'
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

    trend_html = _build_index_trend_html(history_data)
    html = re.sub(
        r"<!-- TREND_CHART_START -->.*?<!-- TREND_CHART_END -->",
        trend_html,
        html,
        flags=re.DOTALL,
    )

    INDEX_HTML.write_text(html, encoding="utf-8")


def _build_trend_html(history_data):
    """수익률 추세 SVG 스파크라인 섹션 HTML 생성."""
    history = history_data.get("history", [])
    valid = [h for h in history if h.get("return_pct") is not None]

    # 보유 기간 (캘린더 기준)
    if history:
        start_str = history[0]["date"].replace(".", "-")
        today_kst = datetime.now(KST).date()
        days_held = (today_kst - date.fromisoformat(start_str)).days + 1
    else:
        days_held = 1

    label = f"수익률 추세 — 보유 {days_held}일째"

    if days_held <= 7:
        note = "매수 후 첫 주. 단기 변동은 무시해도 됩니다."
    elif days_held <= 30:
        note = "한 달을 향해 가는 중. 시장 노이즈에서 벗어나는 중입니다."
    elif days_held <= 90:
        note = "2~3개월 차. 마법공식 종목군의 평균회귀 효과가 나타나기 시작합니다."
    elif days_held <= 180:
        note = "반년 돌파. 통계적으로 마법공식 수익률이 가시화되는 시점입니다."
    elif days_held <= 270:
        note = "후반부. 조금만 더 버티면 1년입니다."
    else:
        note = "매도 시점이 다가오고 있습니다. 원칙대로 준비하세요."

    if not valid:
        return (
            "<!-- TREND_START -->\n"
            "  <div class=\"section\">\n"
            f"    <div class=\"section-label\">{label}</div>\n"
            "    <p class=\"trend-note\">데이터가 쌓이면 이 자리에 추세 차트가 표시됩니다.</p>\n"
            "  </div>\n"
            "  <!-- TREND_END -->"
        )

    W, H = 600, 108
    PL, PR, PT, PB = 36, 14, 14, 24

    returns = [h["return_pct"] for h in valid]
    r_min = min(min(returns), 0.0)
    r_max = max(max(returns), 0.0)
    span = max(r_max - r_min, 1.5)
    y_min = r_min - span * 0.2
    y_max = r_max + span * 0.2
    y_span = y_max - y_min

    n = len(valid)

    def to_x(i):
        if n == 1:
            return PL + (W - PL - PR) * 0.5
        return PL + (W - PL - PR) * i / (n - 1)

    def to_y(r):
        return PT + (H - PT - PB) * (y_max - r) / y_span

    zero_y = to_y(0.0)
    pts = [(to_x(i), to_y(h["return_pct"])) for i, h in enumerate(valid)]
    path_d = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts)

    last_x, last_y = pts[-1]
    last_r = returns[-1]
    color = "#df2c2c" if last_r > 0.05 else "#2563eb" if last_r < -0.05 else "#8a8f98"

    fill_pts = (
        f"{pts[0][0]:.1f},{zero_y:.1f} "
        + " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        + f" {pts[-1][0]:.1f},{zero_y:.1f}"
    )

    fd = valid[0]["date"][5:]
    ld = valid[-1]["date"][5:]
    lbl_anchor = "end" if last_x > W - PR - 54 else "start"
    lbl_x = last_x - 8 if lbl_anchor == "end" else last_x + 8

    svg = "\n".join([
        f'<svg width="100%" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" style="overflow:visible;display:block">',
        f'  <polygon points="{fill_pts}" fill="{color}" fill-opacity="0.06"/>',
        f'  <line x1="{PL}" y1="{zero_y:.1f}" x2="{W-PR}" y2="{zero_y:.1f}" stroke="#e8e8e8" stroke-width="1"/>',
        f'  <text x="{PL-4}" y="{zero_y+4:.1f}" text-anchor="end" font-size="10" fill="#ccc">0%</text>',
        f'  <path d="{path_d}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>',
        f'  <circle cx="{last_x:.1f}" cy="{last_y:.1f}" r="3" fill="{color}"/>',
        f'  <text x="{lbl_x:.1f}" y="{last_y+4:.1f}" text-anchor="{lbl_anchor}" font-size="11" fill="{color}" font-weight="600">{last_r:+.1f}%</text>',
        f'  <text x="{PL}" y="{H}" text-anchor="start" font-size="10" fill="#ccc">{fd}</text>',
        f'  <text x="{W-PR}" y="{H}" text-anchor="end" font-size="10" fill="#ccc">{ld}</text>',
        '</svg>',
    ])

    return (
        "<!-- TREND_START -->\n"
        "  <div class=\"section\">\n"
        f"    <div class=\"section-label\">{label}</div>\n"
        f"    {svg}\n"
        f"    <p class=\"trend-note\">{note}</p>\n"
        "  </div>\n"
        "  <!-- TREND_END -->"
    )


def _update_portfolio(results, total_invested, total_eval, total_ret_str, total_ret_color, round_label, price_date, history_data):
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

    # 회차별 그룹 렌더링
    from itertools import groupby as _groupby
    sorted_results = sorted(results, key=lambda r: r.get("round", 1))
    thead = (
        "        <thead><tr>"
        "<th>종목</th><th>매수일</th><th>매수가</th>"
        "<th>주수</th><th>매수금액</th><th>수익률</th>"
        "</tr></thead>\n"
    )
    groups_html = ""
    for rnum, grp in _groupby(sorted_results, key=lambda r: r.get("round", 1)):
        grp = list(grp)
        rl = grp[0].get("round_label", f"{rnum}회차")
        sd = grp[0].get("sell_date", "")
        sell_note = f' <span class="round-sell-date">→ {sd} 매도 예정</span>' if sd else ""
        rows = ""
        for r in grp:
            rows += (
                f"          <tr>\n"
                f'            <td><div class="sname">{r["name"]}</div>'
                f'<div class="scode">{r["ticker"]}</div></td>\n'
                f'            <td><span class="buy-date">{r["buy_date"]}</span></td>\n'
                f"            <td>{r['buy_price']:,}원</td>\n"
                f"            <td>{r['shares']}주</td>\n"
                f"            <td>{r['buy_amount']:,}원</td>\n"
                f'            <td style="color:{r["ret_color"]}">{r["ret_str"]}</td>\n'
                f"          </tr>\n"
            )
        groups_html += (
            f'      <div class="round-group">\n'
            f'        <div class="round-group-label">{rl}{sell_note}</div>\n'
            f'        <table class="stock-table">\n'
            f"{thead}"
            f"          <tbody>\n{rows}          </tbody>\n"
            f"        </table>\n"
            f"      </div>\n"
        )

    new_holdings = (
        "<!-- HOLDINGS_START -->\n"
        '  <div class="section">\n'
        '    <div class="section-label">보유 종목</div>\n'
        f"{groups_html}"
        "  </div>\n"
        "  <!-- HOLDINGS_END -->"
    )

    html = re.sub(
        r"<!-- HOLDINGS_START -->.*?<!-- HOLDINGS_END -->",
        new_holdings,
        html,
        flags=re.DOTALL,
    )

    PORTFOLIO_HTML.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    main()

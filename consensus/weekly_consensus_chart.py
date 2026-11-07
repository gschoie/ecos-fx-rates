# -*- coding: utf-8 -*-
"""커버리지 영업이익 컨센서스 추이 — 위클리에 바로 붙여넣는 PNG 생성기.

데이터는 GS-DB2 저장소의 KOSPI200 컨센서스 트래커(kospi_consensus/data/consensus.db,
매주 금·토 스냅샷)를 그대로 읽는다. 종목별 작은 차트(소형 다중 차트)에
분기 컨센 2개(예: 4Q26·1Q27 영업이익)의 스냅샷별 추이를 그린다.

  - 컨센서스_추이_분기.png : 분기 영업이익 컨센 (기본: 최신 스냅샷의 마지막 2개 분기)
  - 컨센서스_추이_연간.png : 연간 영업이익 컨센 (기본: 올해E·내년E)

실행:
    python consensus/weekly_consensus_chart.py                  # GS-DB2에서 DB 내려받아 둘 다 생성
    python consensus/weekly_consensus_chart.py --db 경로/consensus.db
    python consensus/weekly_consensus_chart.py --mode quarter --periods 2026.12,2027.03
    python consensus/weekly_consensus_chart.py --since 2026-08-01

종목·순서·섹터는 아래 COMPANIES 만 고치면 된다. (섹터, 표시명, 종목코드)
"""

import argparse
import os
import sqlite3
import sys
import tempfile
import urllib.request
from datetime import timedelta

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter, MaxNLocator
import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# =========================================================================
# 종목 구성 — 이 순서대로 왼쪽→오른쪽, 위→아래로 배치된다.
# 섹터가 바뀌면 새 줄에서 시작한다(같은 섹터 블록은 같은 배경색).
# '조기'(조선기자재)는 조선 블록에 같이 묶는다 → SECTOR_BLOCK 참고.
# =========================================================================
COMPANIES = [
    ("조선", "HD한국조선해양", "009540"),
    ("조선", "HD현대중공업", "329180"),
    ("조선", "HD현대마린엔진", "071970"),
    ("조선", "HD현대마린솔루션", "443060"),
    ("조선", "삼성중공업", "010140"),
    ("조선", "한화오션", "042660"),
    ("조기", "한화엔진", "082740"),
    ("조선", "대한조선", "439260"),
    ("조기", "한국카본", "017960"),
    ("방산", "한화에어로스페이스", "012450"),
    ("방산", "한화시스템", "272210"),
    ("방산", "한국항공우주", "047810"),
    ("방산", "LIG D&A", "079550"),
    ("방산", "현대로템", "064350"),
    ("건기", "두산밥캣", "241560"),
    ("건기", "HD건설기계", "267270"),
]

# 섹터 → 배치 블록(같은 블록이면 줄을 이어 쓴다)
SECTOR_BLOCK = {"조선": "조선", "조기": "조선", "방산": "방산", "건기": "건기"}
# 블록 배경색(옅게) · 섹터 칩 색(진하게)
BLOCK_BG = {"조선": "#EEF6E4", "방산": "#F5EFE6", "건기": "#E9F1FA"}
CHIP = {"조선": "#8CC63F", "조기": "#8CC63F", "방산": "#B79C7E", "건기": "#9DC3E6"}

NCOLS = 5
PANEL_W_IN = 2.25
PANEL_H_IN = 1.95
DPI = 220

LINE1 = "#1E9BD7"   # 첫 번째 기간(파랑, 예: 4Q26)
LINE2 = "#111111"   # 두 번째 기간(검정, 예: 1Q27)
ARROW = "#E46C0A"   # 제목 앞 ▶
GRID = "#D9D9D9"
TEXT = "#222222"
MUTED = "#7F7F7F"
UP = "#D62728"
DOWN = "#1F5FBF"

CHANGE_DAYS = 28    # 범례 괄호 안 변화율: 약 1개월 전 스냅샷 대비

DB_URL = ("https://raw.githubusercontent.com/gschoie/GS-DB2/main/"
          "kospi_consensus/data/consensus.db")
OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "consensus")
FILES = {"quarter": "컨센서스_추이_분기.png", "annual": "컨센서스_추이_연간.png"}


# =========================================================================
# 폰트
# =========================================================================
def setup_font():
    wanted = ["Malgun Gothic", "NanumGothic", "NanumBarunGothic", "AppleGothic",
              "Noto Sans CJK KR", "Noto Sans KR", "WenQuanYi Zen Hei"]
    have = {f.name for f in font_manager.fontManager.ttflist}
    for name in wanted:
        if name in have:
            plt.rcParams["font.family"] = name
            break
    else:
        print("⚠️ 한글 폰트를 찾지 못했습니다 (fonts-nanum 설치 권장). 글자가 깨질 수 있습니다.")
    plt.rcParams["axes.unicode_minus"] = False


# =========================================================================
# 데이터
# =========================================================================
def get_db(path):
    if path:
        return path
    dst = os.path.join(tempfile.gettempdir(), "kospi_consensus.db")
    print(f"컨센서스 DB 내려받는 중… {DB_URL}")
    urllib.request.urlretrieve(DB_URL, dst)
    return dst


def load(db_path, kind):
    codes = [c for _, _, c in COMPANIES]
    con = sqlite3.connect(db_path)
    q = ("SELECT snapshot_date, code, period, op_profit FROM consensus_snapshots "
         f"WHERE kind=? AND code IN ({','.join('?' * len(codes))})")
    df = pd.read_sql(q, con, params=[kind, *codes])
    con.close()
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"])
    return df


def pick_periods(df, kind):
    """기본 기간 2개. 분기: 최신 스냅샷에 있는 마지막 2개 분기(당분기 다음·그다음),
    연간: 최신 스냅샷의 앞 2개 연도(올해E·내년E)."""
    last = df[df.snapshot_date == df.snapshot_date.max()]
    periods = sorted(last.period.dropna().unique())
    return periods[-2:] if kind == "quarter" else periods[:2]


def period_label(p, kind):
    y, m = p.split(".")
    if kind == "quarter":
        return f"{(int(m) - 1) // 3 + 1}Q{y[2:]}"
    return f"{y}E"


# =========================================================================
# 그리기
# =========================================================================
def layout_rows():
    """[(블록, [회사, ...]), ...] — 블록이 바뀌면 새 줄, NCOLS 넘치면 줄바꿈."""
    rows = []
    for sec, name, code in COMPANIES:
        block = SECTOR_BLOCK.get(sec, sec)
        if not rows or rows[-1][0] != block or len(rows[-1][1]) >= NCOLS:
            rows.append((block, []))
        rows[-1][1].append((sec, name, code))
    return rows


def change_text(s):
    """마지막 값과 약 1개월 전(없으면 첫 스냅샷) 값 비교."""
    s = s.dropna()
    if len(s) < 2:
        return None, None
    last_d = s.index[-1]
    base = s[s.index <= last_d - timedelta(days=CHANGE_DAYS)]
    b = base.iloc[-1] if len(base) else s.iloc[0]
    v = s.iloc[-1]
    if b == 0 or (b < 0) != (v < 0):
        return None, None
    pct = (v / b - 1) * 100 if b > 0 else -(v / b - 1) * 100
    if abs(pct) < 0.05:
        return "0.0%", MUTED
    return f"{pct:+.1f}%", (UP if pct > 0 else DOWN)


def draw_panel(ax, title, sec, data, periods, kind, xlim):
    ax.set_facecolor("white")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("#9E9E9E")
        ax.spines[sp].set_linewidth(0.6)
    ax.grid(axis="y", color=GRID, linewidth=0.4)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=5.6, length=2, width=0.5, colors="#444444", pad=1.5)

    # 제목: ▶ 회사명  [섹터칩]
    ax.text(-0.02, 1.30, "▶", transform=ax.transAxes, fontsize=8.5, color=ARROW,
            ha="left", va="bottom")
    ax.text(0.07, 1.30, title, transform=ax.transAxes, fontsize=8.6, color=TEXT,
            fontweight="bold", ha="left", va="bottom")
    ax.text(1.0, 1.31, f" {sec} ", transform=ax.transAxes, fontsize=5.6, color="white",
            fontweight="bold", ha="right", va="bottom",
            bbox=dict(boxstyle="round,pad=0.25", fc=CHIP.get(sec, MUTED), ec="none"))
    ax.text(-0.03, 1.135, "(억원)", transform=ax.transAxes, fontsize=5.4, color=MUTED,
            ha="right", va="center")

    has_any = False
    for i, (p, color) in enumerate(zip(periods, (LINE1, LINE2))):
        s = data.get(p)
        label = period_label(p, kind)
        ly = 1.135 - i * 0.105
        ax.plot([0.20, 0.30], [ly, ly], transform=ax.transAxes, color=color,
                linewidth=1.3, clip_on=False, solid_capstyle="butt")
        if s is None or s.dropna().empty:
            ax.text(0.33, ly, f"{label} OP  n/a", transform=ax.transAxes,
                    fontsize=5.6, color=MUTED, va="center", ha="left")
            continue
        has_any = True
        s = s.dropna()
        ax.plot(s.index, s.values, color=color, linewidth=1.25, drawstyle="steps-post",
                zorder=3 + (1 - i))
        ax.plot(s.index[-1], s.values[-1], "o", color=color, markersize=2.2, zorder=5)
        ax.text(0.33, ly, f"{label} OP", transform=ax.transAxes,
                fontsize=5.6, color=TEXT, va="center", ha="left")
        ax.text(0.76, ly, f"{s.iloc[-1]:,.0f}", transform=ax.transAxes,
                fontsize=5.6, color=TEXT, va="center", ha="right", fontweight="bold")
        chg, ccol = change_text(s)
        if chg:
            ax.text(0.98, ly, chg, transform=ax.transAxes, fontsize=5.6, color=ccol,
                    va="center", ha="right", fontweight="bold")

    ax.set_xlim(*xlim)
    span = (xlim[1] - xlim[0]).days
    if span > 150:
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=max(1, span // 150)))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%y.%m"))
    else:
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=3, maxticks=5))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))

    if not has_any:
        ax.set_yticks([])
        ax.text(0.5, 0.5, "컨센서스 미수집", transform=ax.transAxes, fontsize=7,
                color=MUTED, ha="center", va="center")
        return

    vals = pd.concat([data[p].dropna() for p in periods if p in data])
    lo, hi = vals.min(), vals.max()
    pad = max((hi - lo) * 0.18, abs(hi) * 0.06, 1)
    ymin = lo - pad
    if lo >= 0 and ymin < 0:
        ymin = 0
    ax.set_ylim(ymin, hi + pad)


def render(df, kind, periods, since, path, asof):
    if since:
        df = df[df.snapshot_date >= pd.Timestamp(since)]
    df = df[df.period.isin(periods)]
    if df.empty:
        print(f"⚠️ {kind}: {periods} 데이터가 없습니다 — 건너뜀")
        return
    x0, x1 = df.snapshot_date.min(), df.snapshot_date.max()
    xpad = max(timedelta(days=1), (x1 - x0) * 0.03)
    xlim = (x0 - xpad, x1 + xpad)

    rows = layout_rows()
    nrows = len(rows)
    fig_w = NCOLS * PANEL_W_IN + 0.2
    foot_in = 0.42
    fig_h = nrows * PANEL_H_IN + foot_in
    fig = plt.figure(figsize=(fig_w, fig_h), dpi=DPI)

    # 패널 박스 안 여백(inch): 왼쪽 y축 라벨, 위 제목·범례, 아래 x축 라벨
    L, R, T, B = 0.46, 0.10, 0.58, 0.26
    for r, (block, items) in enumerate(rows):
        y_top = fig_h - r * PANEL_H_IN
        # 블록 배경(회사 수만큼만)
        bx = 0.1 / fig_w
        fig.patches.append(Rectangle(
            (bx, (y_top - PANEL_H_IN + 0.03) / fig_h),
            (len(items) * PANEL_W_IN) / fig_w, (PANEL_H_IN - 0.06) / fig_h,
            transform=fig.transFigure, facecolor=BLOCK_BG.get(block, "#F2F2F2"),
            edgecolor="none", zorder=-10))
        for c, (sec, name, code) in enumerate(items):
            x_left = 0.1 + c * PANEL_W_IN
            ax = fig.add_axes([
                (x_left + L) / fig_w,
                (y_top - PANEL_H_IN + B) / fig_h,
                (PANEL_W_IN - L - R) / fig_w,
                (PANEL_H_IN - T - B) / fig_h,
            ])
            sub = df[df.code == code]
            data = {p: sub[sub.period == p].set_index("snapshot_date")["op_profit"].sort_index()
                    for p in periods}
            draw_panel(ax, name, sec, data, periods, kind, xlim)

    labels = " · ".join(period_label(p, kind) for p in periods)
    what = "분기" if kind == "quarter" else "연간"
    fig.text(0.1 / fig_w, 0.30 / fig_h,
             f"주: {what} 영업이익 컨센서스({labels}) 주간 스냅샷 추이. "
             f"OP=영업이익, 범례 숫자는 최신 컨센(억원), 오른쪽 %는 약 1개월 전 스냅샷 대비 변화율"
             f"(수집 기간이 그보다 짧으면 첫 스냅샷 대비)",
             fontsize=6, color=MUTED, ha="left", va="center")
    fig.text(0.1 / fig_w, 0.13 / fig_h,
             f"자료: 네이버증권(WiseReport) 컨센서스, KOSPI200 컨센서스 트래커 · 기준일 {asof:%Y-%m-%d}",
             fontsize=6, color=MUTED, ha="left", va="center")

    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=DPI, facecolor="white")
    plt.close(fig)
    print(f"저장: {path}  ({labels})")


# =========================================================================
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", help="consensus.db 경로 (없으면 GS-DB2 main에서 내려받음)")
    ap.add_argument("--mode", choices=["quarter", "annual", "both"], default="both")
    ap.add_argument("--periods", help="기간 직접 지정(쉼표 2개), 예: 2026.12,2027.03 "
                                      "(--mode quarter/annual 하나일 때)")
    ap.add_argument("--since", help="이 날짜 이후 스냅샷만 (YYYY-MM-DD)")
    ap.add_argument("--out", default=OUTPUT_DIR, help="출력 폴더")
    args = ap.parse_args()

    setup_font()
    db = get_db(args.db)
    modes = ["quarter", "annual"] if args.mode == "both" else [args.mode]
    for kind in modes:
        df = load(db, kind)
        if df.empty:
            print(f"⚠️ {kind}: 데이터 없음")
            continue
        periods = (args.periods.split(",") if args.periods and args.mode != "both"
                   else pick_periods(df, kind))
        asof = df.snapshot_date.max()
        render(df, kind, periods, args.since, os.path.join(args.out, FILES[kind]), asof)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""커버리지 영업이익 컨센서스 추이 — 위클리에 바로 붙여넣는 PNG 생성기.

KOSPI200 컨센서스 트래커와 같은 소스(FnGuide 컨센서스)에서 과거 시계열을 직접 받아,
종목별 작은 차트(소형 다중 차트)에 최근 6개월 영업이익 컨센 추이를 그린다.
  - FnGuide getCnsTrendChart : 월말 시계열(약 1년)
  - 네이버 WiseReport cF5002  : 분기 = 주간 13개 시점, 연간 = 월말 13개 시점
  → 겹치는 구간은 네이버(촘촘한) 값, 그 이전은 FnGuide 월말 값으로 이어 붙인다.

  - 컨센서스_추이_분기.png/.svg/.csv : 분기 영업이익 컨센 (기본: 다음 2개 분기, 예: 4Q26·1Q27)
  - 컨센서스_추이_연간.png/.svg/.csv : 연간 영업이익 컨센 (기본: 올해E·내년E)

실행:
    python consensus/weekly_consensus_chart.py                  # 최근 6개월, 분기·연간 둘 다
    python consensus/weekly_consensus_chart.py --months 12
    python consensus/weekly_consensus_chart.py --mode quarter --periods 2026.12,2027.03
    python consensus/weekly_consensus_chart.py --since 2026-05-01

종목·순서·섹터는 아래 COMPANIES 만 고치면 된다. (섹터, 표시명, 종목코드)
"""

import argparse
import json
import os
import sys
import time
import urllib.parse
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
# 조선 = 바다 파랑 · 방산 = 골드 · 건기 = 그레이 (사용자 지정)
BLOCK_BG = {"조선": "#E6F1FA", "방산": "#F5EFE6", "건기": "#EEEEEE"}
CHIP = {"조선": "#2B7CB8", "조기": "#2B7CB8", "방산": "#B79C7E", "건기": "#8A8A8A"}

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

DEFAULT_MONTHS = 6  # 기본 표시 기간: 최근 6개월
OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "consensus")
FILES = {"quarter": "컨센서스_추이_분기.png", "annual": "컨센서스_추이_연간.png"}
CSV_FILES = {"quarter": "컨센서스_추이_분기.csv", "annual": "컨센서스_추이_연간.csv"}


# =========================================================================
# 폰트
# =========================================================================
def setup_font():
    """보고서 서체 = 나눔스퀘어 Light. 러너는 fonts-nanum-extra(NanumSquareL.ttf)를 깔아
    그림에 직접 박는다(보는 PC 폰트와 무관). 본문은 Light(300), 굵게 지정한 제목은 같은
    가족의 Bold. Light 가 없는 환경은 종전 나눔고딕 등으로 폴백."""
    fl = font_manager.fontManager.ttflist
    have = {f.name for f in fl}
    if any(f.name == "NanumSquare" and f.weight in (300, "light") for f in fl):
        # 목록이면 글자 단위 폴백(matplotlib ≥3.6) — 나눔스퀘어에 없는 글자는 나눔고딕으로
        plt.rcParams["font.family"] = ["NanumSquare"] + [n for n in ("NanumGothic",) if n in have]
        plt.rcParams["font.weight"] = 300   # 숫자로 — "light" 는 findfont 경고가 줄줄이 난다
        for k in ("axes.titleweight", "axes.labelweight", "figure.titleweight"):
            plt.rcParams[k] = 300   # 기본값 normal(=Regular)이라 따로 내려준다; fontweight="bold" 지정분은 그대로 Bold
        plt.rcParams["axes.unicode_minus"] = False
        return
    wanted = ["Malgun Gothic", "NanumGothic", "NanumBarunGothic", "AppleGothic",
              "Noto Sans CJK KR", "Noto Sans KR", "WenQuanYi Zen Hei"]
    for name in wanted:
        if name in have:
            plt.rcParams["font.family"] = name
            break
    else:
        print("⚠️ 한글 폰트를 찾지 못했습니다 (fonts-nanum 설치 권장). 글자가 깨질 수 있습니다.")
    plt.rcParams["axes.unicode_minus"] = False


# =========================================================================
# 데이터 — FnGuide(월말 시계열, 1년) + 네이버 WiseReport(분기=주간·연간=월말, 13개 시점)
#   둘 다 FnGuide 컨센서스(평균)라 값이 같다. 겹치는 날짜는 네이버(주간) 값을 쓰고
#   그 이전 구간은 FnGuide 월말 값으로 채운다.
# =========================================================================
FN_BASE = "https://wcomp.fnguide.com/CompanyInfo"
NV_BASE = "https://navercomp.wisereport.co.kr"
UA = "Mozilla/5.0 (compatible; consensus-weekly-chart)"
FN_OP = 1          # getCnsTrendChart data_typ: 0=매출액, 1=영업이익
NV_OP = "121500"   # cF5002 acc_cd: 영업이익


def _get_json(url, referer):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": referer,
                                               "X-Requested-With": "XMLHttpRequest"})
    for attempt in range(4):   # 간헐적 connection reset → 재시도
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception:
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))


def _empty():
    return pd.Series(dtype=float, index=pd.DatetimeIndex([]))


def fn_periods(code, freq):
    """FnGuide가 시계열을 주는 결산년월 목록. 예: ['202612', '202703', '202706']."""
    for consol in ("C", "P"):
        q = urllib.parse.urlencode({"cmp_cd": code, "consol_typ": consol,
                                    "freq_typ": freq, "data_typ": FN_OP})
        try:
            ds = _get_json(f"{FN_BASE}/getCnsTrendYYMM?{q}",
                           f"{FN_BASE}/Consensus?gicode=A{code}")["dataset"]
        except Exception:
            continue
        if ds:
            return [d["YYMM"] for d in ds], consol
    return [], "C"


def fn_series(code, freq, yymm, consol="C"):
    q = urllib.parse.urlencode({"cmp_cd": code, "consol_typ": consol, "freq_typ": freq,
                                "select_gsym": yymm, "data_typ": FN_OP})
    try:
        rows = _get_json(f"{FN_BASE}/getCnsTrendChart?{q}",
                         f"{FN_BASE}/Consensus?gicode=A{code}")["dataset"]["data"]
    except Exception as e:
        print(f"  FnGuide 실패 {code} {yymm}: {e}")
        return _empty()
    pts = {pd.to_datetime(r["TRD_DT"], format="%y/%m/%d"): r["VAL_AVG"]
           for r in rows if r.get("VAL_AVG") is not None}
    return pd.Series(pts, dtype=float).sort_index() if pts else _empty()


def nv_series(code, freq, yymm):
    q = urllib.parse.urlencode({"cmp_cd": code, "yymm": yymm, "frq": freq,
                                "acc_cd": NV_OP, "fingubun": "MAIN", "chartType": "svg"})
    try:
        d = _get_json(f"{NV_BASE}/company/ajax/cF5002.aspx?{q}",
                      f"{NV_BASE}/v2/company/c1050001.aspx?cmp_cd={code}")
        c = json.loads(d["chart2"])
    except Exception as e:
        print(f"  네이버 실패 {code} {yymm}: {e}")
        return _empty()
    if "영업이익" not in c.get("item_name", "영업이익"):
        return _empty()
    s = pd.Series([v for v in c["avg"]], index=pd.to_datetime(c["categories"], format="%Y/%m/%d"),
                  dtype=float)
    return s[~s.index.duplicated(keep="last")].dropna().sort_index()


def fetch(kind, periods=None):
    """long DataFrame(snapshot_date, code, period 'YYYY.MM', op_profit)과 기간 목록."""
    freq = "Q" if kind == "quarter" else "Y"
    rows, chosen = [], periods
    for sec, name, code in COMPANIES:
        avail, consol = fn_periods(code, freq)
        if chosen is None and avail:
            chosen = [f"{p[:4]}.{p[4:]}" for p in avail[:2]]   # 분기: 다음 2개 분기, 연간: 올해·내년
        for p in chosen or []:
            yymm = p.replace(".", "")
            fn = fn_series(code, freq, yymm, consol)
            nv = nv_series(code, freq, yymm)
            s = pd.concat([fn[fn.index < nv.index.min()] if len(nv) else fn, nv]).sort_index()
            s = s[~s.index.duplicated(keep="last")]
            rows += [(d, code, p, v) for d, v in s.items()]
            time.sleep(0.15)
        print(f"  {name}: {len([r for r in rows if r[1] == code])}개 시점")
    df = pd.DataFrame(rows, columns=["snapshot_date", "code", "period", "op_profit"])
    return df, chosen or []


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
        return "Δ1M 0.0%", MUTED
    return f"Δ1M {pct:+.1f}%", (UP if pct > 0 else DOWN)


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
        ax.plot([0.15, 0.24], [ly, ly], transform=ax.transAxes, color=color,
                linewidth=1.3, clip_on=False, solid_capstyle="butt")
        if s is None or s.dropna().empty:
            ax.text(0.27, ly, f"{label} OP  n/a", transform=ax.transAxes,
                    fontsize=5.6, color=MUTED, va="center", ha="left")
            continue
        has_any = True
        s = s.dropna()
        ax.plot(s.index, s.values, color=color, linewidth=1.25, drawstyle="steps-post",
                zorder=3 + (1 - i))
        ax.plot(s.index[-1], s.values[-1], "o", color=color, markersize=2.2, zorder=5)
        ax.text(0.27, ly, f"{label} OP", transform=ax.transAxes,
                fontsize=5.6, color=TEXT, va="center", ha="left")
        ax.text(0.66, ly, f"{s.iloc[-1]:,.0f}", transform=ax.transAxes,
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


def clip_since(df, since):
    """since 이후만 남기되, 그 직전 값을 since 시점에 이어 붙여 선이 왼쪽 끝부터 시작하게 한다."""
    keep = [df[df.snapshot_date >= since]]
    before = df[df.snapshot_date < since].sort_values("snapshot_date")
    if len(before):
        carry = before.groupby(["code", "period"]).tail(1).copy()
        carry["snapshot_date"] = since
        keep.append(carry)
    out = pd.concat(keep).sort_values("snapshot_date")
    return out.drop_duplicates(["snapshot_date", "code", "period"], keep="first")


def render(df, kind, periods, since, path, asof):
    df = df[df.period.isin(periods)]
    df = clip_since(df, since)
    if df.empty:
        print(f"⚠️ {kind}: {periods} 데이터가 없습니다 — 건너뜀")
        return
    x0, x1 = since, asof
    xpad = (x1 - x0) * 0.02
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
             f"주: {what} 영업이익 컨센서스({labels}) 평균 추이, 최근 {round((asof - since).days / 30.4)}개월. "
             f"OP=영업이익, 범례 숫자는 최신 컨센(억원), 오른쪽 Δ1M은 1개월 전 대비 변화율",
             fontsize=6, color=MUTED, ha="left", va="center")
    fig.text(0.1 / fig_w, 0.13 / fig_h,
             f"자료: FnGuide, 네이버증권(WiseReport) · 기준일 {asof:%Y-%m-%d}",
             fontsize=6, color=MUTED, ha="left", va="center")

    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=DPI, facecolor="white")
    # 같은 그림의 SVG(벡터) — 엑셀·PPT '삽입 → 그림'으로 넣으면 확대해도 선명. 글자는 경로로 묻어
    # 받는 PC 에 한글 폰트가 없어도 모양이 같다.
    with plt.rc_context({"svg.fonttype": "path"}):
        fig.savefig(os.path.splitext(path)[0] + ".svg", facecolor="white")
    plt.close(fig)
    print(f"저장: {path}  ({labels})")


# =========================================================================
def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mode", choices=["quarter", "annual", "both"], default="both")
    ap.add_argument("--periods", help="기간 직접 지정(쉼표 2개), 예: 2026.12,2027.03 "
                                      "(--mode quarter/annual 하나일 때)")
    ap.add_argument("--months", type=int, default=DEFAULT_MONTHS, help="표시 기간(개월, 기본 6)")
    ap.add_argument("--since", help="시작일 직접 지정 (YYYY-MM-DD, --months 무시)")
    ap.add_argument("--out", default=OUTPUT_DIR, help="출력 폴더")
    args = ap.parse_args()

    setup_font()
    modes = ["quarter", "annual"] if args.mode == "both" else [args.mode]
    for kind in modes:
        print(f"[{kind}] 컨센서스 시계열 수집")
        periods = args.periods.split(",") if args.periods and args.mode != "both" else None
        df, periods = fetch(kind, periods)
        if df.empty:
            print(f"⚠️ {kind}: 데이터 없음")
            continue
        asof = df.snapshot_date.max()
        since = (pd.Timestamp(args.since) if args.since
                 else asof - pd.DateOffset(months=args.months))
        os.makedirs(args.out, exist_ok=True)
        df.sort_values(["code", "period", "snapshot_date"]).to_csv(
            os.path.join(args.out, CSV_FILES[kind]), index=False, encoding="utf-8-sig")
        render(df, kind, periods, since, os.path.join(args.out, FILES[kind]), asof)


if __name__ == "__main__":
    main()

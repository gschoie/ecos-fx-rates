# -*- coding: utf-8 -*-
"""조선주 상대 INDEX 차트 3종 — 위클리/PPT에 바로 붙이는 PNG+SVG.

  ① 한국 주식시장 vs 조선주 : KOSPI vs 한국 조선주 지수
  ② 한국 조선 7사 Performance : 종목별 선
  ③ 한/중/일/싱 조선주 비교  : 국가별 지수

지수는 12주(60거래일) 전 = 100. 국가별 지수는 **시총 가중**(기준일 USD 시총을 고정 가중치로 두고
종목 수익률을 가중 평균 — 통화가 섞인 중국(CNY·HKD·SGD)도 환율 없이 비교 가능). 가격은
weekly_peer_price_image 가 받는 야후 일별 종가를 그대로 쓴다.

실행:
    python peergroup/weekly_peer_index_image.py          # 야후 수집
    python peergroup/weekly_peer_index_image.py --demo   # 가짜 데이터로 레이아웃만

구성은 GROUPS / KR_FIVE 만 고치면 된다(표시명, 야후 티커).
"""

import argparse
import os
import sys
from datetime import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import weekly_peer_price_image as base  # noqa: E402  (폰트·야후 수집·저장 재사용)

# 한국 조선주(사용자 지정 11/7): 조선 4사 + 대한조선 + 한화엔진 + HD현대마린엔진
KR_SHIP = [("HD현대중공업", "329180.KS"), ("HD한국조선해양", "009540.KS"), ("삼성중공업", "010140.KS"),
           ("한화오션", "042660.KS"), ("대한조선", "439260.KS"), ("한화엔진", "082740.KS"),
           ("HD현대마린엔진", "071970.KS")]
GROUPS = {   # ③ 국가별 지수(시총 가중)
    "한국": KR_SHIP,
    "중국": [("CSSC", "600150.SS"), ("CSSC O&ME", "0317.HK"), ("Yangzijiang", "BS6.SI")],
    "일본": [("Mitsubishi HI", "7011.T"), ("Mitsui E&S", "7003.T"), ("Kawasaki HI", "7012.T"),
           ("Sumitomo HI", "6302.T"), ("IHI", "7013.T"), ("Naikai Zosen", "7018.T")],
    "싱가포르": [("Seatrium", "5E2.SI")],
}
KOSPI = ("KOSPI", "^KS11")
# 야후가 시총을 안 주는 종목(SGX 상장 Yangzijiang — fast_info·info 모두 None, 11/7 실측)의 상장주식수 폴백.
# 시총 = 주식수 × 종가 × 환율. 숫자가 바뀌면 여기만 고친다(연차보고서 기준 보통주).
SHARES_FALLBACK = {"BS6.SI": (3.95e9, "SGD")}   # Yangzijiang Shipbuilding ≈ 39.5억주
WEEKS = 12                      # 기준일 = 12주 전
DAYS = WEEKS * 5                # 거래일 환산

GROUP_COLORS = {"한국": "#A68A64", "중국": "#D62728", "일본": "#1F5FBF", "싱가포르": "#5BB5E0"}
LINE_COLORS = ["#1F5FBF", "#A68A64", "#2CA02C", "#D62728", "#111111", "#8C6BB1", "#FF9F1C"]
TEXT, MUTED, GRID = base.TEXT, base.MUTED, base.GRID

W_IN, H_IN = 6.4, 4.8           # 차트 1장 크기(inch) — 3장 묶음은 2×2 격자
FS_TITLE, FS_AX, FS_LG = 16, 12.5, 12
LW = 2.6
OUT_ALL = "조선주_INDEX_3종.png"
OUT_ONE = ["IDX1_한국시장_vs_조선주", "IDX2_한국조선_Performance", "IDX3_한중일싱_조선주"]


def all_tickers():
    out = [KOSPI[1]]
    for items in GROUPS.values():
        out += [t for _, t in items]
    return list(dict.fromkeys(out))


def window(prices):
    """공통 거래일 — KOSPI 거래일 기준으로 맞추고(국내 리포트 관행) 해외 휴장일은 직전값 보유."""
    k = prices[KOSPI[1]]
    idx = k.index[-(DAYS + 1):]
    df = pd.DataFrame({t: s.reindex(idx, method="ffill") for t, s in prices.items()})
    return df.dropna(axis=1, how="all")


def rebase(s):
    return s / s.iloc[0] * 100


def cap_weighted(df, items, caps):
    """기준일 USD 시총(= 현재 시총 × 기준일가/현재가)을 고정 가중치로 둔 지수. 시총 모르는 종목은 제외."""
    cols, w = [], []
    for name, t in items:
        if t in df.columns and caps.get(t) and df[t].notna().all():
            cols.append(t)
            w.append(caps[t] * df[t].iloc[0] / df[t].iloc[-1])
        else:
            why = "가격 없음" if t not in df.columns else ("시총 없음" if not caps.get(t) else "구간 결측")
            print(f"  ⚠️ 지수 제외 {name}({t}): {why}")
    if not cols:
        return None, []
    w = np.array(w) / sum(w)
    rel = np.column_stack([rebase(df[c]).values for c in cols])
    return pd.Series(rel @ w, index=df.index), cols


def demo(tickers, seed=3):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=datetime.today(), periods=300)
    prices = {t: pd.Series(100 * np.exp(np.cumsum(rng.normal(-0.001, 0.02, len(idx)))), index=idx) for t in tickers}
    caps = {t: float(rng.lognormal(8, 1)) for t in tickers if t != KOSPI[1]}
    return prices, caps


# ----------------------------------------------------------------------------- 그리기
def style(ax, title):
    ax.set_title(title, loc="left", fontsize=FS_TITLE, fontweight="bold", color=TEXT, pad=10)
    ax.axhline(100, color=GRID, lw=1.2)
    ax.grid(axis="y", color="#E6E6E6", lw=0.8)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color("#8C8C8C")
    ax.tick_params(labelsize=FS_AX, colors=TEXT, length=4)
    ax.set_ylabel(f"INDEX ({WEEKS}주전=100)", fontsize=FS_AX - 1, color=MUTED)
    ax.margins(x=0.01)


def xticks(ax, idx):
    pos = list(range(0, len(idx), 10))
    ax.set_xticks(pos)
    ax.set_xticklabels([f"{idx[i].month}.{idx[i].day}" for i in pos])


def legend(ax, ncol=2):
    # 범례는 그래프 아래(선을 가리지 않게)
    ax.legend(fontsize=FS_LG, frameon=False, ncol=ncol, loc="upper center", bbox_to_anchor=(0.5, -0.13),
              handlelength=1.6, borderaxespad=0, labelspacing=0.3, columnspacing=1.4)


def chart1(ax, df, caps):
    kr, _ = cap_weighted(df, KR_SHIP, caps)
    x = range(len(df))
    ax.plot(x, rebase(df[KOSPI[1]]).values, color="#7F7F7F", lw=LW, label="KOSPI")
    if kr is not None:
        ax.plot(x, kr.values, color=GROUP_COLORS["한국"], lw=LW + 0.4, label="한국 조선주 (시총가중)")
    style(ax, "한국 주식시장 vs. 조선주"); xticks(ax, df.index); legend(ax)


def chart2(ax, df):
    x = range(len(df))
    for i, (name, t) in enumerate(KR_SHIP):
        if t in df.columns and df[t].notna().all():
            ax.plot(x, rebase(df[t]).values, color=LINE_COLORS[i % len(LINE_COLORS)], lw=LW - 0.4, label=name)
    style(ax, f"한국 조선 {len(KR_SHIP)}사 Performance"); xticks(ax, df.index); legend(ax, ncol=4)


def chart3(ax, df, caps):
    x = range(len(df))
    for g, items in GROUPS.items():
        s, cols = cap_weighted(df, items, caps)
        if s is not None:
            ax.plot(x, s.values, color=GROUP_COLORS[g], lw=LW, label=f"{g} 조선주 ({len(cols)})")
    style(ax, "한/중/일/싱 조선주 비교 (시총가중)"); xticks(ax, df.index); legend(ax)


def render(df, caps, out_dir, asof):
    draws = [lambda ax: chart1(ax, df, caps), lambda ax: chart2(ax, df), lambda ax: chart3(ax, df, caps)]
    # 낱장
    for fn, draw in zip(OUT_ONE, draws):
        fig, ax = plt.subplots(figsize=(W_IN, H_IN), dpi=base.DPI)
        draw(ax)
        fig.tight_layout()
        base.save_fig(fig, os.path.join(out_dir, fn + ".png"))
    # 3장 묶음(2×2, 오른쪽 아래 비움 — 리포트 배치 그대로)
    fig, axes = plt.subplots(2, 2, figsize=(W_IN * 2, H_IN * 2), dpi=base.DPI)
    for ax, draw in zip([axes[0][0], axes[0][1], axes[1][0]], draws):
        draw(ax)
    axes[1][1].axis("off")
    axes[1][1].text(0.02, 0.9, f"기준일 {asof:%Y.%m.%d}\n자료: Yahoo Finance\n"
                    f"INDEX = {WEEKS}주({DAYS}거래일) 전 종가 = 100, KOSPI 거래일 기준\n"
                    "국가 지수 = 기준일 USD 시총 가중(고정 가중치)\n"
                    "한국 조선주 = 조선 4사 + 대한조선 + 한화엔진 + HD현대마린엔진",
                    fontsize=FS_AX, color=MUTED, va="top", linespacing=1.6)
    fig.tight_layout()
    base.save_fig(fig, os.path.join(out_dir, OUT_ALL))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--out", default=base.OUTPUT_DIR)
    a = ap.parse_args()
    base.setup_font()
    tickers = all_tickers()
    print(f"📈 INDEX 차트 — {len(tickers)}개 {'(데모)' if a.demo else '야후 수집'}")
    if a.demo:
        prices, caps = demo(tickers)
    else:
        prices = base.fetch_prices(tickers)
        if KOSPI[1] not in prices:
            print("❌ KOSPI 를 못 받았다 — 중단"); return 1
        caps = base.fetch_market_caps_usd_m([t for t in tickers if t != KOSPI[1] and t in prices])
        for t, (shares, cur) in SHARES_FALLBACK.items():
            if not caps.get(t) and t in prices:
                try:
                    import yfinance as yf
                    fx = float(yf.Ticker(f"{cur}USD=X").history(period="5d")["Close"].dropna().iloc[-1])
                except Exception:
                    fx = {"SGD": 0.77}.get(cur, 1.0)
                caps[t] = shares * float(prices[t].iloc[-1]) * fx / 1e6
                print(f"  ℹ️ {t} 시총은 상장주식수 폴백({shares/1e8:.1f}억주 × 종가 × {cur}USD {fx:.3f})")
    df = window(prices)
    missing = [t for t in tickers if t not in df.columns]
    if missing:
        print(f"⚠️ 데이터 없는 종목: {', '.join(missing)}")
    os.makedirs(a.out, exist_ok=True)
    render(df, caps, a.out, df.index[-1])
    print(f"🖼  {os.path.join(a.out, OUT_ALL)} (+ 낱장 3)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

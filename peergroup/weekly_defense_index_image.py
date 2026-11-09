# -*- coding: utf-8 -*-
"""방산 상대 INDEX 차트 4종 — 조선주 INDEX(weekly_peer_index_image)와 같은 틀, 유니버스만 방산.

  ① 한국 방산 체계 5사 Performance : 종목별 선
  ② 한국 방산 부체계(부품) Performance : 종목별 선
  ③ 한국 체계 5사 vs 부체계 vs 미국 프라임 vs 유럽 체계 : 묶음별 시총가중 지수
  ④ 드론 vs 엔진/부품 vs 항공 (글로벌) : 테마별 시총가중 지수

11/9 사용자 요청("방산쪽도 주가 비교 index 차트"). 12주(60거래일) 전 = 100, KOSPI 거래일 기준,
묶음 지수는 기준일 USD 시총 가중(고정 가중치) — 산식·그리기·저장은 전부 조선판에서 가져온다.
종목 집합은 weekly_peer_price_image.DEFENSE_SECTIONS(방산 주가흐름표)와 같은 티커를 쓰되 부체계는 몇 곳을 더했다.

실행:
    python peergroup/weekly_defense_index_image.py          # 야후 수집 → output/peer_price_defense/
    python peergroup/weekly_defense_index_image.py --demo   # 가짜 데이터로 레이아웃만

구성은 KR_PRIME / KR_SUB / GROUPS / THEMES 만 고치면 된다.
"""

import argparse
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import weekly_peer_price_image as base  # noqa: E402
import weekly_peer_index_image as idx   # noqa: E402  (window·rebase·cap_weighted·style·legend·footnote 틀)

KR_PRIME = [("한화에어로스페이스", "012450.KS"), ("한국항공우주", "047810.KS"), ("LIG D&A", "079550.KS"),
            ("한화시스템", "272210.KS"), ("현대로템", "064350.KS")]
# 부체계·부품(탄약/기동 포함) — 주가흐름표의 탄약/기동·부체계 + 빅텍·코츠테크놀로지·한일단조·삼영컴텍·웨이브일렉트로닉스
KR_SUB = [("풍산", "103140.KS"), ("SNT다이내믹스", "003570.KS"), ("엠앤씨솔루션", "484870.KS"),
          ("아이쓰리시스템", "214430.KQ"), ("퍼스텍", "010820.KS"), ("휴니드", "005870.KS"),
          ("빅텍", "065450.KQ"), ("코츠테크놀로지", "448710.KQ"), ("한일단조", "024740.KQ"),
          ("삼영컴텍", "484590.KQ"), ("웨이브일렉트로닉스", "095270.KQ")]
US_PRIME = [("Lockheed Martin", "LMT"), ("RTX", "RTX"), ("Northrop Grumman", "NOC"), ("General Dynamics", "GD"),
            ("L3Harris", "LHX"), ("Boeing", "BA"), ("Huntington Ingalls", "HII")]
EU_PRIME = [("Rheinmetall", "RHM.DE"), ("BAE Systems", "BA.L"), ("Thales", "HO.PA"), ("Leonardo", "LDO.MI"),
            ("Saab", "SAAB-B.ST"), ("Hensoldt", "HAG.DE"), ("Renk", "R3NK.DE"), ("Kongsberg", "KOG.OL")]
GROUPS = {   # ③
    "한국 체계 5사": KR_PRIME, "한국 부체계": KR_SUB, "미국 프라임": US_PRIME, "유럽 체계": EU_PRIME,
}
GROUP_COLORS = {"한국 체계 5사": "#A68A64", "한국 부체계": "#2CA02C", "미국 프라임": "#1F5FBF", "유럽 체계": "#D62728"}
THEMES = {   # ④ 글로벌 테마(주가흐름표의 미국 드론/신흥·엔진/부품, 유럽 항공·엔진/부품 묶음)
    "드론": [("Kratos", "KTOS"), ("AeroVironment", "AVAV")],
    "엔진/부품": [("GE Aerospace", "GE"), ("Howmet", "HWM"), ("TransDigm", "TDG"), ("Curtiss-Wright", "CW"),
              ("Rolls-Royce", "RR.L"), ("Safran", "SAF.PA"), ("MTU Aero", "MTX.DE")],
    "항공": [("Airbus", "AIR.PA"), ("Dassault Aviation", "AM.PA"), ("Embraer", "EMBJ")],
}
THEME_COLORS = {"드론": "#8C6BB1", "엔진/부품": "#FF9F1C", "항공": "#1F5FBF"}
LINE_COLORS = idx.LINE_COLORS + ["#17BECF", "#BCBD22", "#E377C2", "#7F7F7F"]   # ② 11종목용

OUT_DIR = os.path.join(base._OUT_ROOT, "peer_price_defense")
OUT_ALL = "방산_INDEX_4종.png"
OUT_ONE = ["DIDX1_한국체계5사", "DIDX2_한국부체계", "DIDX3_한국vs미국유럽", "DIDX4_드론_엔진_항공"]


def all_tickers():
    out = [idx.KOSPI[1]]
    for items in list(GROUPS.values()) + list(THEMES.values()):
        out += [t for _, t in items]
    return list(dict.fromkeys(out))


def lines(ax, df, items, title, ncol):
    x = range(len(df))
    for i, (name, t) in enumerate(items):
        if t in df.columns and df[t].notna().all():
            ax.plot(x, idx.rebase(df[t]).values, color=LINE_COLORS[i % len(LINE_COLORS)], lw=idx.LW - 0.4, label=name)
        else:
            print(f"  ⚠️ 선 제외 {name}({t}): {'가격 없음' if t not in df.columns else '구간 결측'}")
    idx.style(ax, title); idx.xticks(ax, df.index); idx.legend(ax, ncol=ncol)


def indices(ax, df, caps, groups, colors, title, ncol):
    x = range(len(df))
    for g, items in groups.items():
        s, cols = idx.cap_weighted(df, items, caps)
        if s is not None:
            ax.plot(x, s.values, color=colors[g], lw=idx.LW, label=f"{g} ({len(cols)})")
    idx.style(ax, title); idx.xticks(ax, df.index); idx.legend(ax, ncol=ncol)


NOTE_LINES = 6


def footnote(asof):
    names = lambda items: "·".join(n for n, _ in items)
    return "\n".join([
        f"기준일 {asof:%Y.%m.%d}  ·  자료: Yahoo Finance  ·  INDEX = {idx.WEEKS}주({idx.DAYS}거래일) 전 종가 = 100, KOSPI 거래일 기준(해외 휴장일은 직전값)",
        "묶음 지수 = 기준일 USD 시총 가중(고정 가중치), 범례 괄호는 지수에 든 종목 수",
        f"한국 부체계 = {names(KR_SUB)}",
        f"미국 프라임 = {names(US_PRIME)}",
        f"유럽 체계 = {names(EU_PRIME)}",
        f"드론 = {names(THEMES['드론'])} / 엔진·부품 = {names(THEMES['엔진/부품'])} / 항공 = {names(THEMES['항공'])}",
    ])


def render(df, caps, out_dir, asof):
    draws = [
        lambda ax: lines(ax, df, KR_PRIME, f"한국 방산 체계 {len(KR_PRIME)}사 Performance", 3),
        lambda ax: lines(ax, df, KR_SUB, "한국 방산 부체계(부품) Performance", 3),
        lambda ax: indices(ax, df, caps, GROUPS, GROUP_COLORS, "한국 체계·부체계 vs. 미국·유럽 (시총가중)", 2),
        lambda ax: indices(ax, df, caps, THEMES, THEME_COLORS, "드론 vs. 엔진/부품 vs. 항공 (글로벌, 시총가중)", 3),
    ]
    for fn, draw in zip(OUT_ONE, draws):
        fig, ax = plt.subplots(figsize=(idx.W_IN, idx.H_IN), dpi=base.DPI)
        draw(ax)
        fig.tight_layout()
        base.save_fig(fig, os.path.join(out_dir, fn + ".png"))
    note_in = 0.32 * NOTE_LINES    # 각주 6줄 — 한 줄에 다 적으면 오른쪽으로 넘친다(데모 실측)
    fig_h = idx.H_IN * 2 + note_in
    fig, axes = plt.subplots(2, 2, figsize=(idx.W_IN * 2, fig_h), dpi=base.DPI)
    for ax, draw in zip(axes.flat, draws):
        draw(ax)
    fig.tight_layout(rect=(0, note_in / fig_h, 1, 1))
    fig.text(0.015, 0.012, footnote(asof), fontsize=idx.FS_AX - 2, color=idx.MUTED, va="bottom", ha="left", linespacing=1.7)
    base.save_fig(fig, os.path.join(out_dir, OUT_ALL))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--out", default=OUT_DIR)
    a = ap.parse_args()
    base.setup_font()
    tickers = all_tickers()
    print(f"🛡️ 방산 INDEX 차트 — {len(tickers)}개 {'(데모)' if a.demo else '야후 수집'}")
    if a.demo:
        prices, caps = idx.demo(tickers)
    else:
        prices = base.fetch_prices(tickers)
        if idx.KOSPI[1] not in prices:
            print("❌ KOSPI 를 못 받았다 — 중단"); return 1
        caps = base.fetch_market_caps_usd_m([t for t in tickers if t != idx.KOSPI[1] and t in prices])
    df = idx.window(prices)
    missing = [t for t in tickers if t not in df.columns]
    if missing:
        print(f"⚠️ 데이터 없는 종목: {', '.join(missing)}")
    os.makedirs(a.out, exist_ok=True)
    render(df, caps, a.out, df.index[-1])
    print(f"🖼  {os.path.join(a.out, OUT_ALL)} (+ 낱장 {len(OUT_ONE)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""건설기계 상대 INDEX 차트 4종 — 조선주 INDEX(weekly_peer_index_image)와 같은 틀, 유니버스만 건설기계.

  ① HD건설기계 · 두산밥캣 · 한국 건설기계 부품사(시총가중) : 종목 2 + 부품 지수 1
  ② 한국 2사 vs 미국 vs 중국 vs 일본 피어그룹 : 묶음별 시총가중 지수
  ③ HD건설기계 · Caterpillar · Komatsu · Hitachi CM · SANY · XCMG · Zoomlion · LiuGong : 종목별 선(중국은 SANY 빼고 점선)
  ④ 두산밥캣 · Deere · CNH · Kobelco · 대동 : 종목별 선

11/10 사용자 요청. 색 지정(사용자): HD건설기계 초록 · 두산밥캣 남색 · 한국 묶음 골드(= DAOL 리포트 골드, 조선판 '한국' 묶음과
같은 #A68A64 — 노란 금색이 아니다) · 중국 빨강. 11/10 2차: CAT 노랑과 Hitachi 주황이 구분이 안 돼 Hitachi 를 검정으로, ④ 에 CNH.
12주(60거래일) 전 = 100, KOSPI 거래일 기준, 묶음 지수는 기준일 USD 시총 가중 — 산식·그리기·저장은 조선판 import.
종목 집합은 weekly_peer_price_image.CONSTRUCTION_SECTIONS(건기 주가변동표)와 같은 티커.

실행:
    python peergroup/weekly_construction_index_image.py          # 야후 수집 → output/peer_price_construction/
    python peergroup/weekly_construction_index_image.py --demo   # 가짜 데이터로 레이아웃만
"""

import argparse
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import weekly_peer_price_image as base  # noqa: E402
import weekly_peer_index_image as idx   # noqa: E402

HD, BOBCAT = ("HD건설기계", "267270.KS"), ("두산밥캣", "241560.KS")
KR_OEM = [HD, BOBCAT]
KR_PARTS = [("디와이파워", "210540.KS"), ("진성티이씨", "036890.KQ"), ("대창단조", "015230.KS"),
            ("동일금속", "109860.KQ"), ("흥국", "010240.KQ"), ("우림피티에스", "101170.KQ")]
US_OEM = [("Caterpillar", "CAT"), ("Terex", "TEX"), ("Oshkosh", "OSK"), ("Manitowoc", "MTW")]
CN_OEM = [("SANY", "600031.SS"), ("XCMG", "000425.SZ"), ("Zoomlion", "1157.HK"), ("LiuGong", "000528.SZ"),
          ("Lonking", "3339.HK")]
JP_OEM = [("Komatsu", "6301.T"), ("Hitachi CM", "6305.T"), ("Kubota", "6326.T"), ("Sumitomo HI", "6302.T"),
          ("Takeuchi", "6432.T"), ("Tadano", "6395.T")]
GROUPS = {"한국 2사": KR_OEM, "미국": US_OEM, "중국": CN_OEM, "일본": JP_OEM}   # ②

GREEN, NAVY, GOLD, RED = "#00A651", "#1B2E6B", idx.GROUP_COLORS["한국"], "#D62728"   # GOLD = DAOL 골드(#A68A64)
GROUP_COLORS = {"한국 2사": GOLD, "미국": "#1F5FBF", "중국": RED, "일본": "#7F7F7F"}
DASH = (0, (4, 2))
# ③ 종목별 스타일 — CAT 노랑·Komatsu 파랑·Hitachi 주황(브랜드색), 중국은 빨강 계열(SANY 만 실선, 나머지 점선)
BIG_STYLE = {
    "HD건설기계": dict(color=GREEN), "Caterpillar": dict(color="#E0A800"), "Komatsu": dict(color="#0057A8"),
    "Hitachi CM": dict(color="#111111"), "SANY": dict(color=RED),
    "XCMG": dict(color="#B01C2E", ls=DASH), "Zoomlion": dict(color="#E8505B", ls=(0, (6, 2))),
    "LiuGong": dict(color="#8B0000", ls=(0, (1, 2))),
}
BIG = [HD, ("Caterpillar", "CAT"), ("Komatsu", "6301.T"), ("Hitachi CM", "6305.T"),
       ("SANY", "600031.SS"), ("XCMG", "000425.SZ"), ("Zoomlion", "1157.HK"), ("LiuGong", "000528.SZ")]
# ④ 소형·농기계 — Deere 초록(브랜드), Kobelco 는 모회사 Kobe Steel(5406.T, 건설기계는 자회사) 회색, 대동 골드
SMALL = [BOBCAT, ("Deere", "DE"), ("CNH", "CNH"), ("Kobelco(Kobe Steel)", "5406.T"), ("대동", "000490.KS")]
SMALL_STYLE = {"두산밥캣": dict(color=NAVY), "Deere": dict(color="#367C2B"), "CNH": dict(color="#C8102E"),
               "Kobelco(Kobe Steel)": dict(color="#7F7F7F"), "대동": dict(color=GOLD)}

OUT_DIR = os.path.join(base._OUT_ROOT, "peer_price_construction")
OUT_ALL = "건설기계_INDEX_4종.png"
OUT_ONE = ["CIDX1_한국2사_부품", "CIDX2_한국vs미중일", "CIDX3_대형OEM", "CIDX4_소형_농기계"]
NOTE_LINES = 6


def all_tickers():
    out = [idx.KOSPI[1]]
    for items in [KR_OEM, KR_PARTS, US_OEM, CN_OEM, JP_OEM, BIG, SMALL]:
        out += [t for _, t in items]
    return list(dict.fromkeys(out))


def lines(ax, df, items, style, title, ncol):
    x = range(len(df))
    for i, (name, t) in enumerate(items):
        if t in df.columns and df[t].notna().all():
            st = style.get(name, {"color": idx.LINE_COLORS[i % len(idx.LINE_COLORS)]})
            ax.plot(x, idx.rebase(df[t]).values, color=st["color"], ls=st.get("ls", "-"), lw=idx.LW - 0.4, label=name)
        else:
            print(f"  ⚠️ 선 제외 {name}({t}): {'가격 없음' if t not in df.columns else '구간 결측'}")
    idx.style(ax, title); idx.xticks(ax, df.index); idx.legend(ax, ncol=ncol)


def chart1(ax, df, caps):
    x = range(len(df))
    for name, t in KR_OEM:
        if t in df.columns and df[t].notna().all():
            ax.plot(x, idx.rebase(df[t]).values, color=GREEN if name == "HD건설기계" else NAVY, lw=idx.LW, label=name)
    s, cols = idx.cap_weighted(df, KR_PARTS, caps)
    if s is not None:
        ax.plot(x, s.values, color=GOLD, lw=idx.LW, ls=DASH, label=f"한국 건기 부품사 ({len(cols)}, 시총가중)")
    idx.style(ax, "HD건설기계 · 두산밥캣 · 한국 건설기계 부품사"); idx.xticks(ax, df.index); idx.legend(ax, ncol=3)


def chart2(ax, df, caps):
    x = range(len(df))
    for g, items in GROUPS.items():
        s, cols = idx.cap_weighted(df, items, caps)
        if s is not None:
            ax.plot(x, s.values, color=GROUP_COLORS[g], lw=idx.LW, label=f"{g} ({len(cols)})")
    idx.style(ax, "한국 2사 vs. 미국 · 중국 · 일본 피어 (시총가중)"); idx.xticks(ax, df.index); idx.legend(ax, ncol=4)


def footnote(asof):
    names = lambda items: "·".join(n for n, _ in items)
    return "\n".join([
        f"기준일 {asof:%Y.%m.%d}  ·  자료: Yahoo Finance  ·  INDEX = {idx.WEEKS}주({idx.DAYS}거래일) 전 종가 = 100, KOSPI 거래일 기준(해외 휴장일은 직전값)",
        "묶음 지수 = 기준일 USD 시총 가중(고정 가중치), 범례 괄호는 지수에 든 종목 수",
        f"한국 건기 부품사 = {names(KR_PARTS)}",
        f"미국 = {names(US_OEM)} / 중국 = {names(CN_OEM)}",
        f"일본 = {names(JP_OEM)}",
        "④ Kobelco 는 건설기계 자회사가 비상장이라 모회사 Kobe Steel(5406.T) 주가",
    ])


def render(df, caps, out_dir, asof):
    draws = [
        lambda ax: chart1(ax, df, caps),
        lambda ax: chart2(ax, df, caps),
        lambda ax: lines(ax, df, BIG, BIG_STYLE, "대형 OEM — HD건설기계 · CAT · 일본 · 중국", 4),
        lambda ax: lines(ax, df, SMALL, SMALL_STYLE, "소형·농기계 — 두산밥캣 · Deere · CNH · Kobelco · 대동", 3),
    ]
    for fn, draw in zip(OUT_ONE, draws):
        fig, ax = plt.subplots(figsize=(idx.W_IN, idx.H_IN), dpi=base.DPI)
        draw(ax)
        fig.tight_layout()
        base.save_fig(fig, os.path.join(out_dir, fn + ".png"))
    note_in = 0.32 * NOTE_LINES
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
    print(f"🏗️ 건설기계 INDEX 차트 — {len(tickers)}개 {'(데모)' if a.demo else '야후 수집'}")
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

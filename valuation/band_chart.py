"""PER·PBR 밴드 차트 (한국 KRW / 해외 USD).

입력
  data/valuation/annual_uploads.csv  업로드(DataGuide·Bloomberg) 연간 EPS·BPS·ROE   ← ingest_uploads.py
  data/valuation/annual_yahoo.csv    Yahoo 연간 실적·컨센(USD)                    ← yahoo_fundamentals.py
  data/valuation/payout_yahoo.csv    배당성향(미래 BPS 추정)
  data/valuation/multiples.csv       엑셀에서 쓰던 배수(없으면 과거 분포로 자동)
  data/valuation/prices_uploads.csv  한국 일간 수정주가(DataGuide) — 그 뒤는 Yahoo 로 이어 붙임
출력
  output/valuation_band/<섹터>_<종목>_PER.png/.svg · _PBR.png/.svg   (PER 밴드 / PBR 밴드 + ROE, 따로)
  output/valuation_band/band_inputs.csv            차트에 실제로 쓴 연도별 EPS·BPS·ROE 와 출처

연도별 값 고르는 순서(같은 해에 여러 개면 앞이 이김)
  ★ 내 모델(data/valuation/my_model/<티커>.csv — 대시보드 입력, set_model.py) →
  업로드 band(기업별 밴드 시트) → 업로드 model(☞추정입력) → 업로드 actual → 업로드 consensus → Yahoo actual → Yahoo consensus
  BPS 가 없는 미래 연도는 BPS(t) = BPS(t-1) + EPS(t)×(1−배당성향) 로 채운다(배당성향 없으면 30%).
밴드 선: 그해 1월부터 3개월에 걸쳐 전년 값 → 당해 값으로 이어지는 계단(엑셀 '계단' 열과 같은 방식).

실행: python valuation/band_chart.py [--only 079550.KS,CAT] [--start 2019]
"""
import argparse
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yfinance as yf  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "consensus"))
from er_snapshot import COMPANIES  # noqa: E402

DATA = os.path.join(ROOT, "data", "valuation")
OUT = os.path.join(ROOT, "output", "valuation_band")
PRIORITY = [("my", "model"), ("upload", "band"), ("upload", "model"), ("upload", "actual"), ("upload", "consensus"),
            ("yahoo", "actual"), ("yahoo", "consensus")]
PRICE_C = "#A68A64"                       # DAOL 골드 (피어그룹 차트와 같은 색)
BAND_C = ["#4D4D4D", "#7A7A7A", "#9C9C9C", "#BDBDBD", "#D9D9D9"]   # 낮은 배수 → 진하게
ROE_C = "#E3E3E3"


def setup_font():
    have = {f.name for f in font_manager.fontManager.ttflist}
    for name in ["Malgun Gothic", "NanumGothic", "NanumBarunGothic", "AppleGothic",
                 "Noto Sans CJK KR", "Noto Sans KR", "WenQuanYi Zen Hei"]:
        if name in have:
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False


# ---------------------------------------------------------------- 연간 값
def load_annual():
    up = pd.read_csv(os.path.join(DATA, "annual_uploads.csv"))
    up["src"] = "upload"
    frames = [up]
    yp = os.path.join(DATA, "annual_yahoo.csv")
    if os.path.exists(yp):
        y = pd.read_csv(yp)
        y["src"] = "yahoo"
        frames.append(y)
    md = os.path.join(DATA, "my_model")                     # 대시보드에서 넣은 내 모델(종목별 파일) — 최우선
    if os.path.isdir(md):
        for f in sorted(os.listdir(md)):
            if f.endswith(".csv"):
                m = pd.read_csv(os.path.join(md, f))
                m["src"], m["basis"] = "my", "model"
                frames.append(m)
    a = pd.concat(frames, ignore_index=True)
    a["rank"] = a.apply(lambda r: PRIORITY.index((r.src, r.basis)) if (r.src, r.basis) in PRIORITY else 99, axis=1)
    return a


def pick(a, tk, this_year):
    """종목 하나의 연도별 EPS·BPS·ROE (+출처) 표."""
    d = a[a.ticker == tk].copy()
    # 업로드 실적은 '올해' 이후 값이면 버린다(DataGuide 가 진행 중 연도를 실적 칸에 채워 둔 경우)
    d = d[~((d.src == "upload") & (d.basis == "actual") & (d.fy >= this_year))]
    d = d.sort_values("rank").drop_duplicates(["fy", "item"])
    v = d.pivot(index="fy", columns="item", values="value")
    s = d.assign(tag=d.src + ":" + d.basis).pivot(index="fy", columns="item", values="tag")
    for c in ("EPS", "BPS", "ROE"):
        if c not in v:
            v[c] = np.nan
            s[c] = None
    return v.sort_index(), s.reindex(v.index)


def fill_bps(v, src, payout):
    keep = 1 - (payout if payout is not None and 0 <= payout < 1 else 0.3)
    for fy in v.index:
        if pd.isna(v.at[fy, "BPS"]) and (fy - 1) in v.index and pd.notna(v.at[fy - 1, "BPS"]) \
                and pd.notna(v.at[fy, "EPS"]):
            v.at[fy, "BPS"] = v.at[fy - 1, "BPS"] + v.at[fy, "EPS"] * keep
            src.at[fy, "BPS"] = "추정:BPS+EPS×유보율"
    for fy in v.index:                                    # ROE 빈칸 = EPS / 평균 BPS
        if pd.isna(v.at[fy, "ROE"]) and pd.notna(v.at[fy, "EPS"]) and pd.notna(v.at[fy, "BPS"]):
            prev = v.at[fy - 1, "BPS"] if (fy - 1) in v.index and pd.notna(v.at[fy - 1, "BPS"]) else v.at[fy, "BPS"]
            v.at[fy, "ROE"] = v.at[fy, "EPS"] / ((prev + v.at[fy, "BPS"]) / 2) * 100
            src.at[fy, "ROE"] = "계산:EPS/평균BPS"
    return v, src


# ---------------------------------------------------------------- 주가
_fx = {}


def fx_daily(cur):
    if cur not in _fx:
        h = yf.Ticker(f"{cur}USD=X").history(start="2016-01-01")["Close"]
        h.index = h.index.tz_localize(None).normalize()
        _fx[cur] = h
    return _fx[cur]


def price(tk, start, up_px):
    h = yf.Ticker(tk).history(start=f"{start - 1}-10-01", auto_adjust=False)
    s = h["Close"].copy()
    s.index = s.index.tz_localize(None).normalize()
    if tk.endswith(".KS"):
        ku = up_px[up_px.ticker == tk]
        if len(ku):                                       # DataGuide 수정주가 + 그 뒤 Yahoo(겹치는 날 비율로 맞춤)
            k = pd.Series(ku.close.values, index=pd.to_datetime(ku.date))
            last = k.index.max()
            tail = s[s.index > last]
            ov = s.reindex([last]).dropna()
            if len(ov) and ov.iloc[0]:
                tail = tail * (k.iloc[-1] / ov.iloc[0])
            s = pd.concat([k, tail])
        return s, "KRW"
    cur = yf.Ticker(tk).fast_info.get("currency") or "USD"
    if cur in ("GBp", "GBX"):
        s, cur = s / 100, "GBP"
    if cur != "USD":
        s = s * fx_daily(cur).reindex(s.index, method="ffill")
    return s.dropna(), "USD"


# ---------------------------------------------------------------- 밴드
def stair(values, start, end):
    """연도별 값 → 월말 계단(1~3월 선형 전환)."""
    idx = pd.date_range(f"{start}-01-31", f"{end}-12-31", freq="ME")
    out = []
    for d in idx:
        cur, prev = values.get(d.year), values.get(d.year - 1)
        if cur is None or pd.isna(cur):
            out.append(np.nan)
        elif d.month <= 3 and prev is not None and pd.notna(prev):
            out.append(prev + (cur - prev) * d.month / 3)
        else:
            out.append(cur)
    return pd.Series(out, index=idx)


def nice(x):
    if x <= 0:
        return None
    m = 10 ** np.floor(np.log10(x))                       # 가장 가까운 깔끔한 수(1·1.5·2·2.5·3·4·5·6·7·8·10 × 10^n)
    return round(min((k * m for k in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 7, 8, 10)), key=lambda c: abs(c - x)), 6)


def auto_mults(px, base):
    m = px.resample("ME").last()
    r = (m / base.reindex(m.index)).replace([np.inf, -np.inf], np.nan)
    r = r[(base.reindex(m.index) > 0)].dropna()
    if len(r) < 6:
        return None
    qs = [nice(q) for q in np.nanpercentile(r, [10, 30, 50, 70, 90])]
    out = sorted({q for q in qs if q})
    return out if len(out) >= 3 else None


def label_x(v):
    return f"{v:g}x"


def mark_last(ax, px, scale, ccy):
    """마지막 종가에 점만 찍는다. 종가 날짜·값 딱지는 그림 안에 넣지 않는다 — 보고서에 그대로 붙이는 그림이라
    (11/14 사용자) 대시보드가 그림 바로 위에 따로 보여준다(band_inputs.csv 의 px_date·px_last)."""
    d, v = px.index[-1], float(px.iloc[-1])
    ax.scatter([d], [v / scale], s=28, color=PRICE_C, edgecolor="white", linewidth=0.8, zorder=5)


def draw(ax, px, base, mults, title, unit, scale, end, roe=None):
    base = base.where(base > 0)                           # 적자 연도는 밴드 선을 끊는다
    for j, k in enumerate(mults):
        line = base * k / scale
        ax.plot(line.index, line.values, color=BAND_C[min(j, 4)], lw=2.0, zorder=2)
        lv = line.dropna()
        if len(lv):
            ax.annotate(label_x(k), (lv.index[-1], lv.iloc[-1]), xytext=(-2, 4), textcoords="offset points",
                        ha="right", va="bottom", fontsize=9, color="#555")
    ax.plot(px.index, px.values / scale, color=PRICE_C, lw=1.8, zorder=3)
    ax.set_title(title, fontsize=11, pad=6)
    ax.set_xlim(px.index[0].normalize().replace(day=1), pd.Timestamp(f"{end + 1}-01-01"))
    # 세로축: 주가가 잘 보이게(주가 최고치×1.35, 단 둘째 배수 선까지는 보이게). 위쪽 배수 선은 잘려도 된다(엑셀 원본과 같음)
    pmax = float((px / scale).max())
    b2 = (base * mults[min(1, len(mults) - 1)] / scale).max()
    ax.set_ylim(0, max(pmax * 1.35, b2 * 1.1 if pd.notna(b2) else 0))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}" if v >= 10 or v == 0 else f"{v:,.1f}"))
    ax.text(0.0, 1.02, unit, transform=ax.transAxes, fontsize=9, ha="left", va="bottom")
    years = range(px.index[0].year + (px.index[0].month > 1), end + 2)
    ax.set_xticks([pd.Timestamp(f"{y}-01-01") for y in years])
    ax.set_xticklabels([f"{y % 100:02d}" for y in years], fontsize=9)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(labelsize=9)
    if roe is not None:
        ax2 = ax.twinx()
        ax2.fill_between(roe.index, 0, roe.values, step="post", color=ROE_C, zorder=0, lw=0)
        ax2.set_ylim(0, max(10, np.nanmax(roe.values) * 1.6) if roe.notna().any() else 30)
        ax2.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
        ax2.tick_params(labelsize=9)
        ax2.text(1.0, 1.02, "(ROE %)", transform=ax2.transAxes, fontsize=9, ha="right", va="bottom", color="#777")
        ax.set_zorder(ax2.get_zorder() + 1)
        ax.patch.set_visible(False)
        for s in ("top",):
            ax2.spines[s].set_visible(False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--start", type=int, default=2019)
    args = ap.parse_args()
    setup_font()
    os.makedirs(OUT, exist_ok=True)
    this_year = pd.Timestamp.now(tz="Asia/Seoul").year
    a = load_annual()
    mult = pd.read_csv(os.path.join(DATA, "multiples.csv")).set_index("ticker")
    pp = os.path.join(DATA, "payout_yahoo.csv")
    pay = pd.read_csv(pp).set_index("ticker")["payout"].to_dict() if os.path.exists(pp) else {}
    upx = pd.read_csv(os.path.join(DATA, "prices_uploads.csv"))
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    log, done, skipped = [], 0, []
    for sector, region, name, tk in COMPANIES:
        if only and tk not in only:
            continue
        try:
            v, src = pick(a, tk, this_year)
            v, src = fill_bps(v, src, pay.get(tk))
            v = v[(v.index >= args.start - 1) & (v.index <= this_year + 4)]   # 기록은 올해+4(내 모델 입력 범위)까지
            src = src.reindex(v.index)
            if v.EPS.dropna().empty:
                skipped.append(f"{name}(EPS 없음)")
                continue
            end = min(int(v.EPS.dropna().index.max()), this_year + 2)   # 그림은 FY3(올해+2)까지
            px, ccy = price(tk, args.start, upx)
            st = max(args.start, int(v.EPS.dropna().index.min()))     # Yahoo 만 있는 종목은 실적 첫해(2022)부터
            px = px[px.index >= f"{st}-01-01"]
            eps_m = stair(v.EPS.to_dict(), st, end)
            bps_m = stair(v.BPS.to_dict(), st, end)
            roe_y = v.ROE.reindex(range(st, end + 1))
            roe_m = pd.Series([roe_y.get(d.year) for d in eps_m.index], index=eps_m.index)
            per_k = pbr_k = None
            if tk in mult.index:
                per_k = [float(x) for x in str(mult.at[tk, "per"]).split()] or None
                pbr_k = [float(x) for x in str(mult.at[tk, "pbr"]).split()] or None
            per_k = per_k or auto_mults(px, eps_m) or [5, 10, 15, 20, 25]
            pbr_k = pbr_k or auto_mults(px, bps_m) or [0.5, 1, 1.5, 2, 3]
            scale, unit = (1000, "(천원)") if ccy == "KRW" and px.max() >= 10000 else (1, f"({ccy})")
            used = set(src[["EPS", "BPS"]].stack().dropna())
            names_ = []
            if any(u.startswith("my") for u in used):
                names_.append("내 모델")
            if any(u.startswith("upload") for u in used):
                names_.append("DataGuide" if ccy == "KRW" else "Bloomberg")
            if any(u.startswith("yahoo") for u in used):
                names_.append("Yahoo")
            foot = (f"자료: {'·'.join(names_)} · 종가 {px.index[-1]:%Y-%m-%d} · "
                    f"밴드 = 연도별 {{}}×배수(올해 이후 추정)")
            fn = f"{sector}_{name}".replace("/", "_").replace(" ", "")
            # PER · PBR 을 따로 저장 — 보고서에 하나씩 붙일 수 있게(<파일>_PER / _PBR)
            for kind, base_m, ks, roe_ in (("PER", eps_m, per_k, None), ("PBR", bps_m, pbr_k, roe_m)):
                fig, ax = plt.subplots(figsize=(5.2, 3.5), dpi=150)
                draw(ax, px, base_m, ks, f"{name} {kind} Band", unit, scale, end, roe=roe_)
                mark_last(ax, px, scale, ccy)
                fig.text(0.01, 0.005, foot.format("EPS" if kind == "PER" else "BPS"), fontsize=7, color="#888")
                fig.tight_layout(rect=(0, 0.03, 1, 1))
                for ext in ("png", "svg"):
                    fig.savefig(os.path.join(OUT, f"{fn}_{kind}.{ext}"), bbox_inches="tight")
                plt.close(fig)
            for fy in v.index:
                log.append(dict(sector=sector, name=name, ticker=tk, ccy=ccy, fy=fy,
                                EPS=v.at[fy, "EPS"], EPS_src=src.at[fy, "EPS"],
                                BPS=v.at[fy, "BPS"], BPS_src=src.at[fy, "BPS"],
                                ROE=v.at[fy, "ROE"], ROE_src=src.at[fy, "ROE"],
                                per_mults=" ".join(f"{k:g}" for k in per_k),
                                pbr_mults=" ".join(f"{k:g}" for k in pbr_k),
                                px_date=f"{px.index[-1]:%Y-%m-%d}", px_last=round(float(px.iloc[-1]), 2),
                                chart_end=end))
            done += 1
            print(f"OK   {tk:<10} {name:<20} {ccy} FY{int(v.index.min())}~{end}")
        except Exception as ex:
            skipped.append(f"{name}({ex})")
            print(f"FAIL {tk:<10} {name:<20} {ex}")
    if log and not only:                                  # --only 시험 실행은 전체 기록을 덮어쓰지 않는다
        pd.DataFrame(log).to_csv(os.path.join(OUT, "band_inputs.csv"), index=False, encoding="utf-8-sig")
    print(f"\n완료 {done}종목" + (f" / 건너뜀: {', '.join(skipped)}" if skipped else ""))


if __name__ == "__main__":
    main()

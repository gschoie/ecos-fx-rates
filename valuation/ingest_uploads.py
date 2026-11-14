"""업로드된 밴드 엑셀(DataGuide·Bloomberg) → 표준 DB.

  data/valuation/raw/*.xlsx  ─▶  data/valuation/annual_uploads.csv   연간 EPS·BPS·ROE
                                data/valuation/multiples.csv         엑셀에서 쓰던 밴드 배수
                                data/valuation/prices_uploads.csv    한국 종목 일간 수정주가(DataGuide)

annual 열: ticker,name,fy,item(EPS|BPS|ROE),basis,value,currency,source,asof
  basis  actual    = DataGuide 실적(발표기준)
         band      = 다종목 파일의 기업별 밴드 시트 12월 행(엑셀 차트가 실제로 쓰는 값 — 밴드에서 최우선)
         model     = ☞추정입력 시트 값(과거는 조정 실적, 미래는 직접 추정)
         consensus = DataGuide 컨센서스(중앙값) / Bloomberg BEST(당해 이후)
  ROE 는 % 단위. 티커는 야후 형식(009540.KS, CAT, 6301.T …)으로 통일.

새 파일을 raw/ 에 넣고 다시 돌리면 전부 다시 만든다(같은 키는 asof 가 최신인 파일이 이김).
파일명 규칙: DG_*_YYYYMMDD.xlsx(DataGuide) / BB_*_YYYYMMDD.xlsx(Bloomberg).
"""
import datetime as dt
import glob
import os
import re

import openpyxl
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "data", "valuation", "raw")
OUT = os.path.join(ROOT, "data", "valuation")

BB_SUFFIX = {"US": "", "JT": ".T", "SS": ".ST", "LN": ".L", "GR": ".DE", "FP": ".PA", "IM": ".MI",
             "NO": ".OL", "SP": ".SI", "KS": ".KS"}


def num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def dg_ticker(code):                       # 'A009540' → '009540.KS'
    return f"{str(code).lstrip('A')}.KS"


def bb_ticker(bb):                         # '6301 JT EQUITY' → '6301.T', '600031 CH' → '600031.SS'
    p = str(bb).upper().split()
    if len(p) < 2:
        return bb
    if p[1] == "CH":
        return p[0] + (".SS" if p[0].startswith("6") else ".SZ")
    return p[0] + BB_SUFFIX.get(p[1], "")


class Sink:
    def __init__(self):
        self.a, self.m, self.p = [], [], []

    def px(self, tk, d, v, src):
        if isinstance(d, dt.datetime) and num(v) and v > 0:
            self.p.append(dict(ticker=tk, date=d.date(), close=float(v), source=src))

    def add(self, tk, name, fy, item, basis, v, cur, src, asof):
        if not num(v):
            return
        if basis != "actual" and v == 0:     # 엑셀 빈칸이 0 으로 들어온 것
            return
        self.a.append(dict(ticker=tk, name=name, fy=int(fy), item=item, basis=basis, value=float(v),
                           currency=cur, source=src, asof=asof))

    def mult(self, ws, tk, name, src, asof):
        r4 = list(ws.iter_rows(min_row=4, max_row=4, max_col=20, values_only=True))[0]
        per = [x for x in r4[7:12] if num(x)]
        pbr = [x for x in r4[15:20] if num(x)]
        if per or pbr:
            self.m.append(dict(ticker=tk, name=name, per=" ".join(f"{x:g}" for x in per),
                               pbr=" ".join(f"{x:g}" for x in pbr), source=src, asof=asof))


def band_dec_rows(ws):
    """밴드 시트(C=날짜, D=종가, E=EPS, M=BPS, U=ROE)에서 12월 행 → {연도: (EPS,BPS,ROE)}."""
    out = {}
    for r in ws.iter_rows(min_row=6, max_col=21, values_only=True):
        d = r[2]
        if isinstance(d, dt.datetime) and d.month == 12:
            out[d.year] = (r[4], r[12], r[20] if len(r) > 20 else None)
    return out


def parse_dg_single(wb, s, src, asof):
    act = list(wb["Actual"].iter_rows(values_only=True))
    name = act[0][1].replace("종가(원)", "")
    code = list(wb["주가"].iter_rows(min_row=10, max_row=10, values_only=True))[0][1]
    tk = dg_ticker(code)
    hdr = act[0]
    col = {}
    for i, h in enumerate(hdr):
        if not h or "TTM" in str(h):
            continue
        for k, it in (("EPS(지배)", "EPS"), ("BPS(지배)", "BPS"), ("ROE(지배)", "ROE")):
            if k in h:
                col[it] = i
    for r in act:
        if isinstance(r[0], dt.datetime) and r[0].month == 12:
            for it, i in col.items():
                s.add(tk, name, r[0].year, it, "actual", r[i], "KRW", src, asof)
    # Forecast: B..G = 모델(C EPS, D BPS, G ROE%) / I..L = 컨센(I BPS, J EPS, L ROE%)
    for r in wb["Forecast"].iter_rows(min_row=3, max_row=24, values_only=True):
        if not isinstance(r[0], dt.datetime):
            continue
        y = r[0].year
        s.add(tk, name, y, "EPS", "model", r[2], "KRW", src, asof)
        s.add(tk, name, y, "BPS", "model", r[3], "KRW", src, asof)
        s.add(tk, name, y, "ROE", "model", r[6], "KRW", src, asof)
        s.add(tk, name, y, "BPS", "consensus", r[8], "KRW", src, asof)
        s.add(tk, name, y, "EPS", "consensus", r[9], "KRW", src, asof)
        s.add(tk, name, y, "ROE", "consensus", r[11], "KRW", src, asof)
    # 배수: Band 시트 4행
    s.mult(wb["Band"], tk, name, src, asof)
    for r in wb["주가"].iter_rows(min_row=14, max_col=2, values_only=True):   # 일간 수정주가
        s.px(tk, r[0], r[1], src)


def parse_dg_multi(wb, s, src, asof):
    g = list(wb["GET"].iter_rows(values_only=True))
    names, codes, items = g[2], g[3], g[4]
    cols = [c for c in range(4, len(codes)) if codes[c] and items[c] in ("EPS", "BPS", "ROE")]
    for r in g:                                       # 실적: C=연도, D='결산'
        if r[3] == "결산" and num(r[2]):
            for c in cols:
                s.add(dg_ticker(codes[c]), names[c], r[2], items[c], "actual", r[c], "KRW", src, asof)
    # ⚠️ ☞추정입력 시트는 종목 열 순서가 GET 시트와 다르다(8~28번째) — 반드시 이 시트 자신의 머리글을 쓴다.
    e = list(wb["☞추정입력+컨센GET"].iter_rows(values_only=True))
    enames, ecodes, eitems = e[2], e[3], e[4]
    ecols = [c for c in range(4, len(ecodes)) if ecodes[c] and eitems[c] in ("EPS", "BPS", "ROE")]
    con = next(i for i, r in enumerate(e) if len(r) > 4 and r[4] == "CON")     # 컨센 블록: 바로 윗줄이 코드
    ccodes = e[con - 1]
    c2n = {c: n for n, c in zip(enames, ecodes) if c}
    for i, r in enumerate(e):
        if r[2] is None and num(r[3]) and 2000 < r[3] < 2040:      # 모델 블록: D=연도, ROE 는 배율
            for c in ecols:
                v = r[c] * 100 if eitems[c] == "ROE" and num(r[c]) else r[c]
                s.add(dg_ticker(ecodes[c]), enames[c], r[3], eitems[c], "model", v, "KRW", src, asof)
        if i > con and num(r[2]) and r[3] == "결산":                # 컨센 블록: C=연도
            for c in ecols:
                if ccodes[c]:
                    s.add(dg_ticker(ccodes[c]), c2n.get(ccodes[c], ""), r[2], eitems[c], "consensus", r[c], "KRW", src, asof)
    gp = list(wb["GET주가"].iter_rows(values_only=True))            # 일간 수정주가: C=날짜, D..=종목
    pcode = next(r for r in gp if r[2] == "코드")
    for r in gp:
        if isinstance(r[2], dt.datetime):
            for c in range(3, len(r)):
                if pcode[c] and str(pcode[c]) != "A0":
                    s.px(dg_ticker(pcode[c]), r[2], r[c], src)
    n2c = {n: c for n, c in zip(names, codes) if n}
    for ws in wb.worksheets:
        if ws.title.startswith(">") or ws.max_column not in (21, 23, 256):
            continue
        nm = list(ws.iter_rows(min_row=3, max_row=3, max_col=4, values_only=True))[0][3]
        if nm in n2c:
            tk = dg_ticker(n2c[nm])
            s.mult(ws, tk, nm, src, asof)
            # 기업별 밴드 시트 12월 행 = 엑셀 차트가 실제로 쓰는 값(basis=band). ☞추정입력 표에 임시값이
            # 남아 있는 종목(한국항공우주 등)이 있어 밴드에서는 이 값을 가장 먼저 쓴다.
            for y, (eps, bps, roe) in band_dec_rows(ws).items():
                s.add(tk, nm, y, "EPS", "band", eps, "KRW", src, asof)
                s.add(tk, nm, y, "BPS", "band", bps, "KRW", src, asof)
                s.add(tk, nm, y, "ROE", "band", roe * 100 if num(roe) else roe, "KRW", src, asof)


def parse_bb(wb, s, src, asof):
    """Bloomberg 판: 원본 시트는 #NAME? 라 기업별 밴드 시트 12월 행을 연간값으로 쓴다(USD).
    올해 이후 = BEST(컨센), 그 전 = 실적. 한국 종목(KS)은 DataGuide 가 있으니 건너뛴다."""
    t = {r[3]: r[5] for r in wb["티커"].iter_rows(min_row=5, values_only=True) if r[3] and r[5]}
    this_year = int(asof[:4])
    for ws in wb.worksheets:
        if ws.title.startswith(">") or ws.max_column != 21:
            continue
        nm = list(ws.iter_rows(min_row=3, max_row=3, max_col=4, values_only=True))[0][3]
        if nm not in t or " KS " in f" {t[nm].upper()} ":
            continue
        tk = bb_ticker(t[nm])
        for y, (eps, bps, roe) in band_dec_rows(ws).items():
            basis = "actual" if y < this_year else "consensus"
            s.add(tk, nm, y, "EPS", basis, eps, "USD", src, asof)
            s.add(tk, nm, y, "BPS", basis, bps, "USD", src, asof)
            s.add(tk, nm, y, "ROE", basis, roe * 100 if num(roe) else roe, "USD", src, asof)
        s.mult(ws, tk, nm, src, asof)


def main():
    s = Sink()
    for f in sorted(glob.glob(os.path.join(RAW, "*.xlsx"))):
        base = os.path.basename(f)
        m = re.search(r"(20\d{6})", base)
        asof = m.group(1) if m else ""
        wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
        if base.startswith("BB_"):
            parse_bb(wb, s, base, asof)
        elif "Actual" in wb.sheetnames:
            parse_dg_single(wb, s, base, asof)
        elif "GET" in wb.sheetnames:
            parse_dg_multi(wb, s, base, asof)
        else:
            print(f"⚠️ 형식을 모르는 파일: {base}")
            continue
        print(f"✓ {base}")
    a = pd.DataFrame(s.a).sort_values("asof").drop_duplicates(["ticker", "fy", "item", "basis"], keep="last")
    a = a.sort_values(["ticker", "item", "basis", "fy"])
    a.to_csv(os.path.join(OUT, "annual_uploads.csv"), index=False, encoding="utf-8-sig")
    m = pd.DataFrame(s.m).sort_values("asof").drop_duplicates("ticker", keep="last").sort_values("ticker")
    m.to_csv(os.path.join(OUT, "multiples.csv"), index=False, encoding="utf-8-sig")
    p = pd.DataFrame(s.p)
    p = p[(p.date >= dt.date(2017, 1, 1)) & (pd.to_datetime(p.date).dt.weekday < 5)]   # 밴드는 2019~ · 주말 채움 제거
    p = p.sort_values("source").drop_duplicates(["ticker", "date"], keep="last")
    p.sort_values(["ticker", "date"]).to_csv(os.path.join(OUT, "prices_uploads.csv"), index=False, encoding="utf-8-sig")
    print(f"prices_uploads.csv {len(p)}행 · {p.ticker.nunique()}종목")
    print(f"annual_uploads.csv {len(a)}행 · {a.ticker.nunique()}종목 / multiples.csv {len(m)}종목")


if __name__ == "__main__":
    main()

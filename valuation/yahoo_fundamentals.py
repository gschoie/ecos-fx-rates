"""Yahoo → 해외 종목 연간 EPS·BPS·ROE(실적 약 4년) + FY1·FY2 컨센 EPS, 전부 USD.

  출력: data/valuation/annual_yahoo.csv  (열은 annual_uploads.csv 와 같음 + local, fin_ccy)
        data/valuation/payout_yahoo.csv  (배당성향 — 미래 BPS 추정용)

종목: consensus/er_snapshot.py 의 COMPANIES 전부. 한국(.KS)은 원화 그대로 두고 업로드에 없는 해만 채운다.
  - 업로드(Bloomberg) 데이터가 있는 종목도 받아 둔다. 밴드에서는 업로드가 우선이고 Yahoo 는 빈 해만 채운다.
환산: 실적은 결산일 환율, 컨센은 오늘 환율(financialCurrency 기준 — Yangzijiang 은 SGD 상장·CNY 보고).
회계연도: 결산월 1~5월이면 전년도 FY 로 본다(일본 3월 결산 → FY2025 = 2026.3).
Yahoo 의 0y = 진행 중인 회계연도 = 마지막 실적 FY + 1.
"""
import os
import sys
import time

import pandas as pd
import yfinance as yf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "consensus"))
from er_snapshot import COMPANIES  # noqa: E402

OUT = os.path.join(ROOT, "data", "valuation")
_fx = {}


def fx_series(cur):
    if cur not in _fx:
        h = yf.Ticker(f"{cur}USD=X").history(period="10y")["Close"]
        _fx[cur] = h.tz_localize(None) if h.index.tz is not None else h
    return _fx[cur]


def rate(cur, d=None):
    if cur in (None, "USD"):
        return 1.0
    s = fx_series(cur)
    return float(s.iloc[-1] if d is None else s[: pd.Timestamp(d)].iloc[-1])


def fy_of(d):
    return d.year if d.month >= 6 else d.year - 1


def get(df, row, col):
    if df is None or row not in df.index or col not in df.columns:
        return None
    v = df.at[row, col]
    return None if pd.isna(v) else float(v)


def rows_for(sector, name, tk, today):
    t = yf.Ticker(tk)
    info = t.info
    fc = info.get("financialCurrency") or info.get("currency")
    ccy = "KRW" if tk.endswith(".KS") else "USD"      # 한국은 원화 그대로, 해외는 USD 환산
    if ccy == "KRW":
        fc = None
    i, b = t.income_stmt, t.balance_sheet
    out = []

    def add(fy, it, basis, v, local, fy_end=None):
        out.append(dict(ticker=tk, name=name, fy=fy, item=it, basis=basis, value=v, currency=ccy,
                        source="yahoo", asof=today, local=local, fin_ccy=fc, fy_end=fy_end, sector=sector))

    for d in i.columns:
        eps, ni = get(i, "Diluted EPS", d), get(i, "Net Income Common Stockholders", d)
        eq, sh = get(b, "Stockholders Equity", d), get(b, "Ordinary Shares Number", d)
        r, fy = rate(fc, d), fy_of(d)
        if eps is not None:
            add(fy, "EPS", "actual", eps * r, eps, d.date())
        if eq and sh:
            add(fy, "BPS", "actual", eq / sh * r, eq / sh, d.date())
        if ni is not None and eq:
            add(fy, "ROE", "actual", ni / eq * 100, None, d.date())
    e = t.earnings_estimate
    if e is not None and len(i.columns):
        base, r = fy_of(max(i.columns)), rate(fc)
        for k, p in ((1, "0y"), (2, "+1y")):
            if p in e.index and pd.notna(e.at[p, "avg"]):
                add(base + k, "EPS", "consensus", float(e.at[p, "avg"]) * r, float(e.at[p, "avg"]))
    payout = info.get("payoutRatio")
    return out, dict(ticker=tk, payout=payout)


def main():
    today = pd.Timestamp.now(tz="Asia/Seoul").strftime("%Y%m%d")
    rows, pay = [], []
    for sector, region, name, tk in COMPANIES:
        for attempt in range(3):
            try:
                r, p = rows_for(sector, name, tk, today)
                rows += r
                pay.append(p)
                print(f"OK   {tk:<10} {name:<22} {len(r)}행")
                break
            except Exception as ex:  # 야후 429 등 일시 오류
                print(f"RETRY {tk} {ex}")
                time.sleep(20)
        time.sleep(1)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "annual_yahoo.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(pay).to_csv(os.path.join(OUT, "payout_yahoo.csv"), index=False, encoding="utf-8-sig")
    print(f"annual_yahoo.csv {len(rows)}행")


if __name__ == "__main__":
    main()

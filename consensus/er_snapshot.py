# -*- coding: utf-8 -*-
"""건설기계·방산 글로벌 피어 Earnings Revision(ER) 일별 스냅샷 적재.

Yahoo Finance 의 애널리스트 추정치 페이지(yfinance)는 '오늘 시점'의 값만 준다.
  - eps_revisions     : 최근 7일/30일 EPS 상향·하향 건수
  - eps_trend         : 컨센서스 EPS 현재 / 7·30·60·90일 전
  - earnings_estimate : 추정 애널리스트 수
과거 이력은 무료로 구할 수 없으므로 매일 한 번 받아 CSV 에 '쌓아' 시계열을 만든다.

출력 (output/earnings_revision/)
  - er_history.csv : 누적 원자료(long). 키 = (date, ticker, period). 같은 날 재실행 시 덮어쓴다.
  - er_latest.csv  : 오늘 요약(종목 1줄, FY1·FY2)
  sector 열(건설기계/방산)로 그룹을 구분한다.

ER 정의(Bloomberg 식과 같은 꼴):
  ER30 = (30일 상향 건수 − 30일 하향 건수) / 애널리스트 수 × 100   (−100 ~ +100)
  ER7  = 7일 기준 동일
  EPS 1M/3M 변화율 = 현재 컨센 / 30·90일 전 컨센 − 1  (Yahoo 가 90일치를 주므로 첫날부터 계산 가능)

period: 0y = 이번 회계연도(FY1), +1y = 다음 회계연도(FY2). 일본 종목은 3월 결산 기준.

실행: python consensus/er_snapshot.py
종목은 아래 COMPANIES 만 고치면 된다. (섹터, 지역, 표시명, 야후 티커)
"""

import os
import sys
import time
from datetime import datetime, timedelta, timezone

import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_CON = [
    ("미국", "Caterpillar", "CAT"),
    ("미국", "Deere", "DE"),
    ("미국", "CNH Industrial", "CNH"),
    ("미국", "United Rentals", "URI"),
    ("일본", "Komatsu", "6301.T"),
    ("일본", "Hitachi CM", "6305.T"),
    ("일본", "Kubota", "6326.T"),
    ("일본", "Kobelco(Kobe Steel)", "5406.T"),  # 코벨코건기는 비상장 → 모회사 고베제강
    ("일본", "Takeuchi", "6432.T"),
    ("스웨덴", "Volvo", "VOLV-B.ST"),
    ("중국", "SANY", "600031.SS"),
    ("중국", "XCMG", "000425.SZ"),
]
_DEF = [  # 방산 INDEX ③ 의 미국 체계·유럽 체계와 같은 구성
    ("미국", "Lockheed Martin", "LMT"),
    ("미국", "RTX", "RTX"),
    ("미국", "Northrop Grumman", "NOC"),
    ("미국", "General Dynamics", "GD"),
    ("미국", "L3Harris", "LHX"),
    ("미국", "Boeing", "BA"),
    ("미국", "Huntington Ingalls", "HII"),
    ("유럽", "Rheinmetall", "RHM.DE"),
    ("유럽", "BAE Systems", "BA.L"),
    ("유럽", "Thales", "HO.PA"),
    ("유럽", "Leonardo", "LDO.MI"),
    ("유럽", "Saab", "SAAB-B.ST"),
    ("유럽", "Hensoldt", "HAG.DE"),
    ("유럽", "Renk", "R3NK.DE"),
    ("유럽", "Kongsberg", "KOG.OL"),
]
COMPANIES = [("건설기계", *c) for c in _CON] + [("방산", *c) for c in _DEF]

PERIODS = ["0q", "+1q", "0y", "+1y"]
OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output", "earnings_revision")
HIST = os.path.join(OUT_DIR, "er_history.csv")
LATEST = os.path.join(OUT_DIR, "er_latest.csv")
KST = timezone(timedelta(hours=9))

COLS = ["date", "sector", "region", "name", "ticker", "period", "currency", "n_analysts",
        "up7", "down7", "up30", "down30",
        "eps_cur", "eps_7d", "eps_30d", "eps_60d", "eps_90d", "er7", "er30", "eps_chg_1m", "eps_chg_3m"]


def _num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(v) else v


def _eps(x):
    # Yahoo 는 빈 값을 0.00000 으로 내려주는 경우가 있다 → 결측 처리
    v = _num(x)
    return None if v is None or v == 0 else v


def _chg(cur, old):
    return None if cur is None or old is None else cur / old - 1


def _er(up, dn, n):
    if up is None or dn is None or not n:
        return None
    return max(-100.0, min(100.0, (up - dn) / n * 100))


def fetch(ticker):
    import yfinance as yf

    tk = yf.Ticker(ticker)
    last = None
    for attempt in range(3):
        try:
            rev, trend, est = tk.eps_revisions, tk.eps_trend, tk.earnings_estimate
            if rev is None or rev.empty:
                raise ValueError("eps_revisions 비어 있음")
            return rev, trend, est
        except Exception as e:  # 네트워크·크럼 오류 재시도
            last = e
            time.sleep(3 * (attempt + 1))
    raise RuntimeError(f"{ticker}: {last}")


def rows_for(sector, region, name, ticker, today):
    rev, trend, est = fetch(ticker)
    out = []
    for p in PERIODS:
        if p not in rev.index:
            continue
        r = rev.loc[p]
        t = trend.loc[p] if trend is not None and p in trend.index else {}
        e = est.loc[p] if est is not None and p in est.index else {}
        n = _num(e.get("numberOfAnalysts"))
        up7, dn7 = _num(r.get("upLast7days")), _num(r.get("downLast7Days"))
        up30, dn30 = _num(r.get("upLast30days")), _num(r.get("downLast30days"))
        cur, d7, d30, d60, d90 = (_eps(t.get(k)) for k in ("current", "7daysAgo", "30daysAgo", "60daysAgo", "90daysAgo"))
        if all(v is None for v in (up30, dn30, cur)):
            continue
        out.append({
            "date": today, "sector": sector, "region": region, "name": name, "ticker": ticker, "period": p,
            "currency": r.get("currency"), "n_analysts": n,
            "up7": up7, "down7": dn7, "up30": up30, "down30": dn30,
            "eps_cur": cur, "eps_7d": d7, "eps_30d": d30, "eps_60d": d60, "eps_90d": d90,
            "er7": _er(up7, dn7, n), "er30": _er(up30, dn30, n),
            "eps_chg_1m": _chg(cur, d30), "eps_chg_3m": _chg(cur, d90),
        })
    return out


def main():
    today = datetime.now(KST).strftime("%Y-%m-%d")
    rows, failed = [], []
    for i, (sector, region, name, ticker) in enumerate(COMPANIES):
        if i:
            time.sleep(1)  # 야후 429(rate limit) 완화
        try:
            r = rows_for(sector, region, name, ticker, today)
            rows += r
            print(f"OK   {ticker:<10} {name:<20} {len(r)}행")
        except Exception as e:
            failed.append(ticker)
            print(f"FAIL {ticker:<10} {name:<20} {e}")
    if not rows:
        sys.exit("전 종목 수집 실패 — 기존 이력 유지, 종료")

    new = pd.DataFrame(rows, columns=COLS)
    os.makedirs(OUT_DIR, exist_ok=True)
    if os.path.exists(HIST):
        old = pd.read_csv(HIST, dtype={"ticker": str})
        if "sector" not in old.columns:  # sector 열 추가 이전(건설기계만 있던) 이력
            old.insert(1, "sector", "건설기계")
        # 같은 날 재실행: 이번에 성공한 종목만 교체(실패 종목의 기존 값은 보존)
        done = set(new["ticker"])
        old = old[~((old["date"] == today) & old["ticker"].isin(done))]
        hist = pd.concat([old, new], ignore_index=True)[COLS]
    else:
        hist = new
    hist = hist.sort_values(["date", "ticker", "period"]).reset_index(drop=True)
    hist.to_csv(HIST, index=False, encoding="utf-8-sig", float_format="%.6g")

    # 오늘 요약: 종목 1줄 × (FY1, FY2)
    order = {t: i for i, (*_, t) in enumerate(COMPANIES)}
    cur = hist[hist["date"] == today]
    wide = []
    for tkr, g in sorted(cur.groupby("ticker"), key=lambda x: order.get(x[0], 99)):
        row = {"date": today, "sector": g["sector"].iat[0], "region": g["region"].iat[0], "name": g["name"].iat[0], "ticker": tkr}
        for p, lab in (("0y", "FY1"), ("+1y", "FY2")):
            s = g[g["period"] == p]
            for c in ("n_analysts", "up30", "down30", "er30", "eps_chg_1m", "eps_chg_3m"):
                row[f"{lab}_{c}"] = s[c].iat[0] if len(s) else None
        wide.append(row)
    pd.DataFrame(wide).to_csv(LATEST, index=False, encoding="utf-8-sig", float_format="%.4g")

    print(f"\n{today}: {len(new)}행 적재 → {os.path.relpath(HIST)} (누적 {hist['date'].nunique()}일)")
    if failed:
        print("실패:", ", ".join(failed))


if __name__ == "__main__":
    main()

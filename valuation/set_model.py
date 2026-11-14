"""대시보드(PE·PB 밴드 › ✏️ 내 모델)에서 넣은 추정치를 data/valuation/my_model/<티커>.csv 로 저장.

입력은 환경변수로만 받는다(워크플로 입력을 셸에 끼워 넣지 않기 위해):
  TICKER  예: 079550.KS  — consensus/er_snapshot.py 의 COMPANIES 에 있는 티커만
  MODEL   "fy,item,value;fy,item,value;…"  item = EPS|BPS|ROE, fy = 올해~올해+4
          빈 값 또는 "CLEAR" = 이 종목의 내 모델 삭제(→ 업로드 값·컨센서스로 돌아감)
단위: 한국 EPS·BPS = 원, 해외 = USD, ROE = %.
이 종목 파일을 통째로 새로 쓴다(넣지 않은 연도·항목은 내 모델에서 빠진다 → 그 칸은 다음 우선순위 값).
종목별 파일이라 여러 종목을 연달아 넣어도 커밋이 충돌하지 않는다.
"""
import os
import re
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "consensus"))
from er_snapshot import COMPANIES  # noqa: E402

DIR = os.path.join(ROOT, "data", "valuation", "my_model")


def main():
    tk = os.environ.get("TICKER", "").strip()
    raw = os.environ.get("MODEL", "").strip()
    names = {t: n for _, _, n, t in COMPANIES}
    if tk not in names:
        sys.exit(f"모르는 티커: {tk!r} — COMPANIES 에 있는 종목만 넣을 수 있습니다")
    os.makedirs(DIR, exist_ok=True)
    path = os.path.join(DIR, f"{tk}.csv")
    if raw in ("", "CLEAR"):
        if os.path.exists(path):
            os.remove(path)
        print(f"{names[tk]}({tk}) 내 모델 삭제")
        return
    now = pd.Timestamp.now(tz="Asia/Seoul")
    rows = []
    for part in raw.split(";"):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(20\d\d),(EPS|BPS|ROE),(-?\d+(?:\.\d+)?)", part)
        if not m:
            sys.exit(f"형식 오류: {part!r} (fy,item,value)")
        fy, item, val = int(m.group(1)), m.group(2), float(m.group(3))
        if not now.year <= fy <= now.year + 4:
            sys.exit(f"연도 범위 밖: {fy} (올해~올해+4 만)")
        if item == "ROE" and abs(val) > 500:
            sys.exit(f"ROE 값이 이상합니다: {val}%")
        rows.append(dict(ticker=tk, name=names[tk], fy=fy, item=item, value=val,
                         currency="KRW" if tk.endswith(".KS") else "USD",
                         source="dashboard", asof=now.strftime("%Y%m%d")))
    if not rows:
        sys.exit("넣을 값이 없습니다")
    df = pd.DataFrame(rows).drop_duplicates(["fy", "item"], keep="last").sort_values(["item", "fy"])
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"{names[tk]}({tk}) 내 모델 {len(df)}칸 저장 → {os.path.relpath(path, ROOT)}")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""한화엔진(구 두산엔진·HSD엔진) 사업부문별 매출 시계열 → 엑셀.

출처: 분기·반기·사업보고서 'II. 사업의 내용 > 주요 제품(및 서비스)' 표의 사업부문별 매출액.
DART 웹사이트에서 받으므로 오픈API 키가 필요 없다.

- 보고서 값은 연초부터 누적(YTD)이다. 3개월 단위 값은 직전 분기 누적을 빼서 만든다.
- 2010.3Q 이전 보고서는 부문별 '비율(%)'만 공시 → '매출실적' 표의 당기 총매출 × 비율로 추정.
  (2005~2006년 분기보고서의 부문 비율은 직전 사업보고서 값을 그대로 옮겨 적은 것이다.)
- '기타' = 합계 − 선박엔진 (디젤발전·부품(AM)·임대 등. 연도별 세부 부문은 '원자료' 시트)
- 받아 둔 보고서는 extracted.json 에 표만 저장해 두고, 다음 실행 때는 새 보고서만 받는다.
"""
import json
import os
import re
import sys
import time

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dart_web  # noqa: E402
from tables import tables  # noqa: E402

CORP_NAME = "한화엔진"
START_YEAR = 2005
STORE = os.path.join(HERE, "extracted.json")
RAW_CACHE = os.path.join(HERE, "cache")  # 로컬 개발용 원문 캐시(있으면 사용)
OUT = os.path.join(os.path.dirname(HERE), "output", "한화엔진_사업부문별_매출.xlsx")

UNIT = "백만원"
HEADER_FILL = PatternFill("solid", fgColor="CFE8F3")
EST_FONT = Font(color="808080", italic=True)
NUM_FMT = "#,##0"


# ── 표 찾기 ─────────────────────────────────────────────────────────────
def _nospace(s):
    return re.sub(r"\s+", "", s or "")


def _header_rows(grid):
    n = 0
    for row in grid:
        if row and _nospace(row[0]) == "사업부문":
            n += 1
        else:
            break
    return n


def find_product_table(tbls):
    """'주요 제품 등의 현황' 표: 사업부문 | … | 구체적용도 | … | 매출액 | 비율."""
    for t in tbls:
        g = t["grid"]
        if not g or _header_rows(g) == 0:
            continue
        h = _nospace(" ".join(g[0]))
        if "구체적" in h or "주요제품" in h:
            return g
    return None


def find_sales_table(tbls):
    """'매출실적' 표: 사업부문 | 매출유형 | 품목 | … | 당기 | 전기 | …."""
    for t in tbls:
        g = t["grid"]
        if not g or _header_rows(g) == 0:
            continue
        h = _nospace(" ".join(g[0]))
        if "매출유형" in h and "구체적" not in h and "주요제품" not in h:
            return g
    return None


# ── 숫자 ────────────────────────────────────────────────────────────────
def to_num(s):
    s = (s or "").strip()
    m = re.search(r"\(?-?\d[\d,]*(\.\d+)?\)?", s)
    if not m:
        return None
    tok = m.group(0)
    neg = tok.startswith("(") and tok.endswith(")") or tok.lstrip("(").startswith("-")
    v = float(re.sub(r"[^\d.]", "", tok))
    return -v if neg else v


def _ratio_in(s):
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", s or "")
    return float(m.group(1)) if m else None


def is_total(label):
    return _nospace(label).startswith(("합계", "총계"))


# ── 보고서 1건 파싱 ─────────────────────────────────────────────────────
def parse_product(grid):
    """→ [{'seg','type','item','amount','ratio'}], amount 신뢰 여부."""
    nh = _header_rows(grid)
    head = [_nospace(" ".join(dict.fromkeys(col))) for col in zip(*grid[:nh])]
    amt_col = ratio_col = combo_col = None
    for i, h in enumerate(head):
        if "매출액(비율)" in h:
            combo_col = i
        elif "매출액" in h and amt_col is None:
            amt_col = i
        elif "비율" in h and ratio_col is None:
            ratio_col = i
    type_col = next((i for i, h in enumerate(head) if "매출유형" in h), None)
    item_col = next((i for i, h in enumerate(head) if "품목" in h or "주요제품" in h), None)

    rows = []
    for r in grid[nh:]:
        if not r or not r[0].strip():
            continue
        amount = to_num(r[amt_col]) if amt_col is not None and amt_col < len(r) else None
        ratio = None
        if ratio_col is not None and ratio_col < len(r):
            ratio = to_num(r[ratio_col])
        if combo_col is not None and combo_col < len(r):
            # 2005~2009: '17,413 (96%)' 또는 '96%' — 금액이 매출이 아닌 경우가 있어 비율만 쓴다
            ratio = _ratio_in(r[combo_col])
        rows.append({
            "seg": r[0].strip(),
            "type": r[type_col].strip() if type_col is not None and type_col < len(r) else "",
            "item": r[item_col].strip() if item_col is not None and item_col < len(r) else "",
            "amount": amount, "ratio": ratio,
        })
    return rows, amt_col is not None


def parse_sales_total(grid):
    """매출실적 표의 당기(첫 숫자 열) 합계."""
    if not grid:
        return None
    nh = _header_rows(grid)
    body = grid[nh:]
    total_row = next((r for r in body if r and is_total(r[0])), None)
    if total_row is None:
        return None
    for v in total_row[1:]:
        n = to_num(v)
        if n is not None and abs(n) >= 1000:
            return n
    return None


def period_of(title):
    m = dart_web.PERIODIC_RE.search(title)
    kind, y, mm = m.group(1), int(m.group(2)), int(m.group(3))
    return y, (mm + 2) // 3, kind


def is_ship(seg):
    s = _nospace(seg)
    return s.startswith(("선박엔진", "선박용엔진"))


def build_record(rep, ext):
    y, q, kind = period_of(rep["title"])
    prod_rows, has_amt = parse_product(ext["product"]) if ext.get("product") else ([], False)
    sales_total = parse_sales_total(ext.get("sales"))
    segs = [r for r in prod_rows if not is_total(r["seg"])]
    tot_row = next((r for r in prod_rows if is_total(r["seg"])), None)

    rec = {"rcpNo": rep["rcpNo"], "title": rep["title"], "date": rep["date"], "year": y, "q": q,
           "segs": segs, "sales_total": sales_total, "note": ""}
    if has_amt and segs and all(r["amount"] is not None for r in segs):
        total = tot_row["amount"] if tot_row and tot_row["amount"] is not None else sum(r["amount"] for r in segs)
        ship = sum(r["amount"] for r in segs if is_ship(r["seg"]))
        rec.update(ship=ship, total=total, other=total - ship, estimated=False)
        diff = total - sum(r["amount"] for r in segs)
        if abs(diff) > 1:
            rec["note"] = f"부문 합 ≠ 합계 (차이 {diff:,.0f})"
    elif segs and sales_total is not None and any(r["ratio"] is not None for r in segs):
        ship_ratio = sum(r["ratio"] or 0 for r in segs if is_ship(r["seg"]))
        ship = round(sales_total * ship_ratio / 100)
        rec.update(ship=ship, total=sales_total, other=sales_total - ship, estimated=True,
                   note=f"부문 비율만 공시 → 총매출×선박엔진 {ship_ratio:g}% 추정")
        for r in segs:
            if r["ratio"] is not None:
                r["amount_est"] = round(sales_total * r["ratio"] / 100)
    else:
        rec.update(ship=None, total=sales_total, other=None, estimated=True, note="부문 표를 찾지 못함")
    return rec


# ── 수집 ───────────────────────────────────────────────────────────────
def load_store():
    if os.path.exists(STORE):
        with open(STORE, encoding="utf-8") as f:
            return json.load(f)
    return {"reports": [], "tables": {}}


def extract_tables(html):
    tbls = tables(html)
    return {"product": find_product_table(tbls), "sales": find_sales_table(tbls)}


def collect(store, offline=False):
    if not offline:
        cik = dart_web.corp_cik(CORP_NAME)
        print(f"{CORP_NAME} DART 고유번호 {cik}")
        reps = dart_web.list_periodic(cik, CORP_NAME, START_YEAR, int(time.strftime("%Y")))
        print(f"정기보고서 {len(reps)}건")
        store["reports"] = sorted(reps, key=lambda r: r["rcpNo"])
    for rep in store["reports"]:
        rcp = rep["rcpNo"]
        if rcp in store["tables"] and store["tables"][rcp].get("product"):
            continue
        raw = os.path.join(RAW_CACHE, rcp, "biz.html")
        if os.path.exists(raw):
            with open(raw, encoding="utf-8") as f:
                html = f.read()
        elif offline:
            continue
        else:
            print(f"  수집 {rcp} {rep['title']}", flush=True)
            html = dart_web.business_section(rcp)
            time.sleep(0.8)
        store["tables"][rcp] = extract_tables(html)
    with open(STORE, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=0)


# ── 시계열 ─────────────────────────────────────────────────────────────
def build_series(store):
    recs = {}
    for rep in store["reports"]:
        ext = store["tables"].get(rep["rcpNo"])
        if not ext:
            continue
        rec = build_record(rep, ext)
        key = (rec["year"], rec["q"])
        # 같은 기간이 둘이면(정정 등) 나중 접수본
        if key not in recs or rec["rcpNo"] > recs[key]["rcpNo"]:
            recs[key] = rec
    # 3개월 값 = 누적 − 직전 분기 누적 (같은 회계연도)
    for (y, q), rec in recs.items():
        prev = recs.get((y, q - 1)) if q > 1 else None
        for k in ("ship", "other", "total"):
            cur = rec.get(k)
            if q == 1:
                rec[k + "_q"] = cur
            elif prev is not None and cur is not None and prev.get(k) is not None:
                rec[k + "_q"] = cur - prev[k]
            else:
                rec[k + "_q"] = None
        rec["est_q"] = rec["estimated"] or (q > 1 and (prev is None or prev["estimated"]))
    return [recs[k] for k in sorted(recs)]


def qlabel(y, q):
    return f"{q}Q{str(y)[2:]}"


# ── 엑셀 ───────────────────────────────────────────────────────────────
def _style_header(ws, ncol, row=1):
    for c in range(1, ncol + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = Font(bold=True)
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def _put_num(cell, v, est=False, fmt=NUM_FMT):
    cell.value = v
    cell.number_format = fmt
    if est:
        cell.font = EST_FONT


def write_period_sheet(ws, series, mode):
    """mode: 'q'(3개월) / 'ytd'(누적) / 'y'(연간)"""
    head = ["기간", "선박엔진", "기타", "합계", "선박엔진 비중", "구분", "보고서", "접수일", "비고"]
    ws.append(head)
    for rec in series:
        if mode == "y" and rec["q"] != 4:
            continue
        suf = "_q" if mode == "q" else ""
        ship, other, total = rec.get("ship" + suf), rec.get("other" + suf), rec.get("total" + suf)
        est = rec["est_q"] if mode == "q" else rec["estimated"]
        label = str(rec["year"]) if mode == "y" else qlabel(rec["year"], rec["q"])
        ws.append([label])
        r = ws.max_row
        _put_num(ws.cell(r, 2), ship, est)
        _put_num(ws.cell(r, 3), other, est)
        _put_num(ws.cell(r, 4), total)
        if ship is not None and total:
            _put_num(ws.cell(r, 5), ship / total, est, "0.0%")
        ws.cell(r, 6, "추정" if est else "공시")
        ws.cell(r, 7, rec["title"]).hyperlink = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rec['rcpNo']}"
        ws.cell(r, 8, rec["date"])
        note = rec["note"]
        if mode == "q" and rec["q"] > 1 and rec.get("ship_q") is None:
            note = (note + "; " if note else "") + "직전 분기 보고서 없음 → 3개월 값 계산 불가"
        ws.cell(r, 9, note)
    _style_header(ws, len(head))
    ws.freeze_panes = "B2"
    for i, w in enumerate([9, 13, 13, 13, 11, 7, 30, 11, 50], 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def write_pivot(ws, series):
    """행=부문, 열=분기(3개월)·연도 — FX 파일의 Pivot Wide 와 같은 모양."""
    qs = [r for r in series]
    ys = [r for r in series if r["q"] == 4]
    cols = [(qlabel(r["year"], r["q"]), r, "_q", r["est_q"]) for r in qs] + \
           [(str(r["year"]), r, "", r["estimated"]) for r in ys]
    ws.append([f"구분 ({UNIT})"] + [c[0] for c in cols])
    for name, key in (("선박엔진", "ship"), ("기타", "other"), ("합계", "total")):
        ws.append([name])
        r = ws.max_row
        for j, (_, rec, suf, est) in enumerate(cols, 2):
            _put_num(ws.cell(r, j), rec.get(key + suf), est and key != "total")
    ws.append(["선박엔진 비중"])
    r = ws.max_row
    for j, (_, rec, suf, est) in enumerate(cols, 2):
        s, t = rec.get("ship" + suf), rec.get("total" + suf)
        if s is not None and t:
            _put_num(ws.cell(r, j), s / t, est, "0.0%")
    _style_header(ws, len(cols) + 1)
    ws.freeze_panes = "B2"
    ws.column_dimensions["A"].width = 16
    for j in range(2, len(cols) + 2):
        ws.column_dimensions[get_column_letter(j)].width = 11
    for i in range(2, 6):
        ws.cell(i, 1).font = Font(bold=True)


def write_raw(ws, series):
    head = ["기간", "보고서", "접수일", "사업부문(원문)", "매출유형", "품목", "매출액(누적)", "비율(%)",
            "매출액 추정(총매출×비율)", "구분 매핑"]
    ws.append(head)
    for rec in series:
        for s in rec["segs"]:
            ws.append([qlabel(rec["year"], rec["q"]), rec["title"], rec["date"], s["seg"], s["type"], s["item"],
                       s["amount"] if not rec["estimated"] else None, s["ratio"], s.get("amount_est"),
                       "선박엔진" if is_ship(s["seg"]) else "기타"])
            ws.cell(ws.max_row, 2).hyperlink = f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rec['rcpNo']}"
            for c in (7, 9):
                ws.cell(ws.max_row, c).number_format = NUM_FMT
        ws.append([qlabel(rec["year"], rec["q"]), rec["title"], rec["date"], "(매출실적 표 당기 총매출)", "", "",
                   rec["sales_total"], None, None, "합계"])
        ws.cell(ws.max_row, 7).number_format = NUM_FMT
    _style_header(ws, len(head))
    ws.freeze_panes = "A2"
    for i, w in enumerate([8, 30, 11, 26, 11, 34, 14, 9, 14, 10], 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def write_readme(ws, series):
    lines = [
        "한화엔진(082740, 구 HSD엔진·두산엔진) 사업부문별 매출",
        f"단위: {UNIT}  |  출처: DART 분기·반기·사업보고서 'II. 사업의 내용 – 주요 제품(및 서비스)' 표",
        f"수록 기간: {qlabel(series[0]['year'], series[0]['q'])} ~ {qlabel(series[-1]['year'], series[-1]['q'])}"
        f"  |  생성: {time.strftime('%Y-%m-%d')}",
        "",
        "시트",
        " · 분기(3개월): 해당 분기 3개월 매출 = 누적 − 직전 분기 누적 (4Q = 연간 − 3Q 누적)",
        " · 분기(누적): 보고서에 적힌 그대로(연초부터 누적)",
        " · 연간: 사업보고서 기준",
        " · Pivot Wide: 행=부문, 열=분기(3개월)·연도",
        " · 원자료: 보고서별 사업부문 원문·매출유형·품목·금액·비율 (부문 명칭 변화 확인용)",
        "",
        "부문 정의",
        " · 선박엔진: 보고서의 '선박엔진/선박용 엔진' 부문 (2022~ SCR 포함, 2026~ 선박전동화 포함)",
        " · 기타: 합계 − 선박엔진. 시기별로 디젤발전(육상용 엔진), 부품(AM), 부동산 임대 등",
        "   (2019.1Q~2Q 는 부품사업이 별도 부문 → 기타에 포함)",
        "",
        "주의",
        " · 회색 기울임 = 추정치. 2010.2Q 이전 보고서는 부문 비율(%)만 공시해서",
        "   '매출실적' 표의 당기 총매출 × 선박엔진 비율로 계산했다(비율이 정수라 오차 ±0.5%p).",
        "   2005~2010년 분기·반기보고서의 비율은 직전 사업보고서 값을 그대로 옮긴 경우가 많아",
        "   이 구간 분기별 부문 구성은 참고용이다(합계는 실제 분기 매출).",
        " · 직전 분기 보고서가 없으면(예: 2007년 1분기·반기) 그 다음 분기의 3개월 값은 비워 둔다.",
        " · 2011년 K-IFRS 도입으로 2010년 이전과 이후는 회계기준이 다르다(보고서 표에 적힌 대로 사용).",
    ]
    for line in lines:
        ws.append([line])
    ws["A1"].font = Font(bold=True, size=13)
    ws.column_dimensions["A"].width = 110


def write_xlsx(series):
    wb = Workbook()
    ws = wb.active
    ws.title = "분기(3개월)"
    write_period_sheet(ws, series, "q")
    write_period_sheet(wb.create_sheet("분기(누적)"), series, "ytd")
    write_period_sheet(wb.create_sheet("연간"), series, "y")
    write_pivot(wb.create_sheet("Pivot Wide"), series)
    write_raw(wb.create_sheet("원자료"), series)
    write_readme(wb.create_sheet("설명"), series)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    wb.save(OUT)
    print(f"저장: {OUT}")


def main():
    offline = "--offline" in sys.argv
    store = load_store()
    collect(store, offline=offline)
    series = build_series(store)
    missing = [r["title"] for r in series if r.get("ship") is None]
    if missing:
        print("부문 매출을 못 읽은 보고서:", missing)
    for r in series:
        tag = "추정" if r["estimated"] else "    "
        ship_q = f"{r['ship_q']:>12,.0f}" if r.get("ship_q") is not None else " " * 12
        ship = f"{r['ship']:>12,.0f}" if r.get("ship") is not None else " " * 12
        print(f"{qlabel(r['year'], r['q'])} {tag} 선박엔진 누적 {ship}  3개월 {ship_q}  합계 {r['total'] or 0:>12,.0f}  {r['note']}")
    write_xlsx(series)


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""DART 웹사이트(dart.fss.or.kr) 클라이언트 — 오픈API 키 없이 공시 원문을 받는다.

- corp_cik(name)              : 회사명 → DART 고유번호
- list_periodic(cik, name)    : 사업·반기·분기보고서 목록 (최종본만)
- business_section(rcp_no)    : 'II. 사업의 내용'(하위 목차 포함) 원문 HTML
"""
import re
import time

import requests

BASE = "https://dart.fss.or.kr"
PERIODIC_RE = re.compile(r"(사업|반기|분기)보고서\s*\((\d{4})\.(\d{2})\)")
_NODE_RE = re.compile(r"node\d+\['(\w+)'\]\s*=\s*\"(.*?)\";")

_S = requests.Session()
_S.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Referer": BASE + "/dsab007/main.do",
    "X-Requested-With": "XMLHttpRequest",
})


def _req(method, path, **kw):
    last = None
    for attempt in range(1, 6):
        try:
            r = _S.request(method, BASE + path, timeout=40, **kw)
            r.encoding = "utf-8"
            # 잘못된 요청에도 200 + 오류 안내 페이지가 온다
            if r.status_code == 200 and "errorWrap" not in r.text[:6000]:
                return r.text
            last = f"HTTP {r.status_code} (오류 페이지)"
        except requests.RequestException as e:
            last = e
        print(f"  DART 재시도 {attempt}/5: {path} / {last}", flush=True)
        time.sleep(2 * attempt)
    raise RuntimeError(f"DART 요청 실패: {path} / {last}")


def corp_cik(name):
    t = _req("POST", "/corp/searchExistAll.ax", data={"textCrpNm": name}).strip().rstrip(",")
    if not t or t == "null":
        raise RuntimeError(f"DART 회사 조회 실패: {name}")
    return t.split(",")[0]


def list_periodic(cik, name, start_year, end_year):
    """정기보고서 목록. 상세검색은 긴 기간을 한 번에 주지 않아 1년 단위로 조회한다.

    공시유형 필터를 걸면 일부 연도(예: 2007 1·2분기) 보고서가 빠져서, 전체 공시를
    받고 보고서명으로 거른다.
    """
    _req("GET", "/dsab007/main.do")  # 세션 쿠키
    out, seen = [], set()
    for y in range(start_year, end_year + 1):
        page = 1
        while True:
            html = _req("POST", "/dsab007/detailSearch.ax", data={
                "currentPage": page, "maxResults": 100, "maxLinks": 10, "sort": "date", "series": "desc",
                "textCrpCik": cik, "textCrpNm": name, "option": "corp",
                "startDate": f"{y}0101", "endDate": f"{y}1231", "finalReport": "recent",
                "businessCode": "all", "corporationType": "all", "closingAccountsMonth": "all",
            })
            rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)
            n_links = 0
            for row in rows:
                m = re.search(r"rcpNo=(\d{14})", row)
                if not m:
                    continue
                n_links += 1
                cells = [re.sub(r"<[^>]+>|\s+", " ", c).strip()
                         for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
                title = next((c for c in cells if PERIODIC_RE.search(c)), None)
                if not title or m.group(1) in seen:
                    continue
                seen.add(m.group(1))
                date = next((c for c in cells if re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", c)), "")
                out.append({"rcpNo": m.group(1), "title": title, "date": date})
            if n_links < 100:
                break
            page += 1
            time.sleep(0.3)
        time.sleep(0.3)
    return out


def _toc(rcp_no):
    html = _req("GET", f"/dsaf001/main.do?rcpNo={rcp_no}")
    seq, cur = [], None
    for k, v in _NODE_RE.findall(html):
        if k == "text":
            cur = {"text": v}
            seq.append(cur)
        elif cur is not None:
            cur[k] = v
    return seq


def business_section(rcp_no):
    """'II. 사업의 내용'과 그 하위 목차 원문을 이어 붙여 반환."""
    parts, on = [], False
    for n in _toc(rcp_no):
        t = re.sub(r"\s+", "", n["text"])
        if not on and (re.match(r"^(II|Ⅱ)\.", t) or "사업의내용" in t):
            on = True
        elif on and re.match(r"^(III|Ⅲ|IV|Ⅳ|V|Ⅴ)\.", t):
            break
        if on and n.get("dcmNo"):
            q = {k: n.get(k, "") for k in ("rcpNo", "dcmNo", "eleId", "offset", "length", "dtd")}
            parts.append(_req("GET", "/report/viewer.do", params=q))
            time.sleep(0.4)
    return "\n".join(parts)

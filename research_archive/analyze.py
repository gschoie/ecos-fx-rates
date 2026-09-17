# -*- coding: utf-8 -*-
"""PDF 메타데이터 추출.

1) PyMuPDF로 페이지별 텍스트 추출 + 1페이지 이미지 렌더링
2) Claude API(vision + text)로 발간일/산업/자료유형/기업(페이지범위·투자의견·TP)/
   제목/핵심키워드를 JSON으로 추출
3) API 키가 없으면 휴리스틱 폴백 (텔레그램 게시물 정보 기반)
"""
from __future__ import annotations

import base64
import datetime as dt
import json
import re
from dataclasses import dataclass, field

import pymupdf as fitz

from . import config


@dataclass
class CompanyRecord:
    name: str
    page_start: int | None = None
    page_end: int | None = None
    rating: str = ""            # 투자의견 (예: Buy, Hold)
    target_price: str = ""      # 현재 TP
    prev_target_price: str = "" # 보고서에 명시된 이전 TP


@dataclass
class ReportMeta:
    published_date: str = ""    # YYYY-MM-DD
    industry: str = ""
    doc_type: str = ""          # "산업" | "기업"
    title: str = ""
    keywords: list[str] = field(default_factory=list)
    companies: list[CompanyRecord] = field(default_factory=list)
    num_pages: int = 0
    analysis_source: str = ""   # "ai" | "heuristic"


# ── PDF 파싱 ─────────────────────────────────────────────────────────

def extract_pdf(data: bytes, max_pages_text: int = 80,
                per_page_chars: int = 500) -> tuple[list[str], bytes, int]:
    """(페이지별 텍스트 목록, 1페이지 PNG, 총 페이지수)"""
    doc = fitz.open(stream=data, filetype="pdf")
    n = doc.page_count
    pages: list[str] = []
    for i in range(min(n, max_pages_text)):
        txt = doc[i].get_text("text") or ""
        txt = re.sub(r"\s+", " ", txt).strip()
        pages.append(txt[:per_page_chars] if i > 0 else txt[:2000])
    pix = doc[0].get_pixmap(dpi=140)
    png = pix.tobytes("png")
    doc.close()
    return pages, png, n


# ── Claude 분석 ──────────────────────────────────────────────────────

_PROMPT = """당신은 증권사 리서치 보고서 아카이빙 시스템의 메타데이터 추출기입니다.
첨부된 것은 (1) 보고서 PDF 1페이지 이미지, (2) 페이지별 추출 텍스트([PAGE n] 마커),
(3) 이 보고서를 공유한 텔레그램 게시물 원문입니다.

다음 JSON만 출력하세요 (설명·마크다운 금지):
{
  "published_date": "YYYY-MM-DD",          // 보고서 발간일. 1페이지 이미지에서 우선 확인
  "industry": "...",                        // 다음 중 하나: %INDUSTRIES% (없으면 "기타")
  "doc_type": "산업" 또는 "기업",           // 특정 1개 기업 분석이면 "기업", 산업/복수기업 인뎁스면 "산업"
  "title": "...",                           // 보고서 제목 (부제 제외 가능, 간결하게)
  "keywords": ["...", "..."],               // 투자포인트 중심 핵심 키워드 2~4개. 각 키워드는 짧게(한글/영문/숫자). 예: "LNGC", "선가", "USV", "MRO", "관세"
  "companies": [                            // 다루는 기업들. 산업 전반 자료면 섹션별 기업. 기업 보고서면 그 기업 1개
    {
      "name": "한화오션",
      "page_start": 18, "page_end": 25,     // 해당 기업 섹션 페이지 범위 (모르면 null)
      "rating": "Buy",                      // 투자의견 (없으면 "")
      "target_price": "120,000원",           // 현재 목표주가 (없으면 "")
      "prev_target_price": "100,000원"       // 보고서에 명시된 직전 목표주가 (없으면 "")
    }
  ]
}
규칙:
- 발간일은 반드시 이미지와 텍스트에서 근거를 찾아 기입. 못 찾으면 텔레그램 게시일 사용: %TG_DATE%
- 산업 전체를 다루는 인뎁스에서 개별 기업 섹션이 있으면 companies에 모두 나열하고 page 범위를 추정.
- keywords는 단순 빈출 단어가 아니라 "이 보고서를 나중에 검색할 때 쓸" 투자포인트 용어로.
- target_price는 원 단위 표기 그대로.
"""


def _call_claude(pages: list[str], png: bytes, tg_text: str,
                 tg_date: str) -> dict:
    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    page_text = "\n".join(f"[PAGE {i+1}] {t}" for i, t in enumerate(pages) if t)
    if len(page_text) > 60000:
        page_text = page_text[:60000]

    prompt = _PROMPT.replace("%INDUSTRIES%", ", ".join(config.INDUSTRIES)) \
                    .replace("%TG_DATE%", tg_date or "미상")

    msg = client.messages.create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {
                    "type": "base64", "media_type": "image/png",
                    "data": base64.b64encode(png).decode()}},
                {"type": "text", "text":
                    f"{prompt}\n\n=== 텔레그램 게시물 ===\n{tg_text[:2000]}"
                    f"\n\n=== PDF 텍스트 ===\n{page_text}"},
            ],
        }],
    )
    raw = "".join(b.text for b in msg.content if b.type == "text")
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError(f"JSON 응답 파싱 실패: {raw[:200]}")
    return json.loads(m.group(0))


# ── 휴리스틱 폴백 ────────────────────────────────────────────────────

_DATE_PATTERNS = [
    r"(20\d{2})[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})",
]


def _guess_date(pages: list[str], tg_date: str) -> str:
    head = " ".join(pages[:2])
    for pat in _DATE_PATTERNS:
        m = re.search(pat, head)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            try:
                return dt.date(y, mo, d).isoformat()
            except ValueError:
                pass
    return (tg_date or "")[:10]


def _guess_industry(companies: list[str], text: str) -> str:
    for c in companies:
        if c in config.COMPANY_INDUSTRY_MAP:
            return config.COMPANY_INDUSTRY_MAP[c]
    scores = {ind: 0 for ind in config.INDUSTRIES}
    hints = {"조선": ["조선", "선박", "선가", "LNGC", "수주잔고", "신조선"],
             "방산": ["방산", "미사일", "K9", "무기", "국방", "폴란드"],
             "기계": ["기계", "건설기계", "굴착기", "전력기기", "변압기", "농기계"]}
    for ind, words in hints.items():
        for w in words:
            scores[ind] += text.count(w)
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else config.FALLBACK_INDUSTRY


def analyze(pdf_bytes: bytes, tg_text: str, tg_date: str,
            tg_hashtags: list[str], tg_title: str) -> ReportMeta:
    pages, png, n = extract_pdf(pdf_bytes)
    meta = ReportMeta(num_pages=n)

    if config.ANTHROPIC_API_KEY:
        try:
            d = _call_claude(pages, png, tg_text, (tg_date or "")[:10])
            meta.published_date = (d.get("published_date") or "")[:10]
            meta.industry = d.get("industry") or config.FALLBACK_INDUSTRY
            meta.doc_type = d.get("doc_type") or ""
            meta.title = (d.get("title") or tg_title).strip()
            meta.keywords = [str(k).strip() for k in d.get("keywords", [])
                             if str(k).strip()][:config.MAX_KEYWORDS]
            for c in d.get("companies", []):
                if not c.get("name"):
                    continue
                meta.companies.append(CompanyRecord(
                    name=str(c["name"]).strip(),
                    page_start=c.get("page_start"),
                    page_end=c.get("page_end"),
                    rating=str(c.get("rating") or ""),
                    target_price=str(c.get("target_price") or ""),
                    prev_target_price=str(c.get("prev_target_price") or ""),
                ))
            meta.analysis_source = "ai"
            _sanity(meta, tg_date, tg_title, tg_hashtags, pages)
            return meta
        except Exception as e:  # AI 실패 시 폴백
            print(f"  [warn] AI 분석 실패, 휴리스틱 폴백: {e}")

    # 휴리스틱
    companies = [h for h in tg_hashtags if h in config.COMPANY_INDUSTRY_MAP]
    meta.published_date = _guess_date(pages, tg_date)
    meta.industry = _guess_industry(companies, " ".join(pages[:10]))
    meta.doc_type = "기업" if len(companies) == 1 else "산업"
    meta.title = tg_title or (pages[0][:60] if pages else "제목미상")
    meta.keywords = []
    meta.companies = [CompanyRecord(name=c) for c in companies]
    meta.analysis_source = "heuristic"
    return meta


def _sanity(meta: ReportMeta, tg_date: str, tg_title: str,
            tg_hashtags: list[str], pages: list[str]) -> None:
    if not re.match(r"^20\d{2}-\d{2}-\d{2}$", meta.published_date or ""):
        meta.published_date = _guess_date(pages, tg_date)
    if meta.industry not in config.INDUSTRIES:
        meta.industry = config.FALLBACK_INDUSTRY if meta.industry in ("", None) \
            else meta.industry  # AI가 새 산업명을 준 경우 그대로 폴더 생성 허용
    if not meta.title:
        meta.title = tg_title or "제목미상"
    if not meta.companies and len(tg_hashtags) == 1:
        meta.companies = [CompanyRecord(name=tg_hashtags[0])]

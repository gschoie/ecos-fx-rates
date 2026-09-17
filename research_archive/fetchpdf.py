# -*- coding: utf-8 -*-
"""보고서 링크 → PDF 바이트 확보.

링크가 PDF 직링크일 수도, 뷰어/랜딩 HTML일 수도 있어 다음 순서로 시도:
1) 링크 자체가 PDF(Content-Type 또는 %PDF 매직)
2) HTML이면 내부에서 .pdf 링크 / iframe / meta refresh 탐색 후 재시도
"""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from . import config


class PdfFetchError(Exception):
    pass


def _get(session: requests.Session, url: str) -> requests.Response:
    r = session.get(url, timeout=config.HTTP_TIMEOUT, allow_redirects=True,
                    stream=True)
    r.raise_for_status()
    return r


def _read_limited(r: requests.Response) -> bytes:
    limit = config.MAX_PDF_MB * 1024 * 1024
    buf = bytearray()
    for chunk in r.iter_content(chunk_size=65536):
        buf.extend(chunk)
        if len(buf) > limit:
            raise PdfFetchError(f"파일이 {config.MAX_PDF_MB}MB 초과: {r.url}")
    return bytes(buf)


def _is_pdf(data: bytes) -> bool:
    return data[:1024].lstrip().startswith(b"%PDF")


def _find_pdf_candidates(html: str, base_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    cands: list[str] = []

    def add(u: str | None):
        if not u:
            return
        full = urljoin(base_url, u.strip())
        if full not in cands:
            cands.append(full)

    # a href / iframe / embed / object 에서 .pdf 우선
    for tag, attr in (("a", "href"), ("iframe", "src"),
                      ("embed", "src"), ("object", "data")):
        for el in soup.find_all(tag):
            u = el.get(attr, "")
            if ".pdf" in u.lower():
                add(u)
    # meta refresh
    meta = soup.find("meta", attrs={"http-equiv": re.compile("refresh", re.I)})
    if meta and "url=" in meta.get("content", "").lower():
        add(re.split(r"url=", meta["content"], flags=re.I)[-1])
    # JS 내 pdf URL
    for m in re.finditer(r"""["']([^"']+\.pdf[^"']*)["']""", html, re.I):
        add(m.group(1))
    # 최후: .pdf 없는 iframe/a 도 후보로 (뷰어 페이지가 한 번 더 감싼 경우)
    for tag, attr in (("iframe", "src"),):
        for el in soup.find_all(tag):
            add(el.get(attr, ""))
    return cands[:8]


def fetch_pdf(url: str) -> tuple[bytes, str]:
    """PDF 바이트와 최종 URL 반환. 실패 시 PdfFetchError."""
    s = requests.Session()
    s.headers.update({"User-Agent": config.USER_AGENT, "Referer": url})

    r = _get(s, url)
    data = _read_limited(r)
    if _is_pdf(data):
        return data, r.url

    # HTML 랜딩 → PDF 링크 탐색 (2단계까지)
    html = data.decode("utf-8", errors="replace")
    for cand in _find_pdf_candidates(html, r.url):
        try:
            r2 = _get(s, cand)
            d2 = _read_limited(r2)
        except Exception:
            continue
        if _is_pdf(d2):
            return d2, r2.url
        # 한 단계 더 (뷰어 안의 뷰어)
        for cand2 in _find_pdf_candidates(d2.decode("utf-8", "replace"), r2.url)[:4]:
            try:
                r3 = _get(s, cand2)
                d3 = _read_limited(r3)
                if _is_pdf(d3):
                    return d3, r3.url
            except Exception:
                continue
    raise PdfFetchError(f"PDF를 찾지 못했습니다: {url}")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

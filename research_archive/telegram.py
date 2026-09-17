# -*- coding: utf-8 -*-
"""t.me/s/<채널> 공개 웹 프리뷰 스크레이핑.

공개 채널은 로그인/API 키 없이 https://t.me/s/HI_GS 에서 최근 게시물을
HTML로 제공하며 ?before=<message_id> 로 과거 페이지를 순차 조회할 수 있다.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

from . import config


@dataclass
class Post:
    msg_id: int
    text: str = ""
    links: list[str] = field(default_factory=list)
    hashtags: list[str] = field(default_factory=list)
    date_iso: str = ""          # 게시 시각 (ISO8601)
    permalink: str = ""         # https://t.me/HI_GS/1234

    @property
    def is_report(self) -> bool:
        return config.COMPLIANCE_PHRASE in self.text.replace(" ", "") or \
               config.COMPLIANCE_PHRASE in self.text

    @property
    def report_url(self) -> str | None:
        """보고서 본문 링크: 텍스트 내 첫 외부 링크(☞ 뒤 링크 우선)."""
        for ln in self.links:
            if not ln.lower().startswith("http"):
                continue
            if "t.me/" in ln:
                continue
            return ln
        return None

    @property
    def title_guess(self) -> str:
        m = re.search(r"[「『]([^」』]+)[」』]", self.text)
        if m:
            return m.group(1).strip()
        first = self.text.strip().splitlines()[0] if self.text.strip() else ""
        return re.sub(r"[🔥✅☞#]", "", first).strip()


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": config.USER_AGENT,
                      "Accept-Language": "ko,en;q=0.8"})
    return s


def parse_channel_html(html: str) -> list[Post]:
    """t.me/s 페이지 HTML → Post 목록 (오름차순 msg_id)."""
    soup = BeautifulSoup(html, "html.parser")
    posts: list[Post] = []
    for msg in soup.select("div.tgme_widget_message[data-post]"):
        data_post = msg.get("data-post", "")
        m = re.match(r".+/(\d+)$", data_post)
        if not m:
            continue
        msg_id = int(m.group(1))

        text_div = msg.select_one(".tgme_widget_message_text")
        text, links = "", []
        if text_div is not None:
            for br in text_div.find_all("br"):
                br.replace_with("\n")
            text = text_div.get_text()
            for a in text_div.find_all("a", href=True):
                href = a["href"]
                if href.startswith("?q="):        # 해시태그 검색 링크
                    continue
                links.append(href)

        hashtags = re.findall(r"#([\w가-힣A-Za-z0-9._·]+)", text)

        t = msg.select_one("time[datetime]")
        date_iso = t["datetime"] if t is not None else ""

        posts.append(Post(
            msg_id=msg_id, text=text, links=links, hashtags=hashtags,
            date_iso=date_iso, permalink=f"https://t.me/{data_post}",
        ))
    posts.sort(key=lambda p: p.msg_id)
    return posts


def fetch_page(before: int | None = None, session: requests.Session | None = None) -> list[Post]:
    """한 페이지(약 20개) 조회. before가 있으면 그 이전 게시물."""
    s = session or _session()
    params = {"before": before} if before else None
    r = s.get(config.TG_PREVIEW_URL, params=params, timeout=config.HTTP_TIMEOUT)
    r.raise_for_status()
    if "tgme_widget_message" not in r.text:
        # 채널 프리뷰 비활성/비공개 등
        if "tgme_page" in r.text and "Preview channel" not in r.text:
            raise RuntimeError(
                f"채널 {config.CHANNEL} 의 웹 프리뷰를 읽을 수 없습니다. "
                "채널이 비공개이거나 프리뷰가 제한된 경우 Telethon 방식이 필요합니다.")
        return []
    return parse_channel_html(r.text)


def iter_history(start_before: int | None = None, max_pages: int = 10000,
                 delay: float = 1.0):
    """과거 방향으로 페이지 단위 순회 (backfill용). 페이지별 Post 리스트 yield."""
    s = _session()
    before = start_before
    for _ in range(max_pages):
        posts = fetch_page(before=before, session=s)
        if not posts:
            return
        yield posts
        oldest = posts[0].msg_id
        if before is not None and oldest >= before:
            return  # 더 이상 진행 없음
        before = oldest
        if before <= 1:
            return
        time.sleep(delay)


def fetch_new(since_id: int, max_pages: int = 50, delay: float = 1.0) -> list[Post]:
    """since_id 초과의 새 게시물 전부 (오름차순)."""
    s = _session()
    collected: dict[int, Post] = {}
    before: int | None = None
    for _ in range(max_pages):
        posts = fetch_page(before=before, session=s)
        if not posts:
            break
        for p in posts:
            if p.msg_id > since_id:
                collected[p.msg_id] = p
        oldest = posts[0].msg_id
        if oldest <= since_id + 1:
            break
        before = oldest
        time.sleep(delay)
    return [collected[k] for k in sorted(collected)]

# -*- coding: utf-8 -*-
"""수집 파이프라인 오케스트레이션.

Telegram 게시물 → 보고서 판별 → PDF 다운로드 → 분석 → 파일명 →
업로드(Drive 또는 로컬) → Master Index 기록 → 상태 저장.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import os
import re

from . import config
from .analyze import ReportMeta, analyze
from .fetchpdf import PdfFetchError, fetch_pdf, sha256
from .telegram import Post


# ── 파일명 ───────────────────────────────────────────────────────────

def _clean(s: str) -> str:
    s = re.sub(r'[\\/:*?"<>|\n\r\t]', " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def build_filename(meta: ReportMeta) -> str:
    date = (meta.published_date or "00000000").replace("-", "")
    parts = [date]
    if meta.doc_type == "기업" and meta.companies:
        parts.append(f"[{_clean(meta.companies[0].name)}]")
    title = _clean(meta.title) or "제목미상"
    parts.append(title)
    if meta.keywords:
        kw = "_".join(_clean(k) for k in meta.keywords[:config.MAX_KEYWORDS])
        parts.append(f"[{kw}]")
    base = "_".join(parts)
    if len(base) > config.MAX_FILENAME_LEN:
        # 제목부터 줄인다
        overflow = len(base) - config.MAX_FILENAME_LEN
        title_short = title[:max(10, len(title) - overflow)].rstrip() + "…"
        parts[parts.index(title)] = title_short
        base = "_".join(parts)[:config.MAX_FILENAME_LEN]
    return base + ".pdf"


# ── 저장소 추상화 ────────────────────────────────────────────────────

class LocalStore:
    """--dry-run/테스트용: Drive 대신 로컬 폴더 + CSV 인덱스."""

    def __init__(self, out_dir: str = "archive_out"):
        self.out = out_dir
        os.makedirs(self.out, exist_ok=True)
        self.csv_path = os.path.join(self.out, "master_index.csv")
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="", encoding="utf-8-sig") as f:
                csv.writer(f).writerow(config.INDEX_COLUMNS)
        self._state_path = os.path.join(self.out, "_archive_state.json")

    def industry_year_folder(self, industry: str, year: str) -> str:
        p = os.path.join(self.out, _clean(industry) or "기타", year)
        os.makedirs(p, exist_ok=True)
        return p

    def upload_pdf(self, folder: str, filename: str, data: bytes) -> str:
        path = os.path.join(folder, filename)
        if os.path.exists(path):
            stem, ext = os.path.splitext(path)
            path = f"{stem} (2){ext}"
        with open(path, "wb") as f:
            f.write(data)
        return path

    def ensure_index_sheet(self) -> str:
        return self.csv_path

    def append_rows(self, _sheet_id: str, rows: list[list[str]]) -> None:
        with open(self.csv_path, "a", newline="", encoding="utf-8-sig") as f:
            csv.writer(f).writerows(rows)

    def read_all_rows(self, _sheet_id: str) -> list[list[str]]:
        with open(self.csv_path, encoding="utf-8-sig") as f:
            rows = list(csv.reader(f))
        return rows[1:]

    def load_state(self) -> dict:
        if os.path.exists(self._state_path):
            with open(self._state_path, encoding="utf-8") as f:
                return json.load(f)
        return {}

    def save_state(self, state: dict) -> None:
        with open(self._state_path, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=1)


# ── TP 이력 조회 ─────────────────────────────────────────────────────

_COL = {name: i for i, name in enumerate(config.INDEX_COLUMNS)}


def _num(tp: str) -> float | None:
    m = re.search(r"[\d,]+(?:\.\d+)?", tp or "")
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


class TpHistory:
    """Master Index 기존 행에서 기업별 최신 투자의견/TP를 기억."""

    def __init__(self, rows: list[list[str]]):
        self.latest: dict[str, dict] = {}
        entries = []
        for r in rows:
            r = r + [""] * (len(config.INDEX_COLUMNS) - len(r))
            comp = r[_COL["기업"]].strip()
            if not comp:
                continue
            entries.append((r[_COL["발간일"]], comp,
                            r[_COL["투자의견"]], r[_COL["Target Price"]]))
        for date, comp, rating, tp in sorted(entries):
            if rating or tp:
                self.latest[comp] = {"date": date, "rating": rating, "tp": tp}

    def diff(self, comp: str, rating: str, tp: str) -> tuple[str, str, str]:
        """(이전TP, TP변경여부, 투자의견변경여부). 이후 최신값 갱신."""
        prev = self.latest.get(comp)
        prev_tp, tp_chg, rating_chg = "", "", ""
        if prev:
            prev_tp = prev["tp"]
            a, b = _num(prev["tp"]), _num(tp)
            if a is not None and b is not None:
                if b > a:
                    tp_chg = f"상향 (+{(b - a) / a * 100:.1f}%)"
                elif b < a:
                    tp_chg = f"하향 ({(b - a) / a * 100:.1f}%)"
                else:
                    tp_chg = "유지"
            if prev["rating"] and rating:
                rating_chg = "유지" if prev["rating"].strip().lower() == \
                    rating.strip().lower() else f"변경 ({prev['rating']}→{rating})"
        if rating or tp:
            self.latest[comp] = {"date": "", "rating": rating, "tp": tp}
        return prev_tp, tp_chg, rating_chg


# ── 레코드 생성 ──────────────────────────────────────────────────────

def build_rows(report_id: str, meta: ReportMeta, post: Post,
               pdf_url: str, drive_link: str, hist: TpHistory) -> list[list[str]]:
    today = dt.date.today().isoformat()
    kw = ", ".join(meta.keywords)

    def row(doc_type, comp, rating="", tp="", prev_tp_report="",
            page_range=""):
        prev_tp, tp_chg, rating_chg = ("", "", "")
        if comp:
            prev_tp, tp_chg, rating_chg = hist.diff(comp, rating, tp)
            if not prev_tp and prev_tp_report:
                prev_tp = prev_tp_report
                a, b = _num(prev_tp_report), _num(tp)
                if a and b and not tp_chg:
                    tp_chg = ("상향 (+%.1f%%)" % ((b - a) / a * 100)) if b > a \
                        else ("하향 (%.1f%%)" % ((b - a) / a * 100)) if b < a else "유지"
        return [report_id, meta.published_date, meta.industry, doc_type,
                comp, meta.title, kw, rating, tp, prev_tp, tp_chg, rating_chg,
                page_range, post.permalink, pdf_url, drive_link, today, "완료"]

    rows = []
    if meta.doc_type == "기업" and len(meta.companies) == 1:
        c = meta.companies[0]
        rows.append(row("기업", c.name, c.rating, c.target_price,
                        c.prev_target_price))
    else:
        rows.append(row("산업", ""))          # 산업 전체 레코드
        for c in meta.companies:
            pr = ""
            if c.page_start:
                pr = f"p.{c.page_start}" + (f"~{c.page_end}" if c.page_end else "")
            rows.append(row("산업자료 내 기업섹션", c.name, c.rating,
                            c.target_price, c.prev_target_price, pr))
    return rows


# ── 메인 처리 ────────────────────────────────────────────────────────

class Pipeline:
    def __init__(self, store, verbose: bool = True):
        self.store = store
        self.state = store.load_state()
        self.state.setdefault("processed_msg_ids", [])
        self.state.setdefault("processed_urls", [])
        self.state.setdefault("pdf_hashes", [])
        self.sheet_id = store.ensure_index_sheet()
        self.hist = TpHistory(store.read_all_rows(self.sheet_id))
        self.verbose = verbose

    def _log(self, msg: str):
        if self.verbose:
            print(msg, flush=True)

    def seen(self, post: Post) -> bool:
        if post.msg_id in self.state["processed_msg_ids"]:
            return True
        url = post.report_url
        return bool(url and url in self.state["processed_urls"])

    def mark(self, post: Post, url: str | None = None, h: str | None = None):
        if post.msg_id not in self.state["processed_msg_ids"]:
            self.state["processed_msg_ids"].append(post.msg_id)
        if url and url not in self.state["processed_urls"]:
            self.state["processed_urls"].append(url)
        if h and h not in self.state["pdf_hashes"]:
            self.state["pdf_hashes"].append(h)

    def process_post(self, post: Post) -> bool:
        """보고서 게시물 1건 처리. 실제 업로드가 일어나면 True."""
        if self.seen(post):
            return False
        if not post.is_report:
            self.mark(post)
            return False
        url = post.report_url
        if not url:
            self._log(f"  [skip] 보고서 문구는 있으나 링크 없음: {post.permalink}")
            self.mark(post)
            return False

        self._log(f"▶ {post.permalink} 처리 중… ({post.title_guess[:40]})")
        try:
            pdf, final_url = fetch_pdf(url)
        except (PdfFetchError, Exception) as e:
            self._log(f"  [error] PDF 다운로드 실패: {e}")
            self._append_error(post, url, f"PDF 다운로드 실패: {e}")
            self.mark(post, url)
            return False

        h = sha256(pdf)
        if h in self.state["pdf_hashes"]:
            self._log("  [skip] 동일 PDF(hash) 이미 저장됨")
            self.mark(post, url, h)
            return False

        meta = analyze(pdf, post.text, post.date_iso, post.hashtags,
                       post.title_guess)
        year = (meta.published_date or "0000")[:4]
        if year == "0000":
            year = (post.date_iso or dt.date.today().isoformat())[:4]
            meta.published_date = meta.published_date or (post.date_iso or "")[:10]

        filename = build_filename(meta)
        folder = self.store.industry_year_folder(meta.industry, year)
        link = self.store.upload_pdf(folder, filename, pdf)
        self._log(f"  ✔ 저장: {meta.industry}/{year}/{filename} "
                  f"[{meta.analysis_source}]")

        report_id = f"R{(meta.published_date or year).replace('-', '')}_M{post.msg_id}"
        rows = build_rows(report_id, meta, post, final_url, link, self.hist)
        self.store.append_rows(self.sheet_id, rows)
        self.mark(post, url, h)
        return True

    def _append_error(self, post: Post, url: str, status: str):
        r = [""] * len(config.INDEX_COLUMNS)
        r[_COL["Report ID"]] = f"ERR_M{post.msg_id}"
        r[_COL["보고서 제목"]] = post.title_guess
        r[_COL["Telegram 원문 링크"]] = post.permalink
        r[_COL["원본 보고서 URL"]] = url
        r[_COL["수집일"]] = dt.date.today().isoformat()
        r[_COL["처리 상태"]] = status
        self.store.append_rows(self.sheet_id, [r])

    def save(self):
        self.store.save_state(self.state)

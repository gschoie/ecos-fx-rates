# -*- coding: utf-8 -*-
"""research_archive 단위/통합 테스트 (네트워크·Google API 불필요)."""
import os
import sys

import pymupdf as fitz
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from research_archive import config, pipeline as pl
from research_archive.analyze import CompanyRecord, ReportMeta
from research_archive.telegram import parse_channel_html

FIXTURE = os.path.join(os.path.dirname(__file__), "fixture_channel.html")


@pytest.fixture
def posts():
    with open(FIXTURE, encoding="utf-8") as f:
        return parse_channel_html(f.read())


def test_parse_channel(posts):
    assert [p.msg_id for p in posts] == [1201, 1202, 1203]
    daily, corp, indepth = posts
    assert not daily.is_report
    assert corp.is_report and indepth.is_report
    assert corp.report_url == "https://example-sec.com/research/report_view?id=98765"
    assert corp.title_guess == "미 해군 MRO의 최대 수혜주"
    assert "한화오션" in corp.hashtags
    assert corp.date_iso.startswith("2026-09-16")
    assert corp.permalink == "https://t.me/HI_GS/1202"
    # 데일리 뉴스의 기사 링크는 report_url이지만 is_report가 아니므로 무시됨
    assert daily.report_url is not None and not daily.is_report


def test_filename_company():
    meta = ReportMeta(published_date="2026-09-16", industry="조선",
                      doc_type="기업", title="미 해군 MRO의 최대 수혜주",
                      keywords=["USV", "MRO", "미해군"],
                      companies=[CompanyRecord(name="한화오션")])
    assert pl.build_filename(meta) == \
        "20260916_[한화오션]_미 해군 MRO의 최대 수혜주_[USV_MRO_미해군].pdf"


def test_filename_industry_and_length():
    meta = ReportMeta(published_date="2026-01-02", industry="조선",
                      doc_type="산업", title="아주 긴 제목 " * 30,
                      keywords=["LNGC", "선가"])
    name = pl.build_filename(meta)
    assert name.startswith("20260102_")
    assert "[LNGC_선가]" in name
    assert len(name) <= config.MAX_FILENAME_LEN + 4
    assert "[한화오션]" not in name


def test_tp_history():
    rows = [["R1", "2026-01-05", "조선", "기업", "한화오션", "t", "", "Buy",
             "100,000원", "", "", "", "", "", "", "", "2026-01-05", "완료"]]
    hist = pl.TpHistory(rows)
    prev_tp, tp_chg, rating_chg = hist.diff("한화오션", "Buy", "120,000원")
    assert prev_tp == "100,000원"
    assert tp_chg == "상향 (+20.0%)"
    assert rating_chg == "유지"
    # 처음 보는 기업
    assert hist.diff("삼성중공업", "Buy", "20,000원") == ("", "", "")


def _fake_pdf(text: str) -> bytes:
    doc = fitz.open()
    for chunk in text.split("|"):
        page = doc.new_page()
        page.insert_text((72, 100), chunk, fontsize=12)
    return doc.tobytes()


def test_pipeline_end_to_end(tmp_path, monkeypatch, posts):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")  # 휴리스틱 경로
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    pdf = _fake_pdf("Hanwha Ocean 2026. 9. 16 LNGC report|body page 2")
    monkeypatch.setattr(pl, "fetch_pdf",
                        lambda url: (pdf, url + "/final.pdf"))

    store = pl.LocalStore(out_dir=str(tmp_path / "out"))
    pipe = pl.Pipeline(store, verbose=False)

    corp = posts[1]
    assert pipe.process_post(corp) is True
    assert pipe.process_post(corp) is False          # 중복(msg id)
    pipe.save()

    # 산업/연도 폴더에 파일 존재
    files = []
    for root, _, fs in os.walk(tmp_path / "out"):
        files += [os.path.join(root, f) for f in fs if f.endswith(".pdf")]
    assert len(files) == 1
    assert os.sep + "조선" + os.sep + "2026" + os.sep in files[0]
    assert "[한화오션]" in os.path.basename(files[0])

    rows = store.read_all_rows("")
    assert len(rows) == 1
    r = rows[0] + [""] * 18
    col = {n: i for i, n in enumerate(config.INDEX_COLUMNS)}
    assert r[col["Report ID"]] == "R20260916_M1202"
    assert r[col["기업"]] == "한화오션"
    assert r[col["자료유형"]] == "기업"
    assert r[col["Telegram 원문 링크"]] == "https://t.me/HI_GS/1202"
    assert r[col["처리 상태"]] == "완료"

    # 동일 PDF 다른 게시물 → hash 중복 차단
    indepth = posts[2]
    assert pipe.process_post(indepth) is False

    # 재기동 시 상태 복원
    pipe2 = pl.Pipeline(pl.LocalStore(out_dir=str(tmp_path / "out")),
                        verbose=False)
    assert pipe2.seen(corp)


def test_industry_rows(posts):
    meta = ReportMeta(
        published_date="2026-09-17", industry="조선", doc_type="산업",
        title="슈퍼사이클의 재해석", keywords=["LNGC", "USV"],
        companies=[CompanyRecord("한화오션", 18, 25, "Buy", "120,000원"),
                   CompanyRecord("HD현대중공업", 26, 31, "Buy", "400,000원")])
    hist = pl.TpHistory([])
    rows = pl.build_rows("R20260917_M1203", meta, posts[2],
                         "https://x/y.pdf", "drive://z", hist)
    assert len(rows) == 3
    col = {n: i for i, n in enumerate(config.INDEX_COLUMNS)}
    assert rows[0][col["자료유형"]] == "산업" and rows[0][col["기업"]] == ""
    assert rows[1][col["자료유형"]] == "산업자료 내 기업섹션"
    assert rows[1][col["해당 기업 Page Range"]] == "p.18~25"
    assert all(r[col["Report ID"]] == "R20260917_M1203" for r in rows)

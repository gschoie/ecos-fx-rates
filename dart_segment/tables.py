# -*- coding: utf-8 -*-
"""DART 원문 HTML → 표(행렬) 추출. rowspan/colspan 을 펼친다. 표 직전 텍스트도 함께 보관."""
import html as _html
import re
from html.parser import HTMLParser


class _P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.stack, self.text_buf = [], [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            self.stack.append({"rows": [], "row": None, "cell": None,
                               "before": " ".join(self.text_buf)[-400:]})
        elif not self.stack:
            if tag in ("p", "br", "div", "h1", "h2", "h3", "section-1", "title"):
                self.text_buf.append("\n")
        elif tag == "tr":
            self.stack[-1]["row"] = []
        elif tag in ("td", "th", "te", "tu"):
            t = self.stack[-1]
            if t["row"] is None:
                t["row"] = []
            t["cell"] = {"text": [], "rs": int(re.sub(r"\D", "", a.get("rowspan", "1") or "1") or 1),
                         "cs": int(re.sub(r"\D", "", a.get("colspan", "1") or "1") or 1)}
        elif tag == "br" and self.stack[-1]["cell"] is not None:
            self.stack[-1]["cell"]["text"].append(" ")

    def handle_endtag(self, tag):
        if not self.stack:
            return
        t = self.stack[-1]
        if tag in ("td", "th", "te", "tu") and t["cell"] is not None:
            t["row"].append(t["cell"]); t["cell"] = None
        elif tag == "tr" and t["row"] is not None:
            t["rows"].append(t["row"]); t["row"] = None
        elif tag == "table":
            if t["row"]:
                t["rows"].append(t["row"])
            self.stack.pop()
            self.tables.append({"before": t["before"], "grid": _expand(t["rows"])})
            self.text_buf = []

    def handle_data(self, d):
        if self.stack:
            c = self.stack[-1]["cell"]
            if c is not None:
                c["text"].append(d)
        else:
            self.text_buf.append(d)


def _clean(s):
    return re.sub(r"\s+", " ", s).strip()


def _expand(rows):
    grid, pend = [], {}
    for r in rows:
        out, ci = [], 0
        cells = list(r)
        while cells or ci in pend:
            if ci in pend:
                txt, left = pend[ci]
                out.append(txt)
                if left > 1:
                    pend[ci] = (txt, left - 1)
                else:
                    del pend[ci]
                ci += 1
                continue
            c = cells.pop(0)
            txt = _clean("".join(c["text"]))
            for _ in range(c["cs"]):
                out.append(txt)
                if c["rs"] > 1:
                    pend[ci] = (txt, c["rs"] - 1)
                ci += 1
        grid.append(out)
    return grid


def tables(html):
    p = _P()
    p.feed(html)
    for t in p.tables:
        t["before"] = _clean(_html.unescape(t["before"]))
    return p.tables

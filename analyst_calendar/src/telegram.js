// t.me/s/<채널> 공개 프리뷰 → 🔥 발간 보고서 목록.
// research_archive/telegram.py 의 parse_channel_html 과 같은 규칙.

export const COMPLIANCE_PHRASE = "컴플라이언스 승인을 득한";

const decode = (s) =>
  s.replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">")
   .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&nbsp;/g, " ");

export function parseChannelHtml(html) {
  const posts = [];
  const chunks = html.split(/<div class="tgme_widget_message [^"]*" data-post="/).slice(1);
  for (const chunk of chunks) {
    const m = chunk.match(/^[^"\/]+\/(\d+)"/);
    if (!m) continue;
    const msgId = Number(m[1]);
    const t = chunk.match(/<div class="tgme_widget_message_text[^"]*"[^>]*>([\s\S]*?)<\/div>/);
    const inner = t ? t[1] : "";
    const links = [...inner.matchAll(/<a [^>]*href="([^"]+)"/g)]
      .map((x) => decode(x[1])).filter((h) => !h.startsWith("?q="));
    const text = decode(inner.replace(/<br\s*\/?>/g, "\n").replace(/<[^>]+>/g, ""));
    const d = chunk.match(/<time datetime="([^"]+)"/);
    const permalink = (chunk.match(/class="tgme_widget_message_date"[^>]*>\s*<a href="([^"]+)"/) || [])[1] || "";
    posts.push({ msgId, text, links, dateIso: d ? d[1] : "", permalink });
  }
  return posts.sort((a, b) => a.msgId - b.msgId);
}

export function isReport(p) {
  return p.text.replace(/\s/g, "").includes(COMPLIANCE_PHRASE.replace(/\s/g, ""));
}

// KST 날짜 (YYYY-MM-DD)
export function kstDate(iso) {
  const d = new Date(new Date(iso).getTime() + 9 * 3600 * 1000);
  return d.toISOString().slice(0, 10);
}

export function toReport(p) {
  const title = (p.text.match(/[「『]([^」』]+)[」』]/) || [])[1]
    || p.text.trim().split("\n")[0].replace(/[🔥✅☞#]/g, "").trim();
  const firstLine = p.text.trim().split("\n")[0];
  const tags = [...firstLine.matchAll(/#([\w가-힣.·]+)/g)].map((x) => x[1]);
  const url = p.links.find((l) => /^https?:/i.test(l) && !l.includes("t.me/")) || null;
  const kind = /인뎁스|in-?depth/i.test(firstLine) ? "인뎁스"
    : /산업|섹터|업종/.test(firstLine) ? "산업" : "기업";
  return {
    id: `tg-${p.msgId}`, type: "report", date: kstDate(p.dateIso),
    time: p.dateIso, title: title.trim(), tags, kind, url, permalink: p.permalink,
  };
}

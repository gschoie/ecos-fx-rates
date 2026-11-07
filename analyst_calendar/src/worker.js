import { parseChannelHtml, isReport, toReport } from "./telegram.js";
import { ANALYSTS, assignAnalyst } from "./analysts.js";

const UA = "Mozilla/5.0 (compatible; analyst-calendar/1.0)";
const json = (data, ttl = 300) => new Response(JSON.stringify(data), {
  headers: { "content-type": "application/json; charset=utf-8",
             "cache-control": `public, max-age=${ttl}` },
});

async function fetchReports(env) {
  const ch = env.TG_CHANNEL || "HI_GS";
  const maxPages = Number(env.TG_MAX_PAGES || 6);
  const out = new Map();
  let before = null;
  for (let i = 0; i < maxPages; i++) {
    const u = `https://t.me/s/${ch}` + (before ? `?before=${before}` : "");
    const r = await fetch(u, { headers: { "user-agent": UA, "accept-language": "ko" },
                               cf: { cacheTtl: 600, cacheEverything: true } });
    if (!r.ok) break;
    const posts = parseChannelHtml(await r.text());
    if (!posts.length) break;
    for (const p of posts) if (isReport(p)) {
      const rep = toReport(p);
      rep.analyst = assignAnalyst(rep.tags, rep.title);
      out.set(rep.id, rep);
    }
    if (before && posts[0].msgId >= before) break;
    before = posts[0].msgId;
  }
  return [...out.values()].sort((a, b) => b.time.localeCompare(a.time));
}

// 세미나 / NDR — 구글 캘린더 연동 자리 (아직 껍데기).
// TODO: env.GCAL_SEMINAR_ICS / env.GCAL_NDR_ICS 의 iCal 을 읽어 아래 형태로 변환
//   { id, type: "seminar"|"ndr", date: "YYYY-MM-DD", start, end, title,
//     company, location, analyst }
async function fetchCalendarEvents(env, type) {
  return [];
}

export default {
  async fetch(req, env, ctx) {
    const { pathname } = new URL(req.url);
    try {
      if (pathname === "/api/reports") return json(await fetchReports(env), 600);
      if (pathname === "/api/seminars") return json(await fetchCalendarEvents(env, "seminar"));
      if (pathname === "/api/ndr") return json(await fetchCalendarEvents(env, "ndr"));
      if (pathname === "/api/analysts") return json(ANALYSTS, 3600);
    } catch (e) {
      return json({ error: String(e) }, 0);
    }
    return env.ASSETS.fetch(req);
  },
};

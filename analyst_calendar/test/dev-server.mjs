// 로컬 확인용: fixture HTML 을 텔레그램 대신 쓰는 미니 서버 (wrangler 없이)
import http from "node:http";
import { readFileSync } from "node:fs";
import { parseChannelHtml, isReport, toReport } from "../src/telegram.js";
import { ANALYSTS, assignAnalyst } from "../src/analysts.js";
const html = readFileSync(new URL("../../tests/fixture_channel.html", import.meta.url), "utf8");
const reports = parseChannelHtml(html).filter(isReport).map(p => { const r = toReport(p); r.analyst = assignAnalyst(r.tags, r.title); return r; });
http.createServer((req, res) => {
  const j = (d) => { res.setHeader("content-type","application/json"); res.end(JSON.stringify(d)); };
  if (req.url === "/api/reports") return j(reports);
  if (req.url === "/api/analysts") return j(ANALYSTS);
  if (req.url.startsWith("/api/")) return j([]);
  res.setHeader("content-type","text/html"); res.end(readFileSync(new URL("../public/index.html", import.meta.url)));
}).listen(8787, () => console.log("http://localhost:8787"));

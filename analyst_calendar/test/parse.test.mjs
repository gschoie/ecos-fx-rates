import { readFileSync } from "node:fs";
import assert from "node:assert";
import { parseChannelHtml, isReport, toReport } from "../src/telegram.js";
import { assignAnalyst } from "../src/analysts.js";

const html = readFileSync(new URL("../../tests/fixture_channel.html", import.meta.url), "utf8");
const posts = parseChannelHtml(html);
assert.equal(posts.length, 3);
const reps = posts.filter(isReport).map(toReport);
assert.equal(reps.length, 2);
assert.equal(reps[0].title, "미 해군 MRO의 최대 수혜주");
assert.deepEqual(reps[0].tags, ["한화오션"]);
assert.equal(reps[0].date, "2026-09-17");          // 23:10Z → KST 다음날
assert.equal(reps[0].url, "https://example-sec.com/research/report_view?id=98765");
assert.equal(reps[0].permalink, "https://t.me/HI_GS/1202");
assert.equal(reps[1].kind, "인뎁스");
assert.equal(assignAnalyst(reps[0].tags, reps[0].title), "ship");
console.log("ok", reps);

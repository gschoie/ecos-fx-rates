/*******************************************************************
 * Telegram 리서치 보고서 → Google Drive 자동 아카이빙 (Apps Script 버전)
 *
 * 사용법 (자세한 안내는 저장소 apps_script/README.md):
 *   1) 아래 GEMINI_API_KEY 에 키 붙여넣기
 *   2) 함수 선택에서 setup 실행 → 권한 허용 (매일 9시 트리거 설치됨)
 *   3) runTest15 실행 → Drive/시트 결과 확인
 *   4) runBackfill 실행 → 과거 게시물 전체 처리 (자동으로 이어서 실행됨)
 *******************************************************************/

/**** ① 설정 ****************************************************/

// ↓↓↓ 여기에 Gemini API 키 붙여넣기 (https://aistudio.google.com/apikey)
const GEMINI_API_KEY = '';

const CHANNEL = 'HI_GS';
const COMPLIANCE_PHRASE = '컴플라이언스 승인을 득한';
const ROOT_FOLDER_NAME = 'Research Reports';
const INDEX_NAME = 'Report Master Index';
const STATE_FILE_NAME = '_archive_state.json';
const INDUSTRIES = ['조선', '방산', '기계'];
const FALLBACK_INDUSTRY = '기타';
const MAX_FILENAME_LEN = 120;
const GEMINI_MODELS = ['gemini-3.8-flash', 'gemini-flash-latest'];
const MAX_PDF_MB = 19; // Gemini 인라인 첨부 한도
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36';

const COMPANY_INDUSTRY_MAP = {
  // 조선
  '한화오션': '조선', 'HD현대중공업': '조선', '삼성중공업': '조선',
  'HD한국조선해양': '조선', 'HD현대미포': '조선', '현대미포조선': '조선',
  'HJ중공업': '조선', '케이조선': '조선', '대한조선': '조선',
  'HD현대마린솔루션': '조선', 'HD현대마린엔진': '조선', '한화엔진': '조선',
  'STX엔진': '조선', '성광벤드': '조선', '태광': '조선', '동성화인텍': '조선',
  '세진중공업': '조선', '오리엔탈정공': '조선',
  // 방산
  '한화에어로스페이스': '방산', 'LIG넥스원': '방산', '현대로템': '방산',
  '한국항공우주': '방산', 'KAI': '방산', '풍산': '방산', '한화시스템': '방산',
  'SNT다이내믹스': '방산', 'SNT모티브': '방산', '휴니드': '방산',
  '빅텍': '방산', '코츠테크놀로지': '방산', 'STX중공업': '방산',
  // 기계
  '두산에너빌리티': '기계', '두산밥캣': '기계', 'HD현대인프라코어': '기계',
  'HD현대건설기계': '기계', 'HD현대일렉트릭': '기계', '효성중공업': '기계',
  'LS일렉트릭': '기계', '대동': '기계', 'TYM': '기계', '디와이파워': '기계',
  '씨에스베어링': '기계', '씨에스윈드': '기계', 'SK오션플랜트': '기계',
};

const INDEX_COLUMNS = [
  'Report ID', '발간일', '산업', '자료유형', '기업', '보고서 제목',
  'AI 핵심키워드', '투자의견', 'Target Price', '이전 Target Price',
  'TP 변경 여부', '투자의견 변경 여부', '해당 기업 Page Range',
  'Telegram 원문 링크', '원본 보고서 URL', 'Google Drive PDF 링크',
  '수집일', '처리 상태',
];

/**** ② 사용자 실행 함수 *****************************************/

/** 최초 1회: 권한 승인 + 폴더/시트 생성 + 매일 9시 트리거 설치 */
function setup() {
  const ctx = makeContext_();
  installDailyTrigger_();
  const tz = Session.getScriptTimeZone();
  Logger.log('설정 완료!');
  Logger.log('- Drive 폴더: ' + ctx.rootFolder.getUrl());
  Logger.log('- Master Index: ' + ctx.ss.getUrl());
  Logger.log('- 매일 9시 자동 실행 트리거 설치됨');
  if (tz !== 'Asia/Seoul') {
    Logger.log('⚠️ 프로젝트 시간대가 ' + tz + ' 입니다. 왼쪽 ⚙️(프로젝트 설정) → ' +
      '시간대를 "(GMT+09:00) 서울"로 바꿔야 오전 9시(한국시간)에 실행됩니다.');
  }
}

/** 테스트: 최근 보고서 15건만 처리 */
function runTest15() {
  runWithLock_(function () {
    const n = processRecent_(15);
    Logger.log('테스트 완료: 보고서 ' + n + '건 처리');
  });
}

/** 매일 자동 실행: 새 게시물만 처리 (트리거가 호출) */
function runDaily() {
  runWithLock_(function () {
    const ctx = makeContext_();
    let posts = [];
    if (!ctx.state.lastSeenId) {
      posts = fetchPage_(null); // 최초 실행: 최신 1페이지를 기준점으로
    } else {
      posts = fetchNew_(ctx.state.lastSeenId);
    }
    let done = 0;
    posts.forEach(function (p) {
      if (processPost_(p, ctx)) done++;
      ctx.state.lastSeenId = Math.max(ctx.state.lastSeenId || 0, p.msgId);
    });
    saveState_(ctx);
    Logger.log('Daily 완료: 새 게시물 ' + posts.length + '건 중 보고서 ' + done + '건 처리');
  });
}

/** 과거 게시물 전체 backfill. 5분 단위로 끊어서 자동으로 이어서 실행됨 */
function runBackfill() {
  deleteTriggers_('runBackfillContinue_');
  runWithLock_(function () {
    const finished = backfillChunk_();
    if (!finished) {
      ScriptApp.newTrigger('runBackfillContinue_').timeBased().after(60 * 1000).create();
      Logger.log('시간 제한으로 일시 중단 — 1분 뒤 자동으로 이어서 실행됩니다.');
    } else {
      Logger.log('🎉 Backfill 완료: 채널 처음까지 모두 처리했습니다.');
    }
  });
}

/** (내부용) backfill 연속 실행 트리거가 호출 */
function runBackfillContinue_() { runBackfill(); }

/** backfill 자동 연속 실행을 중단하고 싶을 때 실행 */
function stopBackfill() {
  deleteTriggers_('runBackfillContinue_');
  Logger.log('Backfill 연속 실행을 중단했습니다. runBackfill을 다시 실행하면 이어서 진행됩니다.');
}

/** ⚠️ 전체 초기화: 저장된 PDF·시트 기록·처리 이력을 모두 지우고 처음 상태로.
 *  테스트 결과가 마음에 안 들어 처음부터 다시 돌리고 싶을 때만 실행. */
function resetAllData() {
  deleteTriggers_('runBackfillContinue_');
  const root = getOrCreateFolder_(null, ROOT_FOLDER_NAME);
  // 산업 폴더 통째로 휴지통으로
  const folders = root.getFolders();
  while (folders.hasNext()) folders.next().setTrashed(true);
  // 상태 파일 삭제
  const st = root.getFilesByName(STATE_FILE_NAME);
  while (st.hasNext()) st.next().setTrashed(true);
  // 시트는 헤더만 남기고 비우기
  const it = root.getFilesByName(INDEX_NAME);
  if (it.hasNext()) {
    const sheet = SpreadsheetApp.open(it.next()).getSheets()[0];
    if (sheet.getLastRow() > 1) {
      sheet.getRange(2, 1, sheet.getLastRow() - 1, sheet.getLastColumn()).clearContent();
    }
  }
  Logger.log('초기화 완료. runTest15 또는 runBackfill을 다시 실행하세요.');
}

/**** ③ 파이프라인 ***********************************************/

function makeContext_() {
  const rootFolder = getOrCreateFolder_(null, ROOT_FOLDER_NAME);
  const ss = ensureIndexSheet_(rootFolder);
  const sheet = ss.getSheets()[0];
  const state = loadState_(rootFolder);
  const rows = sheet.getLastRow() > 1
    ? sheet.getRange(2, 1, sheet.getLastRow() - 1, INDEX_COLUMNS.length).getValues()
    : [];
  return {
    rootFolder: rootFolder, ss: ss, sheet: sheet, state: state,
    tpHistory: buildTpHistory_(rows), folderCache: {},
  };
}

function runWithLock_(fn) {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(5000)) {
    Logger.log('다른 실행이 진행 중이라 이번 실행은 건너뜁니다.');
    return;
  }
  try { fn(); } finally { lock.releaseLock(); }
}

/** 최신 게시물부터 과거로 훑어 보고서 limit건 처리 (시간 초과 시 재실행하면 이어짐) */
function processRecent_(limit) {
  const ctx = makeContext_();
  const startMs = Date.now();
  const BUDGET_MS = 4.3 * 60 * 1000;
  let before = null, done = 0, pages = 0, timeUp = false;
  outer:
  while (done < limit && pages < 200) {
    const posts = fetchPage_(before);
    if (!posts.length) break;
    pages++;
    for (let i = posts.length - 1; i >= 0 && done < limit; i--) {
      if (Date.now() - startMs >= BUDGET_MS) { timeUp = true; break outer; }
      const p = posts[i];
      if (!p.isReport || seen_(ctx.state, p)) continue;
      if (processPost_(p, ctx)) { done++; saveState_(ctx); }
    }
    const oldest = posts[0].msgId;
    if (before !== null && oldest >= before) break;
    before = oldest;
    if (before <= 1) break;
    Utilities.sleep(700);
  }
  saveState_(ctx);
  if (timeUp) {
    Logger.log('⏱ 시간 제한 도달 (' + done + '건 처리) — runTest15를 다시 실행하면 이어서 처리합니다.');
  }
  return done;
}

/** backfill 1회분(약 4.5분). 끝까지 갔으면 true */
function backfillChunk_() {
  const ctx = makeContext_();
  const startMs = Date.now();
  const BUDGET_MS = 4.5 * 60 * 1000;
  let before = ctx.state.backfillBefore || null;
  let done = 0;
  try {
    while (Date.now() - startMs < BUDGET_MS) {
      const posts = fetchPage_(before);
      if (!posts.length) { ctx.state.backfillDone = true; return true; }
      for (let i = posts.length - 1; i >= 0; i--) {
        if (Date.now() - startMs >= BUDGET_MS) return false;
        if (processPost_(posts[i], ctx)) { done++; saveState_(ctx); }
      }
      const oldest = posts[0].msgId;
      if (before !== null && oldest >= before) { ctx.state.backfillDone = true; return true; }
      before = oldest;
      ctx.state.backfillBefore = before;
      if (before <= 1) { ctx.state.backfillDone = true; return true; }
      Utilities.sleep(700);
    }
    return false;
  } finally {
    saveState_(ctx);
    Logger.log('이번 실행 처리: 보고서 ' + done + '건 (커서 msg_id ' + (before || '최신') + ')');
  }
}

/** 게시물 1건 처리. 업로드가 일어나면 true */
function processPost_(post, ctx) {
  if (seen_(ctx.state, post)) return false;
  if (!post.isReport) { mark_(ctx.state, post); return false; }
  const url = post.reportUrl;
  if (!url) { mark_(ctx.state, post); return false; }

  Logger.log('▶ ' + post.permalink + ' 처리 중… (' + post.titleGuess.slice(0, 40) + ')');
  let pdf, finalUrl;
  try {
    const r = fetchPdf_(url);
    pdf = r.bytes; finalUrl = r.url;
  } catch (e) {
    Logger.log('  [error] PDF 다운로드 실패: ' + e);
    appendErrorRow_(ctx, post, url, 'PDF 다운로드 실패: ' + e);
    mark_(ctx.state, post, url);
    return false;
  }

  const hash = sha256_(pdf);
  if (ctx.state.pdfHashes.indexOf(hash) >= 0) {
    Logger.log('  [skip] 동일 PDF(hash) 이미 저장됨');
    mark_(ctx.state, post, url, hash);
    return false;
  }

  const meta = analyze_(pdf, post);
  let year = (meta.publishedDate || '').slice(0, 4);
  if (!/^20\d\d$/.test(year)) {
    year = (post.dateIso || new Date().toISOString()).slice(0, 4);
    if (!meta.publishedDate) meta.publishedDate = (post.dateIso || '').slice(0, 10);
  }

  const filename = buildFilename_(meta);
  const folder = industryYearFolder_(ctx, meta.industry, year);
  const file = folder.createFile(Utilities.newBlob(pdf, 'application/pdf', filename));
  Logger.log('  ✔ 저장: ' + meta.industry + '/' + year + '/' + filename +
    ' [' + meta.analysisSource + ']');

  const reportId = 'R' + (meta.publishedDate || year).replace(/-/g, '') + '_M' + post.msgId;
  const rows = buildRows_(reportId, meta, post, finalUrl, file.getUrl(), ctx.tpHistory);
  appendRows_(ctx.sheet, rows);
  mark_(ctx.state, post, url, hash);
  return true;
}

/**** ④ Telegram 수집 ********************************************/

function fetchPage_(before) {
  let url = 'https://t.me/s/' + CHANNEL;
  if (before) url += '?before=' + before;
  const resp = UrlFetchApp.fetch(url, {
    muteHttpExceptions: true, followRedirects: true,
    headers: { 'User-Agent': UA, 'Accept-Language': 'ko,en;q=0.8' },
  });
  if (resp.getResponseCode() !== 200) {
    throw new Error('텔레그램 페이지 조회 실패 (HTTP ' + resp.getResponseCode() + ')');
  }
  const html = resp.getContentText();
  if (html.indexOf('tgme_widget_message') < 0) return [];
  return parseChannelHtml_(html);
}

function fetchNew_(sinceId) {
  const collected = {};
  let before = null;
  for (let i = 0; i < 50; i++) {
    const posts = fetchPage_(before);
    if (!posts.length) break;
    posts.forEach(function (p) { if (p.msgId > sinceId) collected[p.msgId] = p; });
    const oldest = posts[0].msgId;
    if (oldest <= sinceId + 1) break;
    before = oldest;
    Utilities.sleep(700);
  }
  return Object.keys(collected).map(Number).sort(function (a, b) { return a - b; })
    .map(function (k) { return collected[k]; });
}

function parseChannelHtml_(html) {
  const posts = [];
  const blocks = html.split('tgme_widget_message_wrap');
  for (let i = 1; i < blocks.length; i++) {
    const b = blocks[i];
    const m = b.match(/data-post="([^"]+\/(\d+))"/);
    if (!m) continue;
    const msgId = parseInt(m[2], 10);

    const textM = b.match(/<div class="tgme_widget_message_text[^"]*"[^>]*>([\s\S]*?)<\/div>/);
    const rawHtml = textM ? textM[1] : '';
    const links = [];
    const linkRe = /<a[^>]+href="([^"]+)"/g;
    let lm;
    while ((lm = linkRe.exec(rawHtml)) !== null) {
      const href = htmlDecode_(lm[1]);
      if (href.indexOf('?q=') === 0) continue; // 해시태그 링크
      links.push(href);
    }
    const text = htmlDecode_(
      rawHtml.replace(/<br\s*\/?>/gi, '\n').replace(/<[^>]+>/g, ''));

    const dm = b.match(/<time datetime="([^"]+)"/);
    const compact = text.replace(/\s+/g, '');
    const reportUrl = links.filter(function (l) {
      return /^https?:/i.test(l) && l.indexOf('t.me/') < 0;
    })[0] || null;
    const tm = text.match(/[「『]([^」』]+)[」』]/);
    const firstLine = stripEmoji_(text.trim().split('\n')[0] || '')
      .replace(/[☞#]/g, '').trim();

    posts.push({
      msgId: msgId,
      text: text,
      links: links,
      hashtags: (text.match(/#([\w가-힣.·]+)/g) || []).map(function (s) { return s.slice(1); }),
      dateIso: dm ? dm[1] : '',
      permalink: 'https://t.me/' + m[1],
      isReport: compact.indexOf(COMPLIANCE_PHRASE.replace(/\s+/g, '')) >= 0,
      reportUrl: reportUrl,
      titleGuess: stripEmoji_(tm ? tm[1] : firstLine).trim(),
    });
  }
  posts.sort(function (a, b) { return a.msgId - b.msgId; });
  return posts;
}

function htmlDecode_(s) {
  return s.replace(/&#(\d+);/g, function (_, n) { return String.fromCodePoint(parseInt(n, 10)); })
    .replace(/&#x([0-9a-f]+);/gi, function (_, n) { return String.fromCodePoint(parseInt(n, 16)); })
    .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&nbsp;/g, ' ').replace(/&amp;/g, '&');
}

/** 이모지·깨진 문자 제거 (파일명/제목용) */
function stripEmoji_(s) {
  return String(s || '')
    .replace(/[\p{Extended_Pictographic}️‍�]/gu, '')
    .replace(/[\uD800-\uDFFF]/g, ''); // 짝 잃은 서로게이트
}

/**** ⑤ PDF 다운로드 *********************************************/

function fetchPdf_(url) {
  const first = fetchBytes_(url, url);
  if (isPdf_(first.bytes)) return first;

  const html1 = bytesToText_(first.bytes);
  const cands = findPdfCandidates_(html1, first.url);
  for (let i = 0; i < cands.length; i++) {
    try {
      const r2 = fetchBytes_(cands[i], first.url);
      if (isPdf_(r2.bytes)) return r2;
      const cands2 = findPdfCandidates_(bytesToText_(r2.bytes), r2.url).slice(0, 4);
      for (let j = 0; j < cands2.length; j++) {
        try {
          const r3 = fetchBytes_(cands2[j], r2.url);
          if (isPdf_(r3.bytes)) return r3;
        } catch (e) { /* 다음 후보 */ }
      }
    } catch (e) { /* 다음 후보 */ }
  }
  throw new Error('PDF를 찾지 못했습니다: ' + url);
}

function fetchBytes_(url, referer) {
  let lastErr;
  for (let attempt = 0; attempt < 3; attempt++) {
    if (attempt > 0) Utilities.sleep(2000 * attempt);
    try {
      const resp = UrlFetchApp.fetch(url, {
        muteHttpExceptions: true, followRedirects: true,
        headers: { 'User-Agent': UA, 'Referer': referer || url },
      });
      const code = resp.getResponseCode();
      if (code >= 500) { lastErr = new Error('HTTP ' + code + ' — ' + url); continue; }
      if (code >= 400) throw new Error('HTTP ' + code + ' — ' + url);
      return { bytes: resp.getContent(), url: url };
    } catch (e) {
      lastErr = e;
      // 접속 자체가 불가능한 호스트는 재시도 무의미 (시간 낭비 방지)
      const em = String(e);
      if (em.indexOf('Address unavailable') >= 0 || em.indexOf('DNS') >= 0) break;
    }
  }
  throw lastErr;
}

function isPdf_(bytes) {
  if (!bytes || bytes.length < 4) return false;
  // '%PDF' = 37 80 68 70 (앞쪽 공백/BOM 허용)
  for (let i = 0; i < Math.min(bytes.length - 3, 1024); i++) {
    if (bytes[i] === 37 && bytes[i + 1] === 80 && bytes[i + 2] === 68 && bytes[i + 3] === 70) return true;
    if (bytes[i] > 32 && bytes[i] !== 37) return false;
  }
  return false;
}

function bytesToText_(bytes) {
  try { return Utilities.newBlob(bytes).getDataAsString('UTF-8'); }
  catch (e) { return ''; }
}

function findPdfCandidates_(html, baseUrl) {
  const cands = [];
  function add(u) {
    if (!u) return;
    const full = urlJoin_(baseUrl, htmlDecode_(u.trim()));
    if (full && cands.indexOf(full) < 0) cands.push(full);
  }
  let m;
  const attrRe = /<(?:a|iframe|embed|object)[^>]+(?:href|src|data)="([^"]*\.pdf[^"]*)"/gi;
  while ((m = attrRe.exec(html)) !== null) add(m[1]);
  const metaM = html.match(/http-equiv=["']?refresh["']?[^>]*content="[^"]*url=([^"]+)"/i);
  if (metaM) add(metaM[1]);
  const jsRe = /["']([^"']+\.pdf[^"']*)["']/gi;
  while ((m = jsRe.exec(html)) !== null) add(m[1]);
  const iframeRe = /<iframe[^>]+src="([^"]+)"/gi;
  while ((m = iframeRe.exec(html)) !== null) add(m[1]);
  return cands.slice(0, 8);
}

function urlJoin_(base, u) {
  if (/^https?:\/\//i.test(u)) return u;
  const bm = base.match(/^(https?:\/\/[^\/]+)(\/[^?#]*)?/i);
  if (!bm) return null;
  if (u.indexOf('//') === 0) return 'https:' + u;
  if (u.charAt(0) === '/') return bm[1] + u;
  const path = (bm[2] || '/').replace(/[^\/]*$/, '');
  return bm[1] + path + u;
}

/**** ⑥ Gemini 분석 **********************************************/

function geminiKey_() {
  return (GEMINI_API_KEY ||
    PropertiesService.getScriptProperties().getProperty('GEMINI_API_KEY') || '').trim();
}

let GEMINI_MODEL_CACHE = null; // 실행 1회 동안 캐시

/** 이 키로 실제 사용 가능한 모델 목록 조회 (404 방지) */
function activeGeminiModels_(key) {
  if (GEMINI_MODEL_CACHE) return GEMINI_MODEL_CACHE;
  let list = GEMINI_MODELS.slice();
  try {
    const resp = UrlFetchApp.fetch(
      'https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000',
      { headers: { 'x-goog-api-key': key }, muteHttpExceptions: true });
    if (resp.getResponseCode() === 200) {
      const avail = (JSON.parse(resp.getContentText()).models || [])
        .filter(function (m) {
          return (m.supportedGenerationMethods || []).indexOf('generateContent') >= 0;
        })
        .map(function (m) { return m.name.replace('models/', ''); });
      const preferred = GEMINI_MODELS.filter(function (m) { return avail.indexOf(m) >= 0; });
      const flash = avail.filter(function (n) {
        return n.indexOf('flash') >= 0 && n.indexOf('image') < 0 &&
          n.indexOf('tts') < 0 && n.indexOf('live') < 0 && preferred.indexOf(n) < 0;
      });
      const merged = preferred.concat(flash).slice(0, 4);
      if (merged.length) list = merged;
    }
  } catch (e) { /* 조회 실패 시 기본 목록 사용 */ }
  // 직전 실행에서 성공한 모델을 맨 앞으로 (한도 초과 모델에 낭비 방지)
  const lastGood = PropertiesService.getScriptProperties().getProperty('LAST_GOOD_MODEL');
  if (lastGood && list.indexOf(lastGood) > 0) {
    list.splice(list.indexOf(lastGood), 1);
    list.unshift(lastGood);
  }
  GEMINI_MODEL_CACHE = list;
  Logger.log('  [info] Gemini 모델 후보: ' + list.join(', '));
  return list;
}

/** 진단용: 내 키로 쓸 수 있는 모델 전체를 로그에 출력 */
function listGeminiModels() {
  const key = geminiKey_();
  if (!key) { Logger.log('GEMINI_API_KEY가 비어 있습니다.'); return; }
  const resp = UrlFetchApp.fetch(
    'https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000',
    { headers: { 'x-goog-api-key': key }, muteHttpExceptions: true });
  const models = (JSON.parse(resp.getContentText()).models || []);
  models.forEach(function (m) {
    if ((m.supportedGenerationMethods || []).indexOf('generateContent') >= 0) {
      Logger.log(m.name.replace('models/', ''));
    }
  });
}

const ANALYZE_PROMPT =
  '당신은 증권사 리서치 보고서 아카이빙 시스템의 메타데이터 추출기입니다.\n' +
  '첨부된 PDF 보고서와 이 보고서를 공유한 텔레그램 게시물 원문을 보고,\n' +
  '아래 JSON만 출력하세요 (설명·마크다운 금지):\n' +
  '{\n' +
  ' "published_date": "YYYY-MM-DD",          // 보고서 발간일 (1페이지에서 확인)\n' +
  ' "industry": "...",                        // 다음 중 하나: %IND% (없으면 "기타")\n' +
  ' "doc_type": "산업" 또는 "기업",           // 특정 1개 기업 분석이면 "기업", 산업/복수기업 인뎁스면 "산업"\n' +
  ' "title": "...",                           // 보고서 제목 (간결하게)\n' +
  ' "keywords": ["...", "..."],               // 투자포인트 중심 핵심 키워드 2~4개 (짧게). 예: "LNGC", "선가", "USV", "MRO"\n' +
  ' "companies": [                            // 다루는 기업들. 기업 보고서면 1개, 산업 인뎁스면 섹션별 전부\n' +
  '   {"name": "한화오션", "page_start": 18, "page_end": 25,  // 해당 기업 섹션 페이지 (모르면 null)\n' +
  '    "rating": "Buy", "target_price": "120,000원", "prev_target_price": "100,000원"}\n' +
  ' ]\n' +
  '}\n' +
  '규칙: 발간일을 못 찾으면 텔레그램 게시일 %TGDATE% 사용. target_price는 원 단위 표기 그대로.\n' +
  'keywords는 빈출 단어가 아니라 "나중에 검색할 때 쓸" 투자포인트 용어로.';

function analyze_(pdfBytes, post) {
  const meta = {
    publishedDate: '', industry: '', docType: '', title: '',
    keywords: [], companies: [], analysisSource: 'heuristic',
  };
  const key = geminiKey_();
  const tgDate = (post.dateIso || '').slice(0, 10);

  if (key && pdfBytes.length < MAX_PDF_MB * 1024 * 1024) {
    const models = activeGeminiModels_(key);
    Utilities.sleep(3000); // 무료 등급 분당 한도 보호
    let retried = false;
    for (let mi = 0; mi < models.length; mi++) {
      try {
        const d = callGemini_(models[mi], key, pdfBytes, post.text, tgDate);
        meta.publishedDate = String(d.published_date || '').slice(0, 10);
        meta.industry = d.industry || FALLBACK_INDUSTRY;
        meta.docType = d.doc_type || '';
        meta.title = String(d.title || post.titleGuess).trim();
        meta.keywords = (d.keywords || [])
          .map(function (k) { return String(k).trim().replace(/\s+/g, ''); })
          .filter(String).slice(0, 4);
        meta.companies = (d.companies || []).filter(function (c) { return c && c.name; })
          .map(function (c) {
            return {
              name: String(c.name).trim(),
              pageStart: c.page_start || null, pageEnd: c.page_end || null,
              rating: String(c.rating || ''), tp: String(c.target_price || ''),
              prevTp: String(c.prev_target_price || ''),
            };
          });
        meta.analysisSource = 'ai:' + models[mi];
        PropertiesService.getScriptProperties()
          .setProperty('LAST_GOOD_MODEL', models[mi]);
        sanity_(meta, post);
        return meta;
      } catch (e) {
        const msg = String(e);
        Logger.log('  [warn] Gemini(' + models[mi] + ') 실패: ' + msg.slice(0, 150));
        // 429(한도 초과)는 기다려도 소용없는 경우가 많아 바로 다음 모델로
        if (msg.indexOf('503') >= 0 && !retried) {
          retried = true; Utilities.sleep(25000); mi--; continue;
        }
        if (msg.indexOf('404') >= 0 || msg.indexOf('429') >= 0 ||
            msg.indexOf('503') >= 0) continue; // 다음 모델
        break;
      }
    }
  }

  // 휴리스틱 폴백
  const comps = post.hashtags.filter(function (h) { return COMPANY_INDUSTRY_MAP[h]; });
  meta.publishedDate = tgDate;
  meta.industry = comps.length ? COMPANY_INDUSTRY_MAP[comps[0]] : guessIndustry_(post.text);
  meta.docType = comps.length === 1 ? '기업' : '산업';
  meta.title = post.titleGuess || '제목미상';
  meta.companies = comps.map(function (c) {
    return { name: c, pageStart: null, pageEnd: null, rating: '', tp: '', prevTp: '' };
  });
  return meta;
}

function callGemini_(model, key, pdfBytes, tgText, tgDate) {
  const prompt = ANALYZE_PROMPT.replace('%IND%', INDUSTRIES.join(', '))
    .replace('%TGDATE%', tgDate || '미상');
  const body = {
    contents: [{
      role: 'user',
      parts: [
        { inline_data: { mime_type: 'application/pdf', data: Utilities.base64Encode(pdfBytes) } },
        { text: prompt + '\n\n=== 텔레그램 게시물 ===\n' + tgText.slice(0, 2000) },
      ],
    }],
    generationConfig: { maxOutputTokens: 4000, responseMimeType: 'application/json' },
  };
  const resp = UrlFetchApp.fetch(
    'https://generativelanguage.googleapis.com/v1beta/models/' + model + ':generateContent',
    {
      method: 'post', contentType: 'application/json',
      payload: JSON.stringify(body), muteHttpExceptions: true,
      headers: { 'x-goog-api-key': key },
    });
  if (resp.getResponseCode() !== 200) {
    throw new Error('Gemini HTTP ' + resp.getResponseCode() + ': ' +
      resp.getContentText().slice(0, 300));
  }
  const data = JSON.parse(resp.getContentText());
  const parts = data.candidates[0].content.parts || [];
  const raw = parts.map(function (p) { return p.text || ''; }).join('');
  const jm = raw.match(/\{[\s\S]*\}/);
  if (!jm) throw new Error('JSON 파싱 실패: ' + raw.slice(0, 200));
  return JSON.parse(jm[0]);
}

function sanity_(meta, post) {
  if (!/^20\d\d-\d\d-\d\d$/.test(meta.publishedDate)) {
    meta.publishedDate = (post.dateIso || '').slice(0, 10);
  }
  if (!meta.title) meta.title = post.titleGuess || '제목미상';
  if (!meta.industry) meta.industry = FALLBACK_INDUSTRY;
  if (!meta.companies.length && post.hashtags.length === 1) {
    meta.companies = [{ name: post.hashtags[0], pageStart: null, pageEnd: null,
      rating: '', tp: '', prevTp: '' }];
  }
}

function guessIndustry_(text) {
  const hints = {
    '조선': ['조선', '선박', '선가', 'LNGC', '수주잔고', '신조선'],
    '방산': ['방산', '미사일', 'K9', '무기', '국방', '폴란드'],
    '기계': ['기계', '건설기계', '굴착기', '전력기기', '변압기', '농기계'],
  };
  let best = FALLBACK_INDUSTRY, bestN = 0;
  Object.keys(hints).forEach(function (ind) {
    let n = 0;
    hints[ind].forEach(function (w) { n += text.split(w).length - 1; });
    if (n > bestN) { best = ind; bestN = n; }
  });
  return best;
}

/**** ⑦ 파일명 / 인덱스 행 ****************************************/

function clean_(s) {
  return stripEmoji_(s).replace(/[\\\/:*?"<>|\n\r\t]/g, ' ')
    .replace(/\s+/g, ' ').trim();
}

function buildFilename_(meta) {
  const date = (meta.publishedDate || '00000000').replace(/-/g, '');
  const parts = [date];
  if (meta.docType === '기업' && meta.companies.length) {
    parts.push('[' + clean_(meta.companies[0].name) + ']');
  }
  let title = clean_(meta.title) || '제목미상';
  parts.push(title);
  if (meta.keywords.length) {
    parts.push('[' + meta.keywords.map(clean_).join('_') + ']');
  }
  let base = parts.join('_');
  if (base.length > MAX_FILENAME_LEN) {
    const overflow = base.length - MAX_FILENAME_LEN;
    const shortTitle = title.slice(0, Math.max(10, title.length - overflow)).trim() + '…';
    parts[parts.indexOf(title)] = shortTitle;
    base = parts.join('_').slice(0, MAX_FILENAME_LEN);
  }
  return base + '.pdf';
}

function buildTpHistory_(rows) {
  const COL = colIndex_();
  const latest = {};
  rows.map(function (r) {
    return {
      date: String(r[COL['발간일']] || ''), comp: String(r[COL['기업']] || '').trim(),
      rating: String(r[COL['투자의견']] || ''), tp: String(r[COL['Target Price']] || ''),
    };
  }).filter(function (e) { return e.comp && (e.rating || e.tp); })
    .sort(function (a, b) { return a.date < b.date ? -1 : 1; })
    .forEach(function (e) { latest[e.comp] = { rating: e.rating, tp: e.tp }; });
  return latest;
}

function tpNum_(tp) {
  const m = String(tp || '').match(/[\d,]+(\.\d+)?/);
  return m ? parseFloat(m[0].replace(/,/g, '')) : null;
}

function tpDiff_(hist, comp, rating, tp, prevTpReport) {
  let prevTp = '', tpChg = '', ratingChg = '';
  const prev = hist[comp];
  if (prev) {
    prevTp = prev.tp;
    const a = tpNum_(prev.tp), b = tpNum_(tp);
    if (a !== null && b !== null) {
      tpChg = b > a ? '상향 (+' + ((b - a) / a * 100).toFixed(1) + '%)'
        : b < a ? '하향 (' + ((b - a) / a * 100).toFixed(1) + '%)' : '유지';
    }
    if (prev.rating && rating) {
      ratingChg = prev.rating.trim().toLowerCase() === rating.trim().toLowerCase()
        ? '유지' : '변경 (' + prev.rating + '→' + rating + ')';
    }
  } else if (prevTpReport) {
    prevTp = prevTpReport;
    const a = tpNum_(prevTpReport), b = tpNum_(tp);
    if (a && b) {
      tpChg = b > a ? '상향 (+' + ((b - a) / a * 100).toFixed(1) + '%)'
        : b < a ? '하향 (' + ((b - a) / a * 100).toFixed(1) + '%)' : '유지';
    }
  }
  if (rating || tp) hist[comp] = { rating: rating, tp: tp };
  return [prevTp, tpChg, ratingChg];
}

function buildRows_(reportId, meta, post, pdfUrl, driveLink, hist) {
  const today = Utilities.formatDate(new Date(), 'Asia/Seoul', 'yyyy-MM-dd');
  const kw = meta.keywords.join(', ');
  const status = meta.analysisSource === 'heuristic' ? '완료(휴리스틱)' : '완료';

  function row(docType, c) {
    c = c || { name: '', rating: '', tp: '', prevTp: '', pageStart: null, pageEnd: null };
    let prevTp = '', tpChg = '', ratingChg = '';
    if (c.name) {
      const d = tpDiff_(hist, c.name, c.rating, c.tp, c.prevTp);
      prevTp = d[0]; tpChg = d[1]; ratingChg = d[2];
    }
    let pr = '';
    if (c.pageStart) pr = 'p.' + c.pageStart + (c.pageEnd ? '~' + c.pageEnd : '');
    return [reportId, meta.publishedDate, meta.industry, docType, c.name,
      meta.title, kw, c.rating || '', c.tp || '', prevTp, tpChg, ratingChg,
      pr, post.permalink, pdfUrl, driveLink, today, status];
  }

  const rows = [];
  if (meta.docType === '기업' && meta.companies.length === 1) {
    rows.push(row('기업', meta.companies[0]));
  } else {
    rows.push(row('산업', null));
    meta.companies.forEach(function (c) { rows.push(row('산업자료 내 기업섹션', c)); });
  }
  return rows;
}

function colIndex_() {
  const m = {};
  INDEX_COLUMNS.forEach(function (n, i) { m[n] = i; });
  return m;
}

function appendErrorRow_(ctx, post, url, status) {
  const COL = colIndex_();
  const r = new Array(INDEX_COLUMNS.length).fill('');
  r[COL['Report ID']] = 'ERR_M' + post.msgId;
  r[COL['보고서 제목']] = post.titleGuess;
  r[COL['Telegram 원문 링크']] = post.permalink;
  r[COL['원본 보고서 URL']] = url;
  r[COL['수집일']] = Utilities.formatDate(new Date(), 'Asia/Seoul', 'yyyy-MM-dd');
  r[COL['처리 상태']] = status;
  appendRows_(ctx.sheet, [r]);
}

/**** ⑧ Drive / Sheets / 상태 *************************************/

function getOrCreateFolder_(parent, name) {
  const it = parent ? parent.getFoldersByName(name) : DriveApp.getFoldersByName(name);
  if (it.hasNext()) return it.next();
  return parent ? parent.createFolder(name) : DriveApp.createFolder(name);
}

function industryYearFolder_(ctx, industry, year) {
  const key = industry + '/' + year;
  if (!ctx.folderCache[key]) {
    const ind = getOrCreateFolder_(ctx.rootFolder, clean_(industry) || FALLBACK_INDUSTRY);
    ctx.folderCache[key] = getOrCreateFolder_(ind, year);
  }
  return ctx.folderCache[key];
}

function ensureIndexSheet_(rootFolder) {
  const it = rootFolder.getFilesByName(INDEX_NAME);
  let ss;
  if (it.hasNext()) {
    ss = SpreadsheetApp.open(it.next());
  } else {
    ss = SpreadsheetApp.create(INDEX_NAME);
    DriveApp.getFileById(ss.getId()).moveTo(rootFolder);
  }
  const sheet = ss.getSheets()[0];
  const header = sheet.getRange(1, 1, 1, INDEX_COLUMNS.length).getValues()[0];
  if (String(header[0]) !== INDEX_COLUMNS[0]) {
    sheet.getRange(1, 1, 1, INDEX_COLUMNS.length).setValues([INDEX_COLUMNS]);
    sheet.setFrozenRows(1);
  }
  return ss;
}

function appendRows_(sheet, rows) {
  if (!rows.length) return;
  sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, INDEX_COLUMNS.length)
    .setValues(rows);
}

function loadState_(rootFolder) {
  const it = rootFolder.getFilesByName(STATE_FILE_NAME);
  let s = {};
  if (it.hasNext()) {
    try { s = JSON.parse(it.next().getBlob().getDataAsString()); } catch (e) { s = {}; }
  }
  s.processedMsgIds = s.processedMsgIds || [];
  s.processedUrls = s.processedUrls || [];
  s.pdfHashes = s.pdfHashes || [];
  return s;
}

function saveState_(ctx) {
  const json = JSON.stringify(ctx.state);
  const it = ctx.rootFolder.getFilesByName(STATE_FILE_NAME);
  if (it.hasNext()) it.next().setContent(json);
  else ctx.rootFolder.createFile(STATE_FILE_NAME, json, 'application/json');
}

function seen_(state, post) {
  if (state.processedMsgIds.indexOf(post.msgId) >= 0) return true;
  return !!(post.reportUrl && state.processedUrls.indexOf(post.reportUrl) >= 0);
}

function mark_(state, post, url, hash) {
  if (state.processedMsgIds.indexOf(post.msgId) < 0) state.processedMsgIds.push(post.msgId);
  if (url && state.processedUrls.indexOf(url) < 0) state.processedUrls.push(url);
  if (hash && state.pdfHashes.indexOf(hash) < 0) state.pdfHashes.push(hash);
}

function sha256_(bytes) {
  return Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, bytes)
    .map(function (b) { return ((b & 0xff) + 0x100).toString(16).slice(1); }).join('');
}

/**** ⑨ 트리거 ****************************************************/

function installDailyTrigger_() {
  deleteTriggers_('runDaily');
  ScriptApp.newTrigger('runDaily').timeBased().atHour(9).everyDays(1).create();
}

function deleteTriggers_(fnName) {
  ScriptApp.getProjectTriggers().forEach(function (t) {
    if (t.getHandlerFunction() === fnName) ScriptApp.deleteTrigger(t);
  });
}

# Analyst Calendar — 세미나 · NDR · 자료발간 달력

`analyst-calendar.animsam09.workers.dev` 를 본떠 만든 Cloudflare Worker(정적 페이지 + API).

| 분류 | 소스 | 상태 |
| --- | --- | --- |
| 세미나 | Google Calendar | 껍데기 (`src/worker.js` `fetchCalendarEvents` → 빈 배열) |
| NDR | Google Calendar | 껍데기 (동일) |
| 자료발간 | 🔥 불꽃 리서치 텔레그램 채널 `t.me/s/HI_GS` | 동작 (`src/telegram.js`, research_archive 와 같은 파싱 규칙) |

- 사람(애널리스트)은 `src/analysts.js` — 조선/방산/기계 담당 3명, 보고서 해시태그·제목으로 자동 배정.
  `name` 을 실제 이름으로 바꾸면 된다.
- API: `/api/reports` `/api/seminars` `/api/ndr` `/api/analysts`
- 화면: 월간 달력 / 목록, 분류·담당자 필터, 클릭 시 보고서·텔레그램 원문 링크.

## 로컬 확인 (wrangler 없이)
```bash
node analyst_calendar/test/parse.test.mjs      # 파서 테스트
node analyst_calendar/test/dev-server.mjs      # http://localhost:8787 (fixture 데이터)
```

## 배포
```bash
cd analyst_calendar && npx wrangler deploy
```

## TODO — 구글 캘린더 연동
`wrangler.toml` 의 `GCAL_SEMINAR_ICS` / `GCAL_NDR_ICS` 에 비공개 iCal 주소를 넣고
`fetchCalendarEvents` 에서 VEVENT → `{ id, type, date, start, end, title, company, location, analyst }` 로 변환.

# Research Archive — Telegram 리서치 보고서 → Google Drive 자동 아카이빙

`t.me/HI_GS` 채널에서 `✅ 컴플라이언스 승인을 득한 보고서입니다.` 문구가 있는
게시물만 골라 PDF를 내려받고, Claude API로 메타데이터(발간일·산업·기업·제목·
키워드·투자의견·TP)를 추출해 Google Drive `Research Reports/산업/연도/` 폴더에
저장하고 Google Sheets **Report Master Index**를 갱신합니다.

- 매일 아침 9시(KST)에 GitHub Actions가 자동 실행 (`daily` 모드)
- 과거 게시물 전체 backfill 지원 — 중단돼도 커서(state)로 이어서 처리
- 중복 방지: Telegram message ID + 원본 URL + PDF SHA-256 hash
- 산업 인뎁스 1개 PDF → Master Index에 산업 레코드 1 + 기업별 레코드 N (동일 Report ID, 페이지 범위 포함)
- TP/투자의견 변경: Master Index의 해당 기업 직전 레코드와 비교해 자동 계산

## 1. 사전 준비 (1회)

### Google Drive 인증 (사용자 OAuth — 권장)
> 개인 Gmail 계정에서는 서비스 계정의 저장용량이 0이라 파일 업로드가
> `storageQuotaExceeded`로 실패합니다. 반드시 아래 사용자 OAuth 방식을 쓰세요.
> (서비스 계정은 Google Workspace 공유 드라이브에서만 유효 — 코드는 둘 다 지원)

1. [Google Cloud Console](https://console.cloud.google.com)에서 프로젝트 생성,
   **Drive API**·**Sheets API** 활성화
2. **OAuth 동의 화면** 구성(External) 후 게시 상태를 **프로덕션**으로 변경
   (테스트 상태면 refresh token이 7일 뒤 만료됨)
3. **사용자 인증 정보 → OAuth 클라이언트 ID** 생성(유형: 웹 애플리케이션),
   승인된 리디렉션 URI에 `https://developers.google.com/oauthplayground` 추가
   → 클라이언트 ID/보안 비밀 복사
4. [OAuth Playground](https://developers.google.com/oauthplayground) 접속 →
   ⚙️ → "Use your own OAuth credentials" 체크 → ID/비밀 입력 →
   Step 1 스코프에 `https://www.googleapis.com/auth/drive https://www.googleapis.com/auth/spreadsheets`
   입력 → Authorize APIs → 구글 로그인·허용("확인되지 않은 앱" 경고는
   고급 → 이동으로 진행) → Step 2 "Exchange authorization code for tokens" →
   **Refresh token** 복사
5. Google Drive에 `Research Reports` 폴더를 만들고 폴더 URL의 ID 복사
   (`https://drive.google.com/drive/folders/<이 부분>`) — 본인 계정으로
   업로드하므로 폴더 공유는 필요 없음

### AI 분석 키 (선택 — 무료 옵션 있음)
PDF 내용 분석(키워드·TP·페이지범위 추출)에 쓸 키. 우선순위대로 하나만 있으면 됨:

1. `ANTHROPIC_API_KEY` — [console.anthropic.com](https://console.anthropic.com), 유료 (품질 최상)
2. `GEMINI_API_KEY` — [aistudio.google.com/apikey](https://aistudio.google.com/apikey)에서
   **무료** 발급 (신용카드 불필요, 일일 사용량 제한 내 무료 — 일 단위 보고서 처리엔 충분)
3. 둘 다 없음 — 휴리스틱 모드 (완전 무료). 게시물 해시태그/날짜 기반으로 동작하지만
   AI 키워드·TP·페이지범위는 추출되지 않음.

### GitHub Secrets 등록
저장소 Settings → Secrets and variables → Actions:

| Secret | 값 |
|---|---|
| `GDRIVE_OAUTH_CLIENT_ID` | OAuth 클라이언트 ID |
| `GDRIVE_OAUTH_CLIENT_SECRET` | OAuth 클라이언트 보안 비밀 |
| `GDRIVE_OAUTH_REFRESH_TOKEN` | OAuth Playground에서 받은 refresh token |
| `GDRIVE_ROOT_FOLDER_ID` | Research Reports 폴더 ID |
| `GDRIVE_SERVICE_ACCOUNT_JSON` | (Workspace 공유 드라이브 전용) 서비스 계정 키 JSON |
| `GEMINI_API_KEY` | (권장·무료) Google AI Studio 키 |
| `ANTHROPIC_API_KEY` | (선택·유료) Anthropic API 키 — 있으면 Gemini보다 우선 사용 |
| `MASTER_INDEX_SHEET_ID` | (선택) 기존 시트를 쓸 때만. 비우면 자동 생성 |

## 2. 실행 순서 (권장)

```bash
pip install -r research_archive/requirements.txt
export GDRIVE_SERVICE_ACCOUNT_JSON=/path/to/sa-key.json   # 또는 JSON 문자열
export GDRIVE_ROOT_FOLDER_ID=...
export ANTHROPIC_API_KEY=...
```

**① 테스트 (10~20건)** — 판별/분류/파일명/키워드/TP 정확도 확인:
```bash
python -m research_archive test --limit 15 --local   # Drive 없이 ./archive_out/에 저장
python -m research_archive test --limit 15           # 실제 Drive에 저장
```
`--local`은 `archive_out/` 아래에 동일한 산업/연도 폴더 구조와
`master_index.csv`를 만들어 결과를 미리 검수할 수 있습니다.

**② 과거 전체 Backfill**:
```bash
python -m research_archive backfill              # 채널 처음까지
python -m research_archive backfill --limit 100  # 100건씩 나눠서 (재실행 시 이어서)
```
GitHub Actions에서도 가능: Actions 탭 → Research Archive → Run workflow →
mode=`backfill`.

**③ 매일 자동 실행**: 별도 조작 불필요. 매일 09:00 KST에 `daily` 모드가 돌며
마지막 처리 이후의 새 게시물만 확인합니다.

## 3. 동작 방식

- **Telegram 접근**: 공개 채널 웹 프리뷰(`https://t.me/s/HI_GS`)를 스크레이핑하므로
  Telegram API 키/로그인이 필요 없습니다. `?before=<id>` 파라미터로 과거 페이지를
  순회합니다. (채널이 비공개로 바뀌면 Telethon 방식으로 전환 필요)
- **상태 저장**: Drive 루트 폴더의 `_archive_state.json`에 처리된 message ID,
  URL, PDF hash, backfill 커서를 저장 → GitHub Actions처럼 매번 새 환경에서
  실행돼도 이어서 동작합니다.
- **파일명**: `YYYYMMDD_[기업명]_보고서제목_[키워드1_키워드2].pdf`
  (산업자료는 기업명 생략, 전체 120자 제한)
- **폴더**: `Research Reports/<산업>/<연도>/` — 없으면 자동 생성.
  기본 산업: 조선·방산·기계 (그 외는 AI 판단 산업명 또는 `기타`)
- **실패 처리**: PDF 다운로드 실패 등은 Master Index에 `처리 상태`로 기록되어
  나중에 수동 확인 가능. 실패 게시물은 재시도하지 않고 건너뜁니다
  (재시도하려면 state에서 해당 message ID 제거).

## 4. Master Index 컬럼

`Report ID | 발간일 | 산업 | 자료유형 | 기업 | 보고서 제목 | AI 핵심키워드 |
투자의견 | Target Price | 이전 Target Price | TP 변경 여부 | 투자의견 변경 여부 |
해당 기업 Page Range | Telegram 원문 링크 | 원본 보고서 URL |
Google Drive PDF 링크 | 수집일 | 처리 상태`

자료유형: `산업` / `기업` / `산업자료 내 기업섹션`

## 5. 테스트

```bash
pip install pytest
python -m pytest tests/test_archive.py -q
```

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

### Google Cloud 서비스 계정
1. [Google Cloud Console](https://console.cloud.google.com)에서 프로젝트 생성
2. **Drive API**와 **Sheets API** 활성화 (APIs & Services → Enable)
3. IAM → 서비스 계정 생성 → 키(JSON) 발급·다운로드
4. Google Drive에 `Research Reports` 폴더를 만들고, 서비스 계정 이메일
   (`xxx@yyy.iam.gserviceaccount.com`)에게 **편집자**로 공유
5. 폴더 URL의 ID를 복사 (`https://drive.google.com/drive/folders/<이 부분>`)

> 참고: 서비스 계정이 업로드한 파일은 서비스 계정의 15GB 무료 용량을 사용합니다.
> Google Workspace 사용자라면 공유 드라이브(Shared Drive)를 쓰면 이 제약이 없습니다
> (코드는 둘 다 지원).

### Anthropic API 키
[console.anthropic.com](https://console.anthropic.com)에서 API 키 발급.
키가 없으면 AI 분석 대신 휴리스틱(게시물 해시태그/날짜 기반)으로 동작하지만
키워드·TP·페이지범위 품질이 크게 떨어지므로 키 사용을 권장합니다.

### GitHub Secrets 등록
저장소 Settings → Secrets and variables → Actions:

| Secret | 값 |
|---|---|
| `GDRIVE_SERVICE_ACCOUNT_JSON` | 서비스 계정 키 JSON 파일 내용 전체 |
| `GDRIVE_ROOT_FOLDER_ID` | Research Reports 폴더 ID |
| `ANTHROPIC_API_KEY` | Anthropic API 키 |
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

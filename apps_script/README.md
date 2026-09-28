# Apps Script 버전 설치 안내 (권장 방식)

구글 콘솔 OAuth 설정 없이, 본인 구글 계정 안에서 전체 파이프라인이 돌아가는 버전.
GitHub Actions 버전(`research_archive/`)의 후속으로, 동일한 기능을 제공한다.

## 설치 (5분, 최초 1회)

1. https://script.google.com/create 접속 (구글 로그인)
2. 편집기에 있는 기본 코드(`function myFunction()...`)를 지우고,
   [`Code.gs`](https://raw.githubusercontent.com/gschoie/ecos-fx-rates/main/apps_script/Code.gs)
   내용 전체를 복사해 붙여넣기
3. 코드 상단 `const GEMINI_API_KEY = '';` 의 따옴표 안에
   [Google AI Studio](https://aistudio.google.com/apikey)에서 발급한 무료 키 붙여넣기
4. 왼쪽 ⚙️ **프로젝트 설정** → **시간대**를 `(GMT+09:00) 서울`로 변경 (기본값이 미국일 수 있음)
5. 상단 함수 선택 드롭다운에서 **`setup`** 선택 → **실행** 클릭
   - "승인 필요" → 계정 선택 → "확인되지 않은 앱" 화면이 나오면 **고급 → 이동** → **허용**
   - 실행 로그에 "설정 완료!"와 Drive 폴더/시트 링크가 표시됨

이것으로 매일 오전 9시(한국시간) 자동 실행 트리거까지 설치 완료.

## 사용

| 함수 | 용도 |
|---|---|
| `setup` | 최초 1회: 권한 승인 + 폴더/시트 생성 + 매일 9시 트리거 |
| `runTest15` | 최근 보고서 15건 테스트 처리 |
| `runBackfill` | 과거 게시물 전체 처리. 5분 단위로 끊어 자동으로 이어서 실행 |
| `stopBackfill` | backfill 자동 연속 실행 중단 |
| `runDaily` | 새 게시물 처리 (트리거가 매일 호출 — 수동 실행도 가능) |

실행 결과는 편집기 하단 **실행 로그**와, 왼쪽 시계 아이콘(**트리거**)/**실행** 메뉴에서 확인.

## 결과물

- Drive `Research Reports/<산업>/<연도>/` 폴더에 PDF 저장
  (파일명: `YYYYMMDD_[기업명]_제목_[키워드].pdf`)
- 같은 폴더의 **Report Master Index** 시트에 보고서·기업별 레코드 축적
- `_archive_state.json`: 처리 이력(중복 방지·이어하기용) — 삭제하면 처음부터 다시 처리함

## GitHub Actions 버전과의 관계

`research_archive/`(Python)는 동일 기능의 이전 버전으로, 스케줄 실행은 꺼두었다
(수동 실행만 가능). Apps Script 버전이 정상 동작하면 그쪽은 무시해도 된다.

# PER·PBR 밴드 차트 — 작업 매뉴얼 (GS-DB2 이관용)

2026-11-12~14, `gschoie/ecos-fx-rates` 에서 만든 PER·PBR 밴드 자동화의 전체 기록.
GS-DB2 대시보드 「📊 피어그룹.Valuation」 메뉴 밑으로 옮기기 위한 인수인계 문서다.

---

## 1. 무엇을 만들었나

| 항목 | 내용 |
|---|---|
| 결과물 | 종목별 PNG·SVG 1장 = 위 **PER 밴드**, 아래 **PBR 밴드 + ROE 음영**(오른쪽 축) |
| 종목 | 46개 = ER 적재 종목과 동일 (`consensus/er_snapshot.py` 의 `COMPANIES`) — 조선 12·방산 20·건설기계 14 |
| 통화 | 한국 = 원화(천원 단위 축), 해외 = **USD** |
| 기간 | 2019년 ~ 올해+2(FY3, 지금은 2028E). Yahoo 만 있는 종목은 2022 ~ FY2(2027E) |
| 갱신 | 평일 17:30 KST 크론 + 수동 + `data/valuation/raw/` 에 엑셀 푸시 시 즉시 |
| 원형 | 사용자가 쓰던 DataGuide/Bloomberg 밴드 엑셀(LIG D&A PER Band / PBR Band Chart 이미지)을 그대로 흉내 냄 |

## 2. 파일 지도 (ecos-fx-rates)

```
valuation/
  ingest_uploads.py      ① 업로드 엑셀 → DB(csv)
  yahoo_fundamentals.py  ② Yahoo 연간 실적·컨센 → DB(csv)
  band_chart.py          ③ DB + 주가 → 밴드 차트
data/valuation/
  raw/                   업로드 원본 엑셀 (파일명 규칙 아래)
  annual_uploads.csv     연간 EPS·BPS·ROE (업로드)      ← ①
  multiples.csv          엑셀에서 쓰던 밴드 배수          ← ①
  prices_uploads.csv     한국 일간 수정주가(DataGuide)    ← ①
  annual_yahoo.csv       연간 EPS·BPS·ROE (Yahoo)        ← ②
  payout_yahoo.csv       배당성향(미래 BPS 추정용)        ← ②
output/valuation_band/
  <섹터>_<종목>.png / .svg   차트 46종목
  band_inputs.csv            차트에 실제로 쓴 연도별 값·출처·배수
.github/workflows/valuation-band.yml   자동 실행
```

## 3. 데이터 원천

### 3-1. 업로드 엑셀 (`data/valuation/raw/`)

파일명 규칙: `DG_<이름>_YYYYMMDD.xlsx` = DataGuide, `BB_<이름>_YYYYMMDD.xlsx` = Bloomberg.
같은 종목·연도·구분이 여러 파일에 있으면 **날짜가 최신인 파일이 이긴다.**

| 파일 | 형식 | 읽는 시트 | 내용 |
|---|---|---|---|
| `DG_다종목_20261103.xlsx` | DataGuide 다종목 | `GET`(실적), `☞추정입력+컨센GET`(모델·컨센), `GET주가`(일간), 기업별 밴드 시트 4행(배수) | 한국 34종목, 실적 2000~2025, 추정입력 ~2030, 컨센 ~2026 |
| `DG_HD현대중공업_20261028.xlsx` | DataGuide 단일 | `Actual`, `Forecast`(B~G 모델, I~L 컨센), `주가`, `Band` 4행 | |
| `DG_HD현대마린솔루션_20261026.xlsx` | 〃 | 〃 | 2022 이전은 상장 전 주식수 기준이라 단절 |
| `DG_대한조선_20261111.xlsx` | 〃 | 〃 | 2024~ |
| `BB_건설기계_20261026.xlsx` | Bloomberg | `티커`, 기업별 밴드 시트(12월 행 = 그해 값) | 해외 13 + 한국 일부(한국은 DG 우선이라 건너뜀). **전부 USD**. 원본 BDH 시트는 `#NAME?` 라 밴드 시트 캐시값을 읽음. 올해 이후 = BEST(컨센) |

`annual_uploads.csv` 의 `basis` 구분:
- `actual` = DataGuide 실적(발표기준)
- `model` = ☞추정입력 시트 값 — 과거는 **조정 실적**(예: HD한국조선해양 2017 분할 조정), 미래는 **사용자 자체 추정**
- `consensus` = DataGuide 컨센(중앙값) / Bloomberg BEST

### 3-2. Yahoo (`valuation/yahoo_fundamentals.py`)
- 46종목 전부 받음. 실적 약 4년(2022~2025) + 0y·+1y 컨센 EPS.
- 해외: `financialCurrency` 기준 USD 환산 — 실적 = 결산일 환율, 컨센 = 오늘 환율 (Yangzijiang 은 SGD 상장·CNY 보고, BAE 는 GBp→GBP).
- 회계연도: 결산월 1~5월이면 전년도 FY(일본 3월 결산 → FY2025 = 2026.3). Yahoo 0y = 마지막 실적 FY + 1.
- 한국: 원화 그대로, 업로드에 없는 해만 채움(예: 현대로템·한국카본 2027E).

### 3-3. 주가
- 한국: DataGuide 수정주가(업로드 파일 날짜까지) + 이후 Yahoo 종가(겹치는 날 비율로 이어 붙임).
- 해외: Yahoo 종가(`auto_adjust=False`, 분할만 반영) × 일간 환율 → USD.

## 4. 차트 규칙

**연도별 값 우선순위** (같은 해에 여러 값이면 앞이 이김)
```
업로드 model → 업로드 actual → 업로드 consensus → Yahoo actual → Yahoo consensus
```
- 업로드 actual 중 올해 이후 값은 버림(DataGuide 가 진행 중 연도를 실적 칸에 채워 둔 경우).
- 미래 BPS 가 없으면 `BPS(t) = BPS(t−1) + EPS(t) × (1 − 배당성향)`, 배당성향 없으면 30%.
- ROE 가 없으면 `EPS / 평균 BPS`.

**밴드 선**
- 그해 EPS(BPS) × 배수. 1~3월에 걸쳐 전년 값 → 당해 값으로 선형 전환하는 계단(엑셀 '계단' 열과 같은 방식).
- 적자 연도는 PER 밴드 선을 끊음.
- 배수: `multiples.csv`(엑셀에서 쓰던 5개) 우선. 없으면 과거 월말 PER·PBR 분포의 10·30·50·70·90% 를 깔끔한 수(1·1.5·2·2.5·3·4·5·6·7·8·10×10ⁿ)로 반올림.
- 세로축: 주가 최고치 × 1.35(둘째 배수 선까지는 보이게). 위쪽 배수 선은 잘려도 됨(엑셀 원본과 같음).
- 색: 주가 = DAOL 골드 `#A68A64`, 밴드 = 회색 5단계(낮은 배수가 진함), ROE = 연회색 음영.

## 5. 운영

| 하고 싶은 것 | 방법 |
|---|---|
| 새 엑셀 반영 | `data/valuation/raw/` 에 규칙대로 이름 붙여 푸시 → 워크플로 자동 실행 |
| 종목 추가·삭제 | `consensus/er_snapshot.py` 의 `COMPANIES` (ER 적재와 공유) |
| 배수 바꾸기 | `data/valuation/multiples.csv` 의 `per`·`pbr` 열(공백 구분 5개). 단 다음 ingest 때 엑셀 값으로 덮어써지므로 엑셀 쪽도 고칠 것 |
| 한 종목만 그려 보기 | `python valuation/band_chart.py --only 079550.KS,CAT` |
| 로컬 전체 실행 | `pip install -r peergroup/requirements.txt openpyxl` → ①②③ 순서로 실행 |
| 값 출처 확인 | `output/valuation_band/band_inputs.csv` (EPS_src 등: `upload:model`, `yahoo:consensus`, `추정:BPS+EPS×유보율` …) |

## 6. 자동화 상태 (2026-11-14 기준)

- 워크플로 `valuation-band.yml`: 평일 17:30 KST 크론 + workflow_dispatch + `data/valuation/raw/**`·`valuation/**` 푸시.
- 첫 실행(#28 머지 직후)은 `openpyxl` 미설치로 실패 → 워크플로 설치 줄에 `openpyxl` 추가로 수정.
- **16:44 KST 정시 예약 작업(「주보 ecos 3종 정시 발사」)에는 아직 안 들어감.** 예약 작업 내용은 그 작업이 결과를 올리는 대화에서만 고칠 수 있다. 그 대화에서
  `gh workflow run valuation-band.yml --repo gschoie/ecos-fx-rates --ref main` 를 4번째로 추가하면 된다. 그 전까지는 17:30 크론이 돌린다.

## 7. 주의할 점

1. **공개 저장소 문제** — ecos-fx-rates 는 공개 저장소이고, `data/valuation/` 에 DataGuide·Bloomberg 값과 **사용자 자체 추정치(☞추정입력)** 가 올라가 있다(사용자 지시로 푸시). 한국 커버리지 차트의 밴드 선도 자체 추정 EPS·BPS × 배수라 역산 가능. 비공개 전환은 GitHub Settings → General → Danger Zone → Change visibility. 전환하면 기존 커밋 이력도 함께 비공개가 되지만, 이미 퍼진 사본은 회수되지 않는다.
2. **비공개 전환 시 영향** — GS-DB2 대시보드 ER 화면(`er_report.html`)이 이 저장소 CSV 를 raw 주소로 읽으므로 끊긴다. Actions 무료 한도(월 2,000분)도 생긴다.
3. **데이터 메모**
   - 다종목 파일의 DataGuide 컨센 블록은 기간 설정이 2011~2026 이라 2027·2028E 컨센이 없다(추정입력은 2030까지).
   - 추정입력이 오래된 종목: 현대로템·한국카본(~2023), 두산에너빌리티(~2023). KAI 는 컨센 없음.
   - HD현대중공업 2025 실적 EPS 가 파일마다 다름(15,702 vs 13,486, 주식수 기준 차이).
   - HD한국조선해양 2016~2017: DataGuide 실적 ≠ 추정입력(분할 조정). 밴드는 추정입력 사용.
   - 한국 비커버리지 일부(현대엘리베이터·하이록코리아·와이지-원·진성티이씨·신진에스엠)는 엑셀 밴드 시트 주가가 2019~2020 에서 끊겨 있음(밴드 대상 아님).
   - Yahoo 의 한국 종목 애널리스트 수는 적다(두산밥캣 2명 등) — 한국은 업로드가 우선이라 영향 작음.

## 8. GS-DB2 로 옮기기 — 할 일

목표: GS-DB2 대시보드 「📊 피어그룹.Valuation」 메뉴 밑에 **PE·PB 밴드** 항목 추가.

선택지 (사용자 결정 필요):
- **A. 이미지만 GS-DB2 로 복사** — ecos 워크플로가 그린 PNG/SVG 를 GS-DB2 정적 폴더로 복사(크로스 저장소 푸시는 PAT 시크릿 필요)하거나, GS-DB2 쪽 워크플로가 ecos 산출물을 받아 옴. 계산은 ecos 에 그대로.
- **B. 파이프라인 통째로 GS-DB2 로 이관** — `valuation/` 3개 스크립트 + `data/valuation/` + 워크플로를 GS-DB2 로 옮김. `er_snapshot.COMPANIES` 의존은 종목 목록을 GS-DB2 쪽에 복사하거나 ecos 에서 읽게 바꿀 것.
- 어느 쪽이든 GS-DB2 Pages 는 공개이므로, 자체 추정치가 드러나는 한국 커버리지 이미지를 올릴지(혹은 컨센 기준판만 올릴지) 먼저 정할 것.

메뉴 페이지 구성 제안: 섹터 탭(조선·방산·건설기계) → 종목 카드 그리드(PNG 썸네일, 클릭 시 SVG 원본), 상단에 기준일·자료 출처, 하단에 `band_inputs.csv` 링크.

### GS-DB2 세션에 붙여 넣을 지시문

```
gschoie/ecos-fx-rates 의 docs/valuation_band_MANUAL.md 를 읽고, 거기서 만든 PER·PBR 밴드 차트
(output/valuation_band/*.png·svg, 46종목)를 이 대시보드의 「📊 피어그룹.Valuation」 메뉴 밑에
"PE·PB 밴드" 항목으로 넣어줘. 기존 피어그룹.Valuation 메뉴의 다른 페이지들과 같은 구조·스타일로,
섹터(조선·방산·건설기계) 탭 + 종목 카드 그리드. 이미지 공급은 매뉴얼 8절의 A안(ecos 산출물을
가져오는 방식)으로 하고, 매일 갱신되게 기존 주보 갱신 흐름에 붙여줘.
```

# ecos-fx-rates

업무 자동화용 엑셀 파이프라인 모음. Actions에서 한 번 돌리면 결과 엑셀이
`output/`에 커밋되어 GitHub에서 바로 내려받을 수 있다.

| 파이프라인 | 실행 | 다운로드 |
| --- | --- | --- |
| ECOS 환율 | Actions → "ECOS 환율 엑셀" | [output/BOK_exchange_rates.xlsx](output/BOK_exchange_rates.xlsx) |
| 피어그룹 주가 | 매일 07:10 KST 자동 + Actions → "피어그룹 주가 엑셀" | [output/글로벌_주가_변동률_모니터링_최종.xlsx](output/글로벌_주가_변동률_모니터링_최종.xlsx) |
| 피어그룹 주가 흐름·조선주 INDEX(이미지) | 위 워크플로가 같이 생성 | [output/peer_price/](output/peer_price/) |
| 커버리지 컨센서스 추이(이미지) | Actions → "커버리지 컨센서스 추이 이미지" | [output/consensus/](output/consensus/) |
| PER·PBR 밴드 차트(이미지) | 피어그룹 주가 뒤 자동(평일 16:44 KST~) + 17:30 안전망 + Actions → "PER·PBR 밴드 차트" | [output/valuation_band/](output/valuation_band/) |
| 조선·방산·건설기계 Earnings Revision 적재 | 평일 16:44 KST 자동(Claude 예약) + Actions → "조선·방산·건설기계 Earnings Revision 적재" | [output/earnings_revision/](output/earnings_revision/) |

## ECOS 환율

ECOS(한국은행 경제통계시스템) 주요국 환율(통계코드 731Y001)을 받아
`output/BOK_exchange_rates.xlsx`를 자동 생성하는 파이프라인.

- **통화**: 원/달러 · 원/엔(100엔) · 원/유로 · 원/중국위안 (2005년~현재, 매매기준율)
- **시트**: Daily / Monthly / Quarterly / Annual / Pivot Wide (기간별 평균·기말)
- **Daily는 월~금 연속**: 공휴일 칸은 직전 영업일 값으로 채운다(VLOOKUP이 어떤 평일에도
  걸리도록). 채운 값도 평균에 들어가므로, 고시일만으로 계산하려면 `run_fx.py` 의
  `FILL_WEEKDAYS = False` 로 바꾸면 된다. 마지막 고시일 뒤는 채우지 않는다.
- **Pivot Wide**: `PIVOT_COLLAPSE_BEFORE`(기본 1Q25) 이전 열은 접힌 채로 저장된다
- **실행**: 수동 전용 — Actions → "ECOS 환율 엑셀" → Run workflow (`.github/workflows/fx-ecos.yml`)
- **다운로드**: [output/BOK_exchange_rates.xlsx](output/BOK_exchange_rates.xlsx)

## 피어그룹 주가

야후파이낸스에서 조선·해운·건설기계·방산 피어그룹 주가를 받아
`output/글로벌_주가_변동률_모니터링_최종.xlsx`를 생성한다.

- **시트**: 주가데이터 / 1년 INDEX / 그룹 평균 INDEX(차트 포함) / 변동률 대시보드
- **실행**: 매일 07:10 KST 자동(`schedule`) + 수동 Actions → "피어그룹 주가 엑셀" → Run workflow (`.github/workflows/peergroup-price.yml`). 같은 run이 아래 이미지 2종도 만든다
- **다운로드**: [output/글로벌_주가_변동률_모니터링_최종.xlsx](output/글로벌_주가_변동률_모니터링_최종.xlsx)
- 원래 GS-output-dashboard에서 아티팩트(zip)로만 받을 수 있었으나, 환율과 같이
  결과 엑셀을 저장소에 커밋하도록 옮겼다 (`peergroup/weekly_peergroup_price.py`).

## 피어그룹 주가 흐름 (이미지)

위클리에 그대로 붙여넣는 PNG. 섹션(지수·조선사·엔진/부품·오일/해양·해운)별 표에
1W/1M/3M/YTD/1Y 등락률 막대 + 최근 3개월 주가 스파크라인을 그린다.

- **출력**: `output/peer_price/글로벌_피어그룹_주가흐름.png`(전체 1페이지) + 2페이지 분할본(`_p1_조선`·`_p2_오일해운`) + 섹션별(`01_…`). 전부 **PNG와 SVG** 두 벌 — 엑셀·PPT에는 SVG를 `삽입 → 그림 → 이 디바이스`로 넣으면 확대해도 선명하다(복사·붙여넣기는 비트맵이 되어 흐려짐)
- **종목 수정**: `peergroup/weekly_peer_price_image.py` 상단 `SHIP_SECTIONS` / `DEFENSE_SECTIONS` / `CONSTRUCTION_SECTIONS` (그룹 라벨·표시명·야후 티커)
- **방산·건설기계판**(같은 그림, `--universe defense|construction`): `output/peer_price_defense/글로벌_방산_주가흐름.png`
  (지수·ETF / 한국 체계·탄약/기동·부체계·항공부품·우주 / 글로벌 우주·위성(발사체·위성통신·관측·부품·일본) / 미국 / 유럽 / 기타(중동·인도·일본·중국·남미), 분할 p1 한국·우주 · p2 미국·유럽·기타)
  + `output/peer_price_construction/글로벌_건설기계_주가흐름.png`(지수·원자재 / OEM 지역별 / 농기계·광산·렌탈·딜러 / 부품,
  분할 p1 OEM · p2 수요·부품). 섹션별 PNG 는 `01_…`~`05_…`. 같은 워크플로가 세 판을 모두 만든다
- **기간 기준**: 거래일 오프셋 `TRADING_DAYS`(1W=5·1M=21·3M=63·1Y=252), 스파크라인 `SPARK_DAYS`(63=3M, 126=6M)
- **실행**: "피어그룹 주가 엑셀" 워크플로에 통합(매일 07:10 KST + 수동). 대시보드 갤러리 페이지의 🔄 지금 갱신 버튼도 같은 워크플로를 쏜다
- **레이아웃 확인만**: `python peergroup/weekly_peer_price_image.py --demo` (가짜 데이터)
- **조선주 INDEX 차트 4종**(`peergroup/weekly_peer_index_image.py`, 같은 워크플로): ① KOSPI vs 한국 조선주 ② 한국 조선 7사
  Performance ③ 한/중/일/싱 조선주 비교 ④ 조선 5사 vs 엔진 vs 조선기자재 — 12주 전=100, 국가·밸류체인 지수는 기준일 USD 시총 가중.
  출력 `output/peer_price/조선주_INDEX_4종.png`(2×2 묶음, 각주는 맨 아래) + 낱장 `IDX1~4_*.png`(각각 .svg 동반)
  구성은 스크립트 상단 `KR_SHIP`·`GROUPS`·`CHAIN`.
- **방산 INDEX 차트 4종**(`peergroup/weekly_defense_index_image.py`, 같은 워크플로, 조선판 틀 재사용): ① 한국 방산 체계 5사
  Performance ② 한국 방산 부체계(부품) 11사 Performance ③ 한국 체계·부체계 vs 미국 체계 vs 유럽 체계(시총가중)
  ④ 드론 vs 엔진/부품 vs 항공 vs 우주(글로벌, 시총가중). 출력 `output/peer_price_defense/방산_INDEX_4종.png` + 낱장 `DIDX1~4_*`.
  구성은 `KR_PRIME`·`KR_SUB`·`GROUPS`·`THEMES`.
- **건설기계 INDEX 차트 4종**(`peergroup/weekly_construction_index_image.py`, 같은 워크플로): ① HD건설기계·두산밥캣·
  한국 부품사(시총가중) ② 한국 2사 vs 미국·중국·일본 피어(시총가중) ③ 대형 OEM 8(HD건기·CAT·Komatsu·Hitachi CM·SANY·XCMG·
  Zoomlion·LiuGong — 중국은 SANY 빼고 점선) ④ 두산밥캣·Deere·CNH·Kobelco(Kobe Steel)·대동. 출력
  `output/peer_price_construction/건설기계_INDEX_4종.png` + 낱장 `CIDX1~4_*`.

## 커버리지 컨센서스 추이 (이미지)

위클리용 PNG. 조선·조기·방산·건기 16종목의 **최근 6개월** 영업이익 컨센서스(평균) 추이를
종목별 작은 차트로 그린다. KOSPI200 컨센 트래커와 같은 FnGuide 컨센서스를 과거 시계열로 직접 받는다.

- **소스**: FnGuide `getCnsTrendChart`(월말, 약 1년) + 네이버 WiseReport `cF5002`(분기 = 주간 13개 시점,
  연간 = 월말 13개 시점). 겹치는 구간은 네이버 값, 그 이전은 FnGuide 월말 값으로 잇는다
- **출력**: `output/consensus/컨센서스_추이_분기.png/.svg/.csv`(다음 2개 분기, 예: 4Q26·1Q27) +
  `컨센서스_추이_연간.png/.svg/.csv`(올해E·내년E)
- **종목·순서·섹터**: `consensus/weekly_consensus_chart.py` 상단 `COMPANIES` (섹터, 표시명, 종목코드)
- **옵션**: `--months 12`(기간), `--since 2026-05-01`, `--mode quarter --periods 2026.12,2027.03`
- **실행**: Actions → "커버리지 컨센서스 추이 이미지" (`.github/workflows/consensus-chart.yml`)

## PER·PBR 밴드 차트 (이미지)

조선·방산·건설기계 46종목(ER 적재 종목과 동일, `consensus/er_snapshot.py` 의 `COMPANIES`)의 PER 밴드 + PBR 밴드(ROE 음영) 그림.
한국은 원화(천원), 해외는 USD.

- **DB**(`data/valuation/`) — ⚠️ DataGuide·Bloomberg 값과 자체 추정치가 들어 있으니 저장소는 비공개로 둘 것
  - `raw/` : 업로드한 밴드 엑셀 원본. 파일명 `DG_<이름>_YYYYMMDD.xlsx`(DataGuide) / `BB_<이름>_YYYYMMDD.xlsx`(Bloomberg).
    새 파일을 넣고 푸시하면 워크플로가 바로 다시 만든다(같은 종목·연도는 날짜가 최신인 파일이 이김)
  - `annual_uploads.csv` : 연간 EPS·BPS·ROE (basis = actual 실적 / model ☞추정입력 / consensus 컨센) ← `valuation/ingest_uploads.py`
  - `annual_yahoo.csv` : Yahoo 실적(약 4년)·FY1·FY2 컨센 EPS. 해외는 USD 환산(실적=결산일 환율, 컨센=오늘 환율) ← `valuation/yahoo_fundamentals.py`
  - `multiples.csv` : 엑셀에서 쓰던 밴드 배수(PER·PBR 5개씩). 없는 종목은 과거 배수 분포(5·25·50·75·95%)로 자동
  - `prices_uploads.csv` : 한국 일간 수정주가(DataGuide). 그 뒤는 Yahoo 로 이어 붙인다
- **연도별 값 우선순위**: 내 모델 → 업로드 band → 업로드 model → 업로드 actual → 업로드 consensus → Yahoo actual → Yahoo consensus.
  미래 BPS 가 없으면 `BPS(t−1) + EPS(t)×(1−배당성향)`. 실제로 쓴 값·출처는 `output/valuation_band/band_inputs.csv`
- **밴드 선**: 그해 EPS(BPS)×배수, 1~3월에 걸쳐 전년 값에서 넘어가는 계단(엑셀 '계단' 열과 같은 방식). 2019년~올해+2(FY3)
- **그림**: 종목당 2장 — `<섹터>_<종목>_PER` · `_PBR`(.png/.svg). 왼쪽 위에 `종가 날짜 값` 딱지
- **✏️ 내 모델**: 대시보드에서 올해~올해+4 EPS·BPS·ROE 를 붙여넣으면 `valuation-model.yml` 이 `data/valuation/my_model/<티커>.csv`
  로 저장하고 밴드를 다시 그린다. 우선순위 내 모델 → 업로드 엑셀 모델 → 컨센서스 (`valuation/set_model.py`)
- **Yahoo 만 있는 종목**(해외 방산 15·해외 조선 3·Kobelco·Volvo)은 2022년부터, FY2(내년)까지만 그려진다
- **실행**: `.github/workflows/valuation-band.yml` — **피어그룹 주가 워크플로가 끝나면 이어서**(평일 16:44 KST 정시 예약이 피어그룹을 쏘면 밴드도 따라 돈다) + 평일 17:30 KST 크론(안전망) + 수동 + `data/valuation/raw/` 푸시 시.
  로컬: `python valuation/band_chart.py --only 079550.KS,CAT`

## 조선·방산·건설기계 Earnings Revision 적재

Bloomberg ER 차트를 무료 데이터로 흉내 내기 위해 Yahoo Finance 애널리스트 추정치를 **매일 한 번** 받아 쌓는다.
Yahoo 는 그날 시점 값만 주므로 과거 이력은 없고, 적재를 시작한 날(2026-11-10)부터 시계열이 생긴다.

- **종목**: CAT·Deere·CNH·URI / Komatsu·Hitachi CM·Kubota·Kobelco(=Kobe Steel 5406.T, 코벨코건기는 비상장)·Takeuchi /
  Volvo / SANY·XCMG
- **조선 종목**: 한국 커버리지 9(HD한국조선해양·HD현대중공업·HD현대마린엔진·HD현대마린솔루션·삼성중공업·한화오션·한화엔진·
  대한조선·한국카본) + Yangzijiang(BS6.SI)·CSSC(600150.SS)·Seatrium(5E2.SI)
- **한국 커버리지**: 방산 5(한화에어로·한화시스템·KAI·LIG D&A·현대로템), 건기 2(두산밥캣·HD건설기계)도 각 섹터에 포함.
  야후의 한국 종목 애널리스트 수는 실제보다 적게 잡히는 경우가 많다(두산밥캣 2·HD건설기계 3·한화시스템 4 등)
- **방산 종목**(방산 INDEX ③ 과 동일): 미국 체계 LMT·RTX·NOC·GD·LHX·BA·HII / 유럽 체계 Rheinmetall·BAE·Thales·Leonardo·
  Saab·Hensoldt·Renk·Kongsberg. 종목 수정은 `consensus/er_snapshot.py` 상단 `_KR_*`·`_SHIP`·`_DEF`·`_CON`, 결과는 `sector` 열로 구분
- **ER30** = (30일 EPS 상향 건수 − 하향 건수) / 애널리스트 수 × 100. 7일 기준 `er7` 도 같이 저장
- **EPS 1M·3M 변화율**: 컨센 EPS 현재 vs 30·90일 전(Yahoo 제공) — 이력이 없어도 첫날부터 볼 수 있는 보조 지표
- **출력**: `output/earnings_revision/er_history.csv`(누적, 키 = date·ticker·period, period 0y=FY1·+1y=FY2·0q/+1q=분기),
  `er_latest.csv`(오늘 요약)
- **주의**: 커버리지가 적은 종목(SANY·XCMG·Takeuchi 등 4~6명)은 1~2건 변경으로 ER이 크게 튄다. Yahoo 의 건수·애널리스트
  수는 Bloomberg 집계와 다르다. 하루 빠지면 그날 값은 복구할 수 없다
- **실행**: `.github/workflows/earnings-revision.yml` — 평일 16:44 KST Claude 예약 작업이 dispatch(정시, 피어그룹·컨센서스와 함께), 크론 17:20 평일은 안전망 + 수동
- **화면**: GS-DB2 대시보드 보고서.발간 › 주보 › 📐 ER › 조선/방산/건설기계 (`er_report.html?s=…`, 이 CSV 를 raw 로 읽음)

## 내력

원래 Google Apps Script(`ECOS 환율` 프로젝트)로 돌았으나, ECOS가 Google
데이터센터 IP 대역을 차단하면서 `UrlFetchApp`이 "Address unavailable"로
실패하게 되어 2026-07 GitHub Actions + Python으로 이전했다.
GS-output-dashboard 저장소의 `fx_ecos/` 모듈을 거쳐 별도 저장소로 분리.

## 설정

- 저장소 시크릿 `ECOS_API_KEY` 필요 (ECOS 오픈API 인증키, https://ecos.bok.or.kr 에서 무료 발급)

## 로컬 실행

```bash
pip install -r requirements.txt
ECOS_API_KEY=<키> python run_fx.py

pip install -r peergroup/requirements.txt
python peergroup/weekly_peergroup_price.py
```

# ecos-fx-rates

업무 자동화용 엑셀 파이프라인 모음. Actions에서 한 번 돌리면 결과 엑셀이
`output/`에 커밋되어 GitHub에서 바로 내려받을 수 있다.

| 파이프라인 | 실행 | 다운로드 |
| --- | --- | --- |
| ECOS 환율 | Actions → "ECOS 환율 엑셀" | [output/BOK_exchange_rates.xlsx](output/BOK_exchange_rates.xlsx) |
| 피어그룹 주가 | 매일 07:10 KST 자동 + Actions → "피어그룹 주가 엑셀" | [output/글로벌_주가_변동률_모니터링_최종.xlsx](output/글로벌_주가_변동률_모니터링_최종.xlsx) |
| 피어그룹 주가 흐름·조선주 INDEX(이미지) | 위 워크플로가 같이 생성 | [output/peer_price/](output/peer_price/) |
| 커버리지 컨센서스 추이(이미지) | Actions → "커버리지 컨센서스 추이 이미지" | [output/consensus/](output/consensus/) |

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
- **종목 수정**: `peergroup/weekly_peer_price_image.py` 상단 `SECTIONS` (그룹 라벨·표시명·야후 티커)
- **기간 기준**: 거래일 오프셋 `TRADING_DAYS`(1W=5·1M=21·3M=63·1Y=252), 스파크라인 `SPARK_DAYS`(63=3M, 126=6M)
- **실행**: "피어그룹 주가 엑셀" 워크플로에 통합(매일 07:10 KST + 수동). 대시보드 갤러리 페이지의 🔄 지금 갱신 버튼도 같은 워크플로를 쏜다
- **레이아웃 확인만**: `python peergroup/weekly_peer_price_image.py --demo` (가짜 데이터)
- **조선주 INDEX 차트 3종**(`peergroup/weekly_peer_index_image.py`, 같은 워크플로): ① KOSPI vs 한국 조선주 ② 한국 조선 7사
  Performance ③ 한/중/일/싱 조선주 비교 — 12주 전=100, 국가 지수는 기준일 USD 시총 가중. 출력 `output/peer_price/조선주_INDEX_3종.png`
  (2×2 묶음) + 낱장 `IDX1_…`·`IDX2_…`·`IDX3_…` (PNG+SVG). 구성은 스크립트 상단 `KR_SHIP`·`GROUPS`.

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

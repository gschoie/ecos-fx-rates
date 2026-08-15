# ecos-fx-rates

업무 자동화용 엑셀 파이프라인 모음. Actions에서 한 번 돌리면 결과 엑셀이
`output/`에 커밋되어 GitHub에서 바로 내려받을 수 있다.

| 파이프라인 | 실행 | 다운로드 |
| --- | --- | --- |
| ECOS 환율 | Actions → "ECOS 환율 엑셀" | [output/BOK_exchange_rates.xlsx](output/BOK_exchange_rates.xlsx) |
| 피어그룹 주가 | Actions → "피어그룹 주가 엑셀" | [output/글로벌_주가_변동률_모니터링_최종.xlsx](output/글로벌_주가_변동률_모니터링_최종.xlsx) |

## ECOS 환율

ECOS(한국은행 경제통계시스템) 주요국 환율(통계코드 731Y001)을 받아
`output/BOK_exchange_rates.xlsx`를 자동 생성하는 파이프라인.

- **통화**: 원/달러 · 원/엔(100엔) · 원/유로 · 원/중국위안 (2005년~현재, 매매기준율)
- **시트**: Daily / Monthly / Quarterly / Annual / Pivot Wide (기간별 평균·기말)
- **실행**: 수동 전용 — Actions → "ECOS 환율 엑셀" → Run workflow (`.github/workflows/fx-ecos.yml`)
- **다운로드**: [output/BOK_exchange_rates.xlsx](output/BOK_exchange_rates.xlsx)

## 피어그룹 주가

야후파이낸스에서 조선·해운·건설기계·방산 피어그룹 주가를 받아
`output/글로벌_주가_변동률_모니터링_최종.xlsx`를 생성한다.

- **시트**: 주가데이터 / 1년 INDEX / 그룹 평균 INDEX(차트 포함) / 변동률 대시보드
- **실행**: 수동 전용 — Actions → "피어그룹 주가 엑셀" → Run workflow (`.github/workflows/peergroup-price.yml`)
- **다운로드**: [output/글로벌_주가_변동률_모니터링_최종.xlsx](output/글로벌_주가_변동률_모니터링_최종.xlsx)
- 원래 GS-output-dashboard에서 아티팩트(zip)로만 받을 수 있었으나, 환율과 같이
  결과 엑셀을 저장소에 커밋하도록 옮겼다 (`peergroup/weekly_peergroup_price.py`).

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

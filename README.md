# ecos-fx-rates

ECOS(한국은행 경제통계시스템) 주요국 환율(통계코드 731Y001)을 받아
`output/BOK_exchange_rates.xlsx`를 자동 생성하는 파이프라인.

- **통화**: 원/달러 · 원/엔(100엔) · 원/유로 · 원/중국위안 (2005년~현재, 매매기준율)
- **시트**: Daily / Monthly / Quarterly / Annual / Pivot Wide (기간별 평균·기말)
- **스케줄**: GitHub Actions, 매 평일 17:30 KST (`.github/workflows/fx-ecos.yml`)
- **수동 실행**: Actions → "ECOS 환율 엑셀" → Run workflow
- **다운로드**: [output/BOK_exchange_rates.xlsx](output/BOK_exchange_rates.xlsx)

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
```

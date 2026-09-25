# Phase 1 data quality report

Listing date: 20260925. Financials: FY2025 annual report (DART).

## Rows at each filter step

| Step | Rows |
|---|---|
| KOSPI listing (FinanceDataReader) | 942 |
| Common stocks only (code ends in 0) | 831 |
| Drop SPACs | 831 |
| Drop REITs | 808 |
| Drop listed infrastructure funds | 806 |
| Market cap >= KRW 500bn | 296 |
| DART FY financials available | 292 |
| Financials reported in KRW | 291 |
| Drop EPS <= 0 or BPS <= 0 | 252 |

## Dropped by name rule

- SPAC (0): none
- REIT (23): SK리츠, 롯데리츠, 한화리츠, ESR켄달스퀘어리츠, 신한알파리츠, 삼성FN리츠, 코람코라이프인프라리츠, 이지스밸류플러스리츠, KB스타리츠, 신한서부티엔디리츠, 제이알글로벌리츠, 대신밸류리츠, 이리츠코크렙, 디앤디플랫폼리츠, NH올원리츠, 이지스레지던스리츠, 코람코더원리츠, NH프라임리츠, 미래에셋글로벌리츠, 미래에셋맵스리츠, 신한글로벌액티브리츠, 케이탑리츠, 마스턴프리미어리츠
- Infrastructure fund (2): 맥쿼리인프라, KB발해인프라

## Missing values in pulled DART data (before profitability filter)

| Field | Missing |
|---|---|
| corp_code | 0 |
| induty_code | 0 |
| fs_div | 2 |
| net_income_parent | 4 |
| equity_parent | 2 |
| dps_common | 2 |
| payout_reported_pct | 18 |

## Companies without usable FY financials (excluded)

- 003530 한화투자증권 (fs_div: CFS)
- 094800 맵스리얼티 (fs_div: None)
- 0220W0 한화머시너리앤서비스홀딩스 (fs_div: None)
- 001270 부국증권 (fs_div: CFS)

## Financials not in KRW (excluded, no FX conversion)

- 241560 두산밥캣 (USD)

## Non-December fiscal year (kept, flagged)

- 001720 신영증권 (fiscal month 03)

## Final universe composition

- Total: 252
- Financials: 36, non-financials: 216
- Filed a Value-Up plan: 173
- Consolidated (CFS): 245, separate (OFS): 7

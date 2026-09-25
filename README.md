# Korea Value-Up Re-rating Screen

Which KOSPI companies still trade below the P/B their ROE justifies, after Korea's governance
reforms (the Value-Up Program from February 2024, Commercial Act amendments from July 2025 and
the dividend tax changes of January 2026)?

This repo screens the KOSPI with public data, tests how the market reacted to Value-Up plan
disclosures, and (in progress) values one company in a sell-side style initiation note.

**Status:** screen and event study complete. Company valuation (Excel 3-statement model, DCF,
trading comps) and the initiation note are in progress.

## Key findings so far

- **ROE explains about half of valuation.** Across 214 KOSPI non-financials, log(P/B) on ROE
  with sector fixed effects gives R-squared 0.53. One extra point of ROE goes with about 6%
  higher P/B within a sector.
- **The discount is concentrated, not universal.** 32% of companies trade below a textbook
  justified P/B at a 9.2% cost of equity. Materials, utilities and telecom, transport and autos
  trade 45% to 57% below the P/B their ROE implies. Holding companies sit about 30% below.
- **Filing a Value-Up plan did not move prices.** Across 169 first plan disclosures, the mean
  7-day cumulative abnormal return is +0.24% (t = 0.41). No subgroup is significant.
- **22 candidates** trade in the bottom quartile of the ROE-adjusted residual with above-median
  ROE and below-median payout, meaning room to raise shareholder returns.

![P/B vs ROE](outputs/charts/pb_vs_roe.png)

![Sector discount](outputs/charts/residual_by_sector.png)

![Event study](outputs/charts/event_study_car.png)

Full write-up with interpretation and limitations: [outputs/phase1_3_summary.md](outputs/phase1_3_summary.md).

## Method

| Step | Script | What it does |
|---|---|---|
| Universe | `src/build_universe.py` | KOSPI common stocks, excluding REITs and infrastructure funds, market cap of at least KRW 500bn, positive EPS and BPS. Pulls FY2025 financials, dividends and Value-Up filings from DART. |
| Screen | `src/screen.py` | OLS of log(P/B) on winsorized ROE with sector fixed effects and HC3 robust SEs. The residual is the discount to ROE-justified P/B. Cross-checked against justified P/B = (ROE - g) / (COE - g). |
| Event study | `src/event_study.py` | Market-model CAR over [-1, +5] around each company's first Value-Up plan, estimated on [-250, -30] against KOSPI. |

Definitions:
- P/B = (common + preferred market cap) / parent equity
- ROE = parent net income / parent equity (FY2025)
- Payout = DPS / EPS, both from the DART dividend table

Every step's row counts, exclusions and missing values are logged in
[outputs/data_quality_report.md](outputs/data_quality_report.md).

## Data sources

- [DART OpenAPI](https://opendart.fss.or.kr) via OpenDartReader: financial statements, dividends,
  exchange disclosures, industry codes
- FinanceDataReader: KOSPI listing, market cap, daily prices, KOSPI index
- FRED series IRLTLT01KRM156N: Korea 10-year government bond yield
- Damodaran, Country Risk Premiums, January 2026 update: Korea equity risk premium

## Reproduce

Requires Python 3.12 and a free DART API key.

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # then add your DART_API_KEY
.venv/bin/python src/build_universe.py
.venv/bin/python src/screen.py
.venv/bin/python src/event_study.py
```

Run the scripts from the repo root. Raw API responses are cached in `data/raw/` (not committed),
so reruns do not call the APIs again.

## Limitations

- One fiscal year of ROE. Cyclical companies at peak earnings can look cheap on this screen.
- Treasury shares are included in market cap, which slightly overstates P/B for companies with
  large buybacks held in treasury.
- The event study's first plan dates cluster (59 in March 2026), which overstates the precision
  of the t-statistic.

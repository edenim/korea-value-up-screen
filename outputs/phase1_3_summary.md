# Phases 1 to 3: summary

Data as of 25 Sep 2026 (prices) and FY2025 annual reports (financials). All numbers below are
produced by `src/build_universe.py`, `src/screen.py` and `src/event_study.py`.

## Phase 1: universe and data

| Step | Companies |
|---|---|
| KOSPI listing | 942 |
| Common stocks only | 831 |
| Drop REITs (23) and listed infrastructure funds (2) | 806 |
| Market cap >= KRW 500bn (common + preferred) | 296 |
| FY2025 financials available on DART | 292 |
| Financials reported in KRW (drops Doosan Bobcat, USD filer) | 291 |
| Positive EPS and BPS | 252 |

Of the 252, 36 are financials (banks, insurers, securities, cards, financial holding companies)
and 216 are non-financials. 173 filed a Value-Up plan between May 2024 and Sep 2026.
Full detail, including every excluded company and why, is in `outputs/data_quality_report.md`.

Data handling choices:
- P/B and ROE are computed from DART statements (parent net income and parent equity), not
  taken from KRX. When a filer tags these lines differently, an exact identity of reported
  figures is used (for example parent equity = total equity minus non-controlling interests),
  and the rule applied is recorded per company in `fin_rule`.
- Payout = FY2025 DPS / FY2025 consolidated EPS from the DART dividend table. It matches DART's
  own reported payout ratio with a median absolute gap of 0.0pp.
- The Value-Up flag counts only actual plans. Preview notices (예고) are stored separately.

## Phase 2: ROE-justified P/B screen

Model: log(P/B) on ROE (winsorized 1/99) with 16 sector fixed effects, HC3 robust SEs,
214 non-financials.

| Result | Value |
|---|---|
| ROE coefficient | 6.00 (robust SE 0.83, p < 0.001) |
| R-squared | 0.53 |
| Median P/B, median ROE | 1.29x, 8.0% |
| Rank correlation with justified P/B gap | 0.65 |
| Share trading below justified P/B | 32% |
| Candidates (bottom-quartile residual, ROE > median, payout < median) | 22, of which 8 filed a Value-Up plan |

Justified P/B = (ROE - g) / (COE - g), with COE = 4.29% (Korea 10Y yield, Aug 2026, FRED)
+ 1.0 x 4.87% (Korea total ERP, Damodaran Jan 2026) = 9.16%, and g = 2.0% (Bank of Korea
inflation target).

**Interpretation.** Profitability explains about half of the variation in valuation across
KOSPI non-financials. Each extra percentage point of ROE goes with roughly 6% higher P/B within
the same sector. The regression and the textbook justified P/B formula broadly agree on which
stocks look cheap (rank correlation 0.65), which gives some confidence that the residual is
picking up valuation rather than noise. Only about a third of companies trade below their
justified P/B at a 9.2% cost of equity, so the "Korea discount" is concentrated rather than
universal.

**Sector view (ROE-only model, chart `residual_by_sector.png`).** Materials (-57% median),
utilities and telecom (-54%), transport, consumer discretionary and autos (about -45%) trade
well below the P/B their ROE implies. Industrials and tech hardware trade about 120% above it,
driven by shipbuilding, defense, power equipment and semiconductor names where investors pay
for expected growth beyond current ROE. Holding companies sit at -30%, consistent with the
holding company discount the governance reforms target.

**Value-Up filers vs non-filers (non-financials, 146 vs 68).** Filers have lower median P/B (1.15x vs 1.55x), lower ROE
(7.3% vs 9.9%) and much higher payout (33% vs 8%). Their median residual (-0.03) is close to
non-filers' (-0.05), so filing a plan has not, on its own, closed the ROE-adjusted gap.

**Candidate caveats.** The screen is mechanical and some names need judgment before valuation:
- Peak-cycle ROE: shipbuilding and marine engines (Daehan Shipbuilding, HD Hyundai Marine
  Engine, STX Engine, Sejin Heavy) sit below the line partly because a log-linear model
  extrapolates very high P/B from very high ROE.
- ROE jumps that may be one-off: KCC (6.5% to 19.7%), Daewoong Pharmaceutical (3.1% to 19.5%),
  Hankuk Carbon (4.3% to 17.5%), Dongwon Industries (2.7% to 10.4%).
- Regulated or restructuring: KEPCO and Korea District Heating (tariff-regulated), Taeyoung
  Engineering and Construction (post-workout).

## Phase 3: event study

CAR over [-1, +5] around each company's first Value-Up plan, market model vs KOSPI, estimation
window [-250, -30].

| Group | N | Mean CAR | Median CAR | t-stat | Share positive |
|---|---|---|---|---|---|
| All | 169 | +0.24% | -0.48% | 0.41 | 47% |
| Non-financials | 144 | +0.14% | -1.44% | 0.22 | 44% |
| Financials | 25 | +0.80% | +1.03% | 0.83 | 64% |
| First filed 2024 to 2025 | 99 | +0.20% | -0.10% | 0.28 | 48% |
| First filed 2026 | 70 | +0.30% | -1.71% | 0.31 | 46% |

**Interpretation.** On average the market did not react to a company's first Value-Up plan.
None of the groups is statistically different from zero. A plausible reading is that the plans
were widely anticipated once the program was announced in February 2024, so prices moved at the
policy level rather than on each company's filing. Financials show the most positive (but still
insignificant) reaction, in line with banks' plans containing concrete payout targets.

**Limitations.**
- Event clustering: 59 first filings fall in March 2026 and 52 in Oct to Dec 2024. Same-date
  events share market shocks, so the cross-sectional t-stat overstates precision. It is still
  insignificant.
- Four recent IPOs were dropped for lacking 250 days of history.
- The event date is the DART receipt date. Filings after the close are captured by the [-1, +5]
  window, but intraday timing is not modeled.
- A 7-day window cannot capture a slow re-rating that happens as plans are executed.

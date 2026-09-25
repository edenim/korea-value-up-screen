# Kyung Dong Navien (009450): DCF assumptions

Status: CONFIRMED by the analyst on 2026-09-25 and implemented in `model/Navien_009450_model.xlsx`.
Implementation notes: market cap uses shares outstanding (ex treasury), KRW 870.1bn, so D/E is 0.412 and
WACC is 7.90%. The tax rate on EBIT is the exact average of the two applicable-rate ratios, 29.9%.
All KRW figures in billions unless noted.
Every historical number comes from DART (consolidated statements, notes, filings) cached in
`data/raw/dart/`. Market inputs come from files cached in `data/raw/reference/`.

## Facts the assumptions rest on

| Item | FY2023 | FY2024 | FY2025 | 1H2025 | 1H2026 | Source |
|---|---|---|---|---|---|---|
| Revenue | 1,204.3 | 1,353.9 | 1,502.2 | 757.5 | 813.5 | DART CFS |
| North America | 660.9 | 774.9 | 865.8 | 471.6 | 505.0 | Notes, geographic disclosure |
| Korea | 389.7 | 411.5 | 458.4 | 228.8 | 228.6 | same |
| Russia | 79.9 | 78.7 | 80.0 | 28.8 | 35.3 | same |
| China | 30.9 | 30.7 | 23.9 | 6.7 | 7.9 | same |
| Other overseas | 42.9 | 58.0 | 74.1 | 21.6 | 36.7 | same |
| Operating profit | 105.9 | 132.6 | 143.4 | 90.6 | 148.1 | DART CFS |
| Operating margin | 8.8% | 9.8% | 9.5% | 12.0% | 18.2% | computed |
| D&A | n/a | 47.4 | 52.8 | 25.8 | 27.3 | Notes, expenses by nature |
| Capex (PP&E + intangibles) | 65.6 | 111.3 | 162.2 | n/a | 66.2 | DART cash flow |
| Net working capital (AR + inventory - AP - contract liabilities) | 227.2 | 355.5 | 415.8 | | | DART BS |
| Effective tax rate | 22.5% | 18.6% | 40.5% | | | DART CFS |
| Tax at applicable rate / pre-tax income | | 30.4% | 29.3% | | | Notes, tax reconciliation |

Other facts:
- 1H2026 cost of sales includes US tariff refunds (notes, expenses by nature). The amount is
  NOT disclosed, so 1H2026 margins cannot be normalized precisely.
- Commax (81%) consolidated from 1 Jan 2026. Consideration KRW 31.7bn. FY2025 Commax revenue
  85.1bn with an operating loss of 14.2bn (Commax's own DART filing).
- Seotan plant expansion, KRW 104.3bn, Jul 2024 to Jul 2026, completed (DART filing 2026-07-23).
- Q2 2026 revenue -1.0% YoY, operating profit +64.6% YoY (preliminary results, 2026-08-11).
- FY2025 swing in tax: deferred tax expense of 14.0bn vs a 32.3bn benefit in FY2024.
- Shares outstanding 14,452,932 (14,568,592 listed less 115,660 treasury). Price KRW 60,200
  on 25 Sep 2026. Market cap KRW 877.0bn.
- Debt at 30 Jun 2026: short-term 276.1, long-term 68.8, leases 13.9, total 358.8. Cash and
  deposits 158.8. Net debt 200.0. Non-controlling interests 7.6.

## Proposed assumptions

### Revenue (by region)

| Region | FY26E | FY27E | FY28E | FY29E | FY30E | Rationale |
|---|---|---|---|---|---|---|
| North America | +7% | +7% | +6% | +5% | +4% | 1H26 actual +7.1%. Growth slowing from +17.2% (FY24) and +11.7% (FY25). New Seotan capacity supports continued growth. Taper toward terminal growth. |
| Korea (incl. Commax) | 0% | +3% | +3% | +3% | +3% | 1H26 flat even with Commax consolidated. Mature replacement market. |
| Russia | 0% | 0% | 0% | 0% | 0% | FY23 to FY25 CAGR +0.1%. Sanctions risk argues against extrapolating the 1H26 rebound. |
| China | -5% | -5% | -5% | -5% | -5% | FY23 to FY25 CAGR -12.1%, 1.6% of revenue. |
| Other overseas | +20% | +15% | +12% | +10% | +8% | FY23 to FY25 CAGR +31.4% from a small base, 1H26 +70%. |

### Margins, reinvestment, tax

| Assumption | Proposed | Rationale |
|---|---|---|
| Operating margin FY26E | 1H26 actual + 2H26 at 2H25 margin (7.1%) | Uses reported 1H26 as is (refund included, amount unknown), avoids extrapolating it. |
| Operating margin FY27E onward | 9.5% | FY23 to FY25 average (9.4%), range 8.8% to 9.8%. |
| D&A | 3.5% of revenue | FY24 and FY25 both 3.5%. |
| Capex FY26E | 7.0% of revenue | 1H26 actual 8.1%, expansion finished in Jul 2026. |
| Capex FY27E, FY28E onward | 5.0%, then 4.5% | Pre-expansion FY23 was 5.4%. Stays above D&A to fund growth. |
| Net working capital | 26% of revenue | FY24 26.3%, FY25 27.7%. FY23 (18.9%) predates the inventory build. |
| Tax rate on EBIT | 29.8% | Average of tax at applicable rates in FY24 (30.4%) and FY25 (29.3%). Excludes the deferred tax swings that made reported rates 18.6% and 40.5%. |

### Discount rate

| Input | Proposed | Source |
|---|---|---|
| Risk-free rate | 4.29% | Korea 10Y government bond yield, Aug 2026, FRED IRLTLT01KRM156N |
| Equity risk premium | 4.87% | Damodaran country risk premiums, Jan 2026, Korea total ERP |
| Unlevered beta | 0.86 | Damodaran global industry betas, Jan 2026, Building Materials (469 firms) |
| Debt / equity (market) | 0.41 | 358.8 / 877.0 |
| Marginal tax rate (debt shield, relevering) | 26.4% | Korea statutory rate including local tax, Damodaran country tax rates |
| Levered beta | 1.12 | 0.86 x (1 + (1 - 26.4%) x 0.41) |
| Cost of equity | 9.73% | 4.29% + 1.12 x 4.87% |
| Pre-tax cost of debt | 4.69% | Risk-free rate + 0.40% spread. Interest coverage 15.3x (FY25 EBIT / interest paid) maps to AAA in Damodaran's synthetic rating table for smaller firms. |
| WACC | 7.91% | 71% equity, 29% debt |
| Terminal growth | 2.0% | Bank of Korea inflation target. Below nominal GDP growth, so conservative. |

Why not the regression beta: Navien's weekly beta against KOSPI is 0.13 (2y) to 0.20 (3y)
with R-squared 0.01. The KOSPI is dominated by semiconductors, so the regression carries no
information about Navien's risk. A bottom-up industry beta is the standard fix.

Cross-check: Navien's own impairment test in the FY2025 notes uses a 10.58% discount rate for
a cash-generating unit (pre-tax basis, so not directly comparable).

### Mechanics

| Item | Proposed |
|---|---|
| Explicit forecast | FY2026E to FY2030E. FY2026E counts only 2H26 cash flow, since 1H26 is already in the 30 Jun 2026 balance sheet. |
| Discounting | Mid-period convention from 30 Jun 2026 |
| Bridge to equity | Enterprise value - net debt (200.0) - non-controlling interests (7.6) |
| Per share | Divide by 14,452,932 shares outstanding |
| Sensitivity | WACC (6.9% to 8.9%, 0.5pp steps) x terminal growth (1.0% to 3.0%, 0.5pp steps) |
| Trading comps | A. O. Smith (AOS), Rinnai (5947.T), Noritz (5943.T), Ariston (ARIS.MI), Lennox (LII), Coway (021240). EV/EBITDA and P/E from Yahoo Finance via yfinance, dated. Used as a cross-check, not blended into the target. |
| Rating rule | Overweight if upside > 15%, Neutral if -15% to +15%, Underweight if < -15% |

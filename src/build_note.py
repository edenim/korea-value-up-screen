"""Phase 5: build the initiation note (HTML -> PDF via headless Chrome).

Every number is read from pipeline outputs:
  outputs/model_values.json      (evaluated Excel model, see evaluate_model.py)
  outputs/screen_stats.json, outputs/event_study_stats.json, data/processed/screen_results.csv
  data/raw/prices/009450.csv     (52-week range)
Text that is not a number (business description) paraphrases the FY2025 DART annual report.

Run from the repo root:  .venv/bin/python src/build_note.py
"""

import json
import subprocess

import numpy as np
import pandas as pd

import charts
from config import OUTPUT_DIR, PROCESSED_DIR, RAW_DIR, ROOT

NOTE_DIR = ROOT / "note"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
REPORT_DATE = "25 September 2026"


def fmt_bn(v, d=1):
    return f"{v:,.{d}f}" if v >= 0 else f"({-v:,.{d}f})"


def pct(v, d=1):
    return f"{v * 100:.{d}f}%"


def load():
    mv = json.loads((OUTPUT_DIR / "model_values.json").read_text(encoding="utf-8"))
    screen = json.loads((OUTPUT_DIR / "screen_stats.json").read_text())
    event = json.loads((OUTPUT_DIR / "event_study_stats.json").read_text(encoding="utf-8"))
    results = pd.read_csv(PROCESSED_DIR / "screen_results.csv", dtype={"code": str})
    prices = pd.read_csv(RAW_DIR / "prices" / "009450.csv", index_col=0, parse_dates=True)["Close"]
    return mv, screen, event, results, prices


def sensitivity(dcf, marker):
    """Return (column headers, [(row header, values)]) for the grid that follows `marker`."""
    keys = list(dcf.keys())
    start = keys.index(marker)
    head = dcf[keys[start + 1]]
    cols = [head[k] for k in ["Value", "C", "D", "E", "F"]]
    rows = []
    for k in keys[start + 2: start + 7]:
        r = dcf[k]
        rows.append((r["A"], [r[c] for c in ["Value", "C", "D", "E", "F"]]))
    return cols, rows


def build():
    mv, screen, event, results, prices = load()
    H, M, D, C, I = mv["Historical"], mv["Model"], mv["DCF"], mv["Comps"], mv["Inputs"]

    price = I["Share price (KRW)"]["Value"]
    shares = I["Shares outstanding"]["Value"]
    value_ps = D["Equity value per share (KRW)"]["Value"]
    target = round(value_ps / 1000) * 1000  # target price rounded to the nearest KRW 1,000
    upside = target / price - 1
    band = I["Rating band (+/-)"]["Value"]
    rating = "Overweight" if upside > band else ("Underweight" if upside < -band else "Neutral")
    wacc = D["WACC"]["Value"]
    g = I["Terminal growth"]["Value"]
    mcap = D["Market cap"]["Value"]
    net_debt = D["Less: net debt, 30 Jun 2026"]["Value"]
    last_year = prices[prices.index >= prices.index[-1] - pd.Timedelta(days=365)]
    hi52, lo52 = last_year.max(), last_year.min()
    end_2024 = prices[prices.index <= "2024-12-31"].iloc[-1]

    # Navien's position in the screen
    nav = results[results["code"] == "009450"].iloc[0]
    nav_discount = np.exp(nav["residual"]) - 1
    payout_median = screen["payout_median"]

    # Historical facts
    op24, op25 = H["Operating profit"]["FY2024"], H["Operating profit"]["FY2025"]
    ni24, ni25 = H["Net income attributable to parent"]["FY2024"], H["Net income attributable to parent"]["FY2025"]
    etr24, etr25 = H["Effective tax rate"]["FY2024"], H["Effective tax rate"]["FY2025"]
    app25 = H["Tax at applicable rates / profit before tax"]["FY2025"]
    capex_pct25 = H["Capex / revenue"]["FY2025"]
    fcf25 = H["Cash flow from operations"]["FY2025"] - H["Total capex"]["FY2025"]
    na_share = H["Revenue: North America"]["FY2025"] / H["Total revenue"]["FY2025"]
    opm_1h25, opm_1h26 = H["Operating margin"]["1H2025"], H["Operating margin"]["1H2026"]
    growth_1h26 = H["Revenue growth"]["1H2026"]
    fcff = D["Free cash flow to firm"]
    fcff_vals = [fcff[k] for k in ["Value", "C", "D", "E", "F"]]
    eq_parent_jun = H["Equity attributable to parent"]["1H2026"]
    ebitda_ltm = C["EBITDA, LTM to 1H2026"]["Ticker"]
    ni_ltm = C["Net income to parent, LTM"]["Ticker"]

    # ---------------- charts ----------------
    NOTE_DIR.mkdir(exist_ok=True)
    img = NOTE_DIR / "img"
    img.mkdir(exist_ok=True)
    years = ["FY23A", "FY24A", "FY25A", "FY26E", "FY27E", "FY28E", "FY29E", "FY30E"]
    hist_cols = ["FY2023", "FY2024", "FY2025"]
    model_cols = ["FY2026E", "FY2027E", "FY2028E", "FY2029E", "FY2030E"]
    regions = {"North America": "Revenue: North America", "Korea": "Revenue: Korea", "Russia": "Revenue: Russia",
               "China": "Revenue: China", "Other overseas": "Revenue: Other overseas"}
    series = {name: [H[k][c] for c in hist_cols] + [M[k][c] for c in model_cols] for name, k in regions.items()}
    charts.navien_revenue_by_region(years, series, 3, img / "revenue_by_region.png")
    capex = [H["Total capex"][c] for c in hist_cols] + [M["Capex"][c] for c in model_cols]
    fcf = ([H["Cash flow from operations"][c] - H["Total capex"][c] for c in hist_cols]
           + [M["Cash flow from operations"][c] - M["Capex"][c] for c in model_cols])
    charts.navien_capex_fcf(years, capex, fcf, 3, img / "capex_fcf.png")

    g_cols, g_rows = sensitivity(D, "Sensitivity: value per share (KRW), WACC (rows) x terminal growth (columns)")
    m_cols, m_rows = sensitivity(D, "Sensitivity: value per share (KRW), long-term operating margin (rows) x WACC (columns)")
    inner = [v for _, vals in g_rows[1:4] for v in vals[1:4]]  # WACC +/-0.5pp, g +/-0.5pp
    comps_rows = [("DCF, WACC and g +/-0.5pp", min(inner), max(inner)),
                  ("Peer median fwd P/E on FY27E", C["At median forward P/E on FY2027E net income"]["Ticker"],
                   C["At median forward P/E on FY2027E net income"]["Ticker"]),
                  ("Peer median EV/EBITDA, LTM", C["At median EV / EBITDA (LTM)"]["Ticker"],
                   C["At median EV / EBITDA (LTM)"]["Ticker"]),
                  ("Peer median P/E, LTM", C["At median P/E (LTM)"]["Ticker"], C["At median P/E (LTM)"]["Ticker"]),
                  ("52-week trading range", lo52, hi52)]
    charts.navien_valuation_range(comps_rows, price, target, img / "valuation_range.png")
    for name in ["pb_vs_roe.png", "residual_by_sector.png"]:
        (img / name).write_bytes((charts.CHART_DIR / name).read_bytes())

    # ---------------- tables ----------------
    def fin_summary():
        cols = [("FY24A", "hist", "FY2024"), ("FY25A", "hist", "FY2025"), ("FY26E", "model", "FY2026E"),
                ("FY27E", "model", "FY2027E"), ("FY28E", "model", "FY2028E")]
        ev_now = C["Enterprise value"]["Ticker"]
        rows = []
        for lab, src, c in cols:
            if src == "hist":
                rev, op, ni = H["Revenue per income statement"][c], H["Operating profit"][c], H["Net income attributable to parent"][c]
                ebitda = H["EBITDA"][c]
                prev = {"FY2024": "FY2023", "FY2025": "FY2024"}[c]
                roe = ni / H["Equity attributable to parent"][prev]
            else:
                rev, op, ni, ebitda = M["Total revenue"][c], M["Operating profit"][c], M["Net income"][c], M["EBITDA"][c]
                roe = M["ROE (on opening equity)"][c]
            eps = ni * 1e9 / shares
            rows.append((lab, rev, op, op / rev, ni, eps, price / eps, roe, ev_now / ebitda))
        head = "".join(f"<th>{r[0]}</th>" for r in rows)
        spec = [("Revenue (KRW bn)", 1, lambda v: fmt_bn(v, 0)), ("Operating profit (KRW bn)", 2, lambda v: fmt_bn(v, 0)),
                ("Operating margin", 3, pct), ("Net income to parent (KRW bn)", 4, lambda v: fmt_bn(v, 0)),
                ("EPS (KRW)", 5, lambda v: f"{v:,.0f}"), ("P/E at current price", 6, lambda v: f"{v:.1f}x"),
                ("ROE (on opening equity)", 7, pct), ("EV/EBITDA at current EV", 8, lambda v: f"{v:.1f}x")]
        body = "".join(f"<tr><td>{name}</td>" + "".join(f"<td>{f(r[i])}</td>" for r in rows) + "</tr>"
                       for name, i, f in spec)
        return f"<table class='num'><tr><th></th>{head}</tr>{body}</table>"

    def fcff_table():
        cols = ["2H26E", "FY27E", "FY28E", "FY29E", "FY30E"]
        keys = ["Value", "C", "D", "E", "F"]
        lines = [("Revenue", "Revenue"), ("EBIT", "EBIT (operating profit)"), ("Tax on EBIT", "Less: tax on EBIT"),
                 ("D&amp;A", "Add: D&A"), ("Capex", "Less: capex"), ("Change in NWC", "Less: increase in net working capital"),
                 ("<b>FCFF</b>", "Free cash flow to firm"), ("PV of FCFF", "PV of FCFF")]
        head = "".join(f"<th>{c}</th>" for c in cols)
        body = "".join(f"<tr><td>{lab}</td>" + "".join(f"<td>{fmt_bn(D[k][c], 1)}</td>" for c in keys) + "</tr>"
                       for lab, k in lines)
        return f"<table class='num'><tr><th>KRW bn</th>{head}</tr>{body}</table>"

    def grid(cols, rows, row_fmt, col_fmt, base_row, base_col, corner):
        head = "".join(f"<th>{col_fmt(c)}</th>" for c in cols)
        body = ""
        for rv, vals in rows:
            cells = "".join(
                f"<td class='{'base' if abs(rv - base_row) < 1e-9 and abs(c - base_col) < 1e-9 else ''}'>{v:,.0f}</td>"
                for c, v in zip(cols, vals))
            body += f"<tr><th>{row_fmt(rv)}</th>{cells}</tr>"
        return f"<table class='num grid'><tr><th>{corner}</th>{head}</tr>{body}</table>"

    base_col_idx = min(range(len(m_cols)), key=lambda j: abs(m_cols[j] - 0.079))
    g_base_idx = min(range(len(g_cols)), key=lambda j: abs(g_cols[j] - g))
    m_lookup = {round(rv, 4): vals[base_col_idx] for rv, vals in m_rows}
    w_lookup = {round(rv, 4): vals[g_base_idx] for rv, vals in g_rows}
    view_vals = {"m85": m_lookup[0.085], "m105": m_lookup[0.105], "w89": w_lookup[0.089]}
    margin_step = (m_rows[2][1][base_col_idx] - m_rows[1][1][base_col_idx]) / (m_rows[2][0] - m_rows[1][0]) / 100
    wacc_grid = grid(g_cols, g_rows, lambda v: pct(v, 1), lambda v: pct(v, 1), 0.079, g, "WACC \\ g")
    margin_grid = grid(m_cols, m_rows, lambda v: pct(v, 1), lambda v: pct(v, 1),
                       I["Operating margin, FY2027E onward"]["Value"], 0.079, "OPM \\ WACC")

    peers = [(k, v) for k, v in C.items() if "EV/EBITDA" in v and k != "Peer median"]

    def mult(v):
        return v if isinstance(v, str) else f"{v:.1f}x"

    comps_body = "".join(
        f"<tr><td>{name}</td><td>{v['Ticker']}</td><td>{mult(v['EV/EBITDA'])}</td><td>{mult(v['P/E TTM'])}</td>"
        f"<td>{mult(v['P/E fwd'])}</td><td>{mult(v['P/B'])}</td><td>{pct(v['ROE'])}</td></tr>" for name, v in peers)
    med = C["Peer median"]
    comps_body += (f"<tr class='total'><td>Peer median</td><td></td><td>{med['EV/EBITDA']:.1f}x</td>"
                   f"<td>{med['P/E TTM']:.1f}x</td><td>{med['P/E fwd']:.1f}x</td><td>{med['P/B']:.1f}x</td>"
                   f"<td>{pct(med['ROE'])}</td></tr>")
    comps_body += (f"<tr class='total'><td>Kyung Dong Navien</td><td>009450 KS</td>"
                   f"<td>{C['EV / EBITDA, LTM']['Ticker']:.1f}x</td><td>{C['P/E, LTM']['Ticker']:.1f}x</td>"
                   f"<td>{C['P/E, FY2027E (model)']['Ticker']:.1f}x</td><td>{C['P/B, 30 Jun 2026']['Ticker']:.1f}x</td>"
                   f"<td>{pct(ni_ltm / eq_parent_jun)}</td></tr>")
    comps_table = ("<table class='num'><tr><th>Company</th><th>Ticker</th><th>EV/EBITDA</th><th>P/E TTM</th>"
                   f"<th>P/E fwd</th><th>P/B</th><th>ROE</th></tr>{comps_body}</table>")

    wacc_table = "".join(f"<tr><td>{lab}</td><td>{val}</td></tr>" for lab, val in [
        ("Risk-free rate (Korea 10Y, FRED)", pct(I["Risk-free rate"]["Value"], 2)),
        ("Equity risk premium (Damodaran, Korea)", pct(I["Equity risk premium"]["Value"], 2)),
        ("Unlevered beta (Damodaran, Building Materials)", f"{I['Unlevered beta']['Value']:.2f}"),
        ("Levered beta at D/E " + f"{D['Debt / equity']['Value']:.2f}", f"{D['Levered beta']['Value']:.2f}"),
        ("Cost of equity", pct(D["Cost of equity"]["Value"], 2)),
        ("After-tax cost of debt", pct(D["After-tax cost of debt"]["Value"], 2)),
        ("<b>WACC</b>", f"<b>{pct(wacc, 2)}</b>"),
        ("Terminal growth", pct(g, 1)),
    ])
    ev_table = "".join(f"<tr><td>{lab}</td><td>{val}</td></tr>" for lab, val in [
        ("Sum of PV of FCFF (KRW bn)", fmt_bn(D["Sum of PV of FCFF"]["Value"])),
        ("PV of terminal value (KRW bn)", fmt_bn(D["PV of terminal value"]["Value"])),
        ("<b>Enterprise value (KRW bn)</b>", f"<b>{fmt_bn(D['Enterprise value']['Value'])}</b>"),
        ("Less: net debt, 30 Jun 2026", fmt_bn(net_debt)),
        ("Less: non-controlling interests", fmt_bn(D["Less: non-controlling interests, 30 Jun 2026"]["Value"])),
        ("<b>Equity value (KRW bn)</b>", f"<b>{fmt_bn(D['Equity value']['Value'])}</b>"),
        ("Value per share (KRW)", f"{value_ps:,.0f}"),
        ("Terminal value share of EV", pct(D["Terminal value as % of EV"]["Value"], 0)),
        ("Implied terminal EV/EBITDA", f"{D['Implied terminal EV / EBITDA (FY2030)']['Value']:.1f}x"),
    ])

    ev_all = event["all"]
    html = TEMPLATE.format(**{
        "REPORT_DATE": REPORT_DATE, "rating": rating, "wacc_grid": wacc_grid, "margin_grid": margin_grid,
        "comps_table": comps_table, "wacc_table": wacc_table, "ev_table": ev_table,
        "margin_step_s": f"{round(margin_step, -3):,.0f}",
        **{f"v_{k}_s": f"{v:,.0f}" for k, v in view_vals.items()},
        **{f"u_{k}_s": pct(v / price - 1, 0) for k, v in view_vals.items()},
        "price_s": f"{price:,.0f}", "target_s": f"{target:,.0f}", "upside_s": pct(upside),
        "mcap_s": fmt_bn(mcap, 0), "net_debt_s": fmt_bn(net_debt, 0), "shares_s": f"{shares / 1e6:.2f}m",
        "hi52_s": f"{hi52:,.0f}", "lo52_s": f"{lo52:,.0f}", "end2024_s": f"{end_2024:,.0f}",
        "pb_s": f"{C['P/B, 30 Jun 2026']['Ticker']:.2f}x", "pe_ltm_s": f"{C['P/E, LTM']['Ticker']:.1f}x",
        "pe27_s": f"{C['P/E, FY2027E (model)']['Ticker']:.1f}x",
        "value_ps_s": f"{value_ps:,.0f}", "wacc_s": pct(wacc, 1), "g_s": pct(g, 1),
        "op_growth_s": pct(op25 / op24 - 1, 0), "ni_growth_s": pct(1 - ni25 / ni24, 0),
        "etr24_s": pct(etr24), "etr25_s": pct(etr25), "app25_s": pct(app25),
        "capex_pct25_s": pct(capex_pct25), "fcf25_s": fmt_bn(fcf25, 0),
        "fcff_lo_s": fmt_bn(min(fcff_vals[1:]), 0), "fcff_hi_s": fmt_bn(max(fcff_vals[1:]), 0),
        "payout25_s": pct(nav["payout"], 0), "payout_med_s": pct(payout_median, 0),
        "nav_discount_s": pct(-nav_discount, 0), "na_share_s": pct(na_share, 0),
        "opm_1h25_s": pct(opm_1h25), "opm_1h26_s": pct(opm_1h26), "growth_1h26_s": pct(growth_1h26),
        "opm_lt_s": pct(I["Operating margin, FY2027E onward"]["Value"]),
        "opm_2h_s": pct(I["Operating margin, 2H2026E"]["Value"]),
        "nd_ebitda_s": f"{net_debt / ebitda_ltm:.1f}x",
        "r2_s": f"{screen['r_squared']:.2f}", "roe_coef_s": f"{screen['roe_coef']:.1f}",
        "n_nonfin": screen["n_nonfinancial"], "n_cand": screen["n_candidates"],
        "share_below_s": pct(screen["share_below_justified"], 0), "coe_s": pct(screen["coe"], 1),
        "ev_n": ev_all["n"], "ev_car_s": pct(ev_all["mean_car"], 2), "ev_t_s": f"{ev_all['t_stat']:.2f}",
        "fin_table": fin_summary(), "fcff_table": fcff_table(),
        "comps_mid_fwd_s": f"{C['At median forward P/E on FY2027E net income']['Ticker']:,.0f}",
    })
    html_path = NOTE_DIR / "Navien_initiation.html"
    html_path.write_text(html, encoding="utf-8")
    pdf_path = NOTE_DIR / "Navien_initiation.pdf"
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf_path}", html_path.as_uri()], check=True, capture_output=True)
    return pdf_path, target, upside, rating


TEMPLATE = """<!doctype html>
<html><head><meta charset="utf-8"><title>Kyung Dong Navien initiation</title>
<style>
@page {{ size: A4; margin: 14mm 14mm 14mm 14mm; }}
body {{ font-family: Arial, Helvetica, sans-serif; font-size: 8.4pt; color: #1a1a1a; line-height: 1.38; margin: 0; }}
.page {{ page-break-after: always; }}
.page:last-child {{ page-break-after: auto; }}
.bar {{ background: #1F3864; color: #fff; padding: 5px 9px; font-size: 8pt; display: flex; justify-content: space-between; }}
h1 {{ font-size: 17pt; margin: 8px 0 2px; color: #1F3864; }}
h2 {{ font-size: 11pt; color: #1F3864; margin: 10px 0 4px; border-bottom: 1.5px solid #1F3864; padding-bottom: 2px; }}
h3 {{ font-size: 9.4pt; margin: 8px 0 2px; color: #1F3864; }}
.sub {{ font-size: 11pt; color: #444; margin: 0 0 6px; font-style: italic; }}
.cols {{ display: flex; gap: 14px; }}
.main {{ flex: 1; }}
.side {{ width: 205px; }}
.box {{ background: #EEF2F8; padding: 7px 8px; margin-bottom: 8px; }}
.rating {{ font-size: 13pt; font-weight: bold; color: #1F3864; }}
table {{ border-collapse: collapse; width: 100%; font-size: 8pt; margin: 3px 0 6px; }}
th, td {{ padding: 2.2px 4px; border-bottom: 0.5px solid #d0d0d0; text-align: left; }}
th {{ background: #D9E1F2; font-weight: bold; }}
table.num td, table.num th {{ text-align: right; }}
table.num td:first-child, table.num th:first-child {{ text-align: left; }}
table.kv td:last-child {{ text-align: right; }}
tr.total td {{ font-weight: bold; border-top: 1px solid #888; }}
td.base {{ background: #FFF2CC; font-weight: bold; }}
.grid th {{ text-align: center; }}
img {{ width: 100%; margin: 2px 0; }}
.two {{ display: flex; gap: 10px; align-items: flex-start; }}
.two > div {{ flex: 1; }}
table {{ font-size: 7.6pt; }}
.src {{ font-size: 7pt; color: #666; font-style: italic; margin: 0 0 6px; }}
ul {{ margin: 2px 0 4px 16px; padding: 0; }}
li {{ margin-bottom: 3px; }}
.disc {{ font-size: 7pt; color: #555; border-top: 1px solid #aaa; margin-top: 8px; padding-top: 4px; }}
</style></head><body>

<div class="page">
<div class="bar"><span>Korea Equity Research | Initiation of Coverage</span><span>{REPORT_DATE}</span></div>
<h1>Kyung Dong Navien (009450 KS)</h1>
<p class="sub">The plant is built. Now the cash comes back.</p>
<div class="cols">
<div class="main">
<p>We initiate on Kyung Dong Navien, the Korean boiler and water heater maker that earns
{na_share_s} of its revenue in North America, with an <b>{rating}</b> rating and a target price of
<b>KRW {target_s}</b>, {upside_s} above the current price. Our KOSPI-wide screen flags Navien as one of the
most undervalued companies relative to the P/B its ROE and sector justify. We think the market is
anchoring on a FY2025 earnings decline that was driven by tax, not operations, and is not yet pricing the
free cash flow that follows the end of a two-year capex cycle.</p>

<h3>1. The FY2025 earnings dip was tax, not business</h3>
<p>FY2025 operating profit rose {op_growth_s} while net income fell {ni_growth_s}. The effective tax rate
jumped to {etr25_s} from {etr24_s}, driven by a swing in deferred taxes. Tax at statutory rates was
{app25_s} of pre-tax profit. On a normal tax rate, the earnings base is much higher than the headline
suggests.</p>

<h3>2. The capex cycle is over and free cash flow turns positive</h3>
<p>The KRW 104.3bn Seotan plant expansion was completed in July 2026. Capex reached {capex_pct25_s} of
revenue in FY2025 and free cash flow (operating cash flow less capex) was KRW {fcf25_s}bn. We model capex
falling to 4.5% of revenue by FY2028E and free cash flow to the firm of KRW {fcff_lo_s}bn to
{fcff_hi_s}bn a year from FY2027E.</p>

<h3>3. Room to pay out, a Value-Up story not yet told</h3>
<p>Navien paid out {payout25_s} of FY2025 earnings, against a median of {payout_med_s} across the {n_nonfin}
non-financials in our screen, and has not filed a Value-Up plan. The stock trades {nav_discount_s} below the
P/B our screen model implies for its ROE and sector. Our event study shows that filing a plan alone did not
move prices (mean CAR {ev_car_s}, t = {ev_t_s}), so the catalyst we watch for is an actual increase in
payout funded by the new free cash flow, not the filing itself.</p>

<h3>Key risks</h3>
<ul>
<li><b>US demand and tariffs.</b> {na_share_s} of revenue is North American. 1H2026 margins
({opm_1h26_s} vs {opm_1h25_s} in 1H2025) include US tariff refunds whose amount is not disclosed.
We do not extrapolate them.</li>
<li><b>Slowing growth.</b> 1H2026 revenue grew {growth_1h26_s} including the Commax acquisition, and
Q2 revenue fell 1.0% year on year (DART preliminary results, 11 Aug 2026).</li>
<li><b>Share price signal.</b> The stock fell from KRW {end2024_s} at end 2024 to KRW {price_s}
despite higher operating profit. The market may be pricing a risk that filings do not yet show.</li>
<li>FX (KRW/USD), Russia sanctions, and losses at Commax (FY2025 operating loss KRW 14.2bn).</li>
</ul>
</div>
<div class="side">
<div class="box">
<div class="rating">{rating}</div>
<table class="kv">
<tr><td>Target price (KRW)</td><td><b>{target_s}</b></td></tr>
<tr><td>Price, 25 Sep 2026 (KRW)</td><td>{price_s}</td></tr>
<tr><td>Upside</td><td><b>{upside_s}</b></td></tr>
<tr><td>DCF value (KRW)</td><td>{value_ps_s}</td></tr>
<tr><td>WACC / terminal g</td><td>{wacc_s} / {g_s}</td></tr>
</table></div>
<div class="box">
<b>Key data</b>
<table class="kv">
<tr><td>Market cap (KRW bn)</td><td>{mcap_s}</td></tr>
<tr><td>Shares outstanding</td><td>{shares_s}</td></tr>
<tr><td>52-week range (KRW)</td><td>{lo52_s} to {hi52_s}</td></tr>
<tr><td>Net debt, Jun 2026 (KRW bn)</td><td>{net_debt_s}</td></tr>
<tr><td>Net debt / LTM EBITDA</td><td>{nd_ebitda_s}</td></tr>
<tr><td>P/B, Jun 2026</td><td>{pb_s}</td></tr>
<tr><td>P/E, LTM</td><td>{pe_ltm_s}</td></tr>
<tr><td>P/E, FY2027E</td><td>{pe27_s}</td></tr>
<tr><td>Value-Up plan filed</td><td>No</td></tr>
</table></div>
</div></div>
<h2>Financial summary</h2>
{fin_table}
<p class="src">Source: DART (FY2024 to FY2025 consolidated), analyst model (FY2026E to FY2028E). FY2026E includes
1H2026 actuals, which contain undisclosed US tariff refunds. Target price is the DCF value rounded to the
nearest KRW 1,000.</p>
</div>

<div class="page">
<div class="bar"><span>Kyung Dong Navien (009450 KS)</span><span>{REPORT_DATE}</span></div>
<h2>Market context: where the Korea discount still sits</h2>
<p>Korea's Value-Up Program (from February 2024), the Commercial Act amendments (from July 2025) and the
January 2026 dividend tax changes all aim to close the gap between Korean valuations and what companies
earn. To find where that gap remains, we screened {n_nonfin} KOSPI non-financials with market caps above
KRW 500bn. We regress log P/B on ROE with sector fixed effects. ROE explains about half the variation
(R-squared {r2_s}); within a sector, one extra point of ROE goes with roughly {roe_coef_s}% higher P/B.</p>
<img src="img/pb_vs_roe.png" style="width: 80%;">
<p class="src">Source: DART, FinanceDataReader, analyst screen. Sector-adjusted P/B removes each sector's fixed
effect; distance below the line is the discount to ROE-justified P/B.</p>
<p>The discount is concentrated rather than universal. Only {share_below_s} of companies trade below a
textbook justified P/B at a {coe_s} cost of equity. Materials, utilities and telecom, transport and autos
trade well below what their ROE implies, while industrials and technology hardware trade far above it.</p>
<div class="two"><div>
<img src="img/residual_by_sector.png">
<p class="src">Source: analyst screen, ROE-only model (without sector effects) to show sector-level gaps.</p>
</div><div>
<p><b>Did Value-Up filings move prices?</b> Across {ev_n} first Value-Up plan disclosures, the mean
cumulative abnormal return over trading days -1 to +5 was {ev_car_s} (t = {ev_t_s}). Markets appear to have
priced the program at the policy level, not company by company. For stock selection this means filing a plan
is not enough; delivery on payout is what matters.</p>
<p><b>Why Navien.</b> Of the {n_cand} candidates (bottom quartile of residual, above-median ROE,
below-median payout), many have peak-cycle ROE (shipbuilding) or one-off gains. Navien combines a large
discount, a simple single-segment business, an explainable earnings dip and a clear cash flow inflection.</p>
</div></div>
</div>

<div class="page">
<div class="bar"><span>Kyung Dong Navien (009450 KS)</span><span>{REPORT_DATE}</span></div>
<h2>Company: a boiler maker that became a US water heater business</h2>
<p>According to its FY2025 annual report, the parent company's sales are 45% water heaters, 38% household
boilers and 17% other products. In the US, water heaters are 73% of sales. In Korea, Navien developed the
industry's first condensing boiler in 1998, and condensing boilers are now mandatory in designated
air-quality zones, which supports replacement demand. The company reports a single operating segment but
discloses revenue by region, which we use as the forecast driver.</p>
<div class="two"><div><img src="img/revenue_by_region.png">
<p class="src">Source: DART notes (geographic revenue), analyst forecasts. Korea includes Commax from FY2026E.</p></div>
<div><img src="img/capex_fcf.png">
<p class="src">Source: DART cash flow statements (FY2023A to FY2025A), analyst model (FY2026E onward, CFO less capex,
before acquisitions and dividends).</p></div></div>
<h3>What we assume</h3>
<ul>
<li><b>Revenue:</b> North America +7% in FY2026E (1H2026 actual +7.1%), slowing to +4% by FY2030E. Korea
flat in FY2026E (1H2026 flat even with Commax), then +3%. Russia flat, China -5%, other overseas +20%
fading to +8%.</li>
<li><b>Margins:</b> FY2026E uses 1H2026 as reported plus a 2H2026 margin equal to 2H2025 ({opm_2h_s}).
From FY2027E we use {opm_lt_s}, the FY2023 to FY2025 average, because the size of the 1H2026 tariff
refund is not disclosed.</li>
<li><b>Tax:</b> 29.9% on EBIT, the FY2024 to FY2025 average of tax at statutory rates, excluding
deferred tax swings.</li>
<li><b>Reinvestment:</b> capex 7.0% of revenue in FY2026E, 5.0% in FY2027E, 4.5% after. D&amp;A 3.5% and
net working capital 26% of revenue, in line with FY2024 to FY2025.</li>
</ul>
<h3>What would change our view</h3>
<ul>
<li><b>Margin below its FY2023 level (8.8%).</b> At an 8.5% long-term operating margin, the DCF value is
KRW {v_m85_s} ({u_m85_s} upside), close to the Neutral boundary. This is the main downside case.</li>
<li><b>Higher discount rate.</b> At an 8.9% WACC (one point above ours), the value is KRW {v_w89_s}
({u_w89_s} upside).</li>
<li><b>Part of the 1H2026 margin holds.</b> At a 10.5% long-term margin, the value is KRW {v_m105_s}
({u_m105_s} upside).</li>
<li><b>Capital return.</b> A Value-Up plan with a payout well above today's {payout25_s} would address the
thesis directly. We would revisit the rating if free cash flow is instead spent on further acquisitions.</li>
</ul>
<div class="disc">This note is an independent student project prepared for learning and portfolio purposes.
It is not investment advice, not a solicitation, and not affiliated with or endorsed by any financial
institution. All figures are from public data (DART, FinanceDataReader, FRED, Damodaran Online, Yahoo
Finance) processed by the code and Excel model in the accompanying repository. Price data as of
{REPORT_DATE}.</div>
</div>

<div class="page">
<div class="bar"><span>Kyung Dong Navien (009450 KS)</span><span>{REPORT_DATE}</span></div>
<h2>Valuation: DCF target of KRW {target_s}</h2>
<div class="cols">
<div class="main">
<h3>Free cash flow to firm</h3>
{fcff_table}
<p class="src">Valuation date 30 Jun 2026, mid-period discounting. 2H2026E is FY2026E less 1H2026 actual.</p>
</div>
<div class="side" style="width: 230px;">
<h3>Discount rate</h3>
<table class="kv">{wacc_table}</table>
<p class="src">The regression beta against KOSPI is 0.13 with R-squared 0.01, so we use a bottom-up
industry beta relevered at Navien's D/E.</p>
</div></div>
<div class="cols">
<div class="main">
<h3>Sensitivity: value per share (KRW)</h3>
{wacc_grid}
{margin_grid}
</div>
<div class="side" style="width: 230px;">
<h3>From EV to equity</h3>
<table class="kv">{ev_table}</table>
</div></div>
<h3>Trading comparables (cross-check, not blended into the target)</h3>
{comps_table}
<p class="src">Source: Yahoo Finance via yfinance (peers, trailing twelve months, local currency), analyst model
(Navien). Navien LTM figures include 1H2026 tariff refunds.</p>
<div class="two"><div style="flex: 1.25;"><img src="img/valuation_range.png"></div><div>
<p>Our DCF sits below every comparables-based value. At the peer median forward P/E on our FY2027E earnings,
Navien would be worth KRW {comps_mid_fwd_s}. We anchor on the DCF because it does not rely on
refund-inflated trailing earnings, which makes the target conservative. The main upside risk to our target is
margin: each point of long-term operating margin is worth roughly KRW {margin_step_s} per share at our WACC.</p></div></div>

</div>
</body></html>
"""


if __name__ == "__main__":
    path, target, upside, rating = build()
    print(f"Saved {path} | target KRW {target:,.0f} | upside {upside:.1%} | {rating}")

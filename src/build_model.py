"""Phase 4: build the Kyung Dong Navien (009450) Excel model with live formulas.

Sheets: Cover, Inputs, Historical, Model (3 statements), DCF, Comps.
Every historical number is read from cached DART files (data/raw/dart/) or cached reference
files (data/raw/reference/), never typed by hand, except the few note disclosures marked
"DART notes" in the Source column. All projections and valuation outputs are Excel formulas.

Units: KRW bn unless a row says otherwise.

Run from the repo root:  .venv/bin/python src/build_model.py
"""

import json
import re

import pandas as pd
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from config import RAW_DIR, ROOT

OUT_PATH = ROOT / "model" / "Navien_009450_model.xlsx"
FIN_DIR = RAW_DIR / "dart" / "finstate"
BN = 1e9

# ---------------- styles ----------------
FONT = "Arial"
BLUE, GREEN, BLACK = "0000FF", "008000", "000000"
KEY_FILL = PatternFill("solid", fgColor="FFFF00")
HEAD_FILL = PatternFill("solid", fgColor="1F3864")
SUB_FILL = PatternFill("solid", fgColor="D9E1F2")
THIN = Side(style="thin", color="808080")

FMT = {
    "bn": '#,##0.0;(#,##0.0);"-"',
    "won": '#,##0;(#,##0);"-"',
    "pct": '0.0%;(0.0%);"-"',
    "pct2": '0.00%;(0.00%);"-"',
    "x": '0.0"x";(0.0"x");"-"',
    "num": '#,##0;(#,##0);"-"',
    "dec": '0.00;(0.00);"-"',
    "yr": '0.00',
    "text": "@",
}

CROSS_SHEET_LINK = re.compile(r"^='?[A-Za-z ]+'?!\$?[A-Z]+\$?\d+$")


def style_value(cell, value, fmt, key=False):
    cell.value = value
    cell.number_format = FMT[fmt]
    if isinstance(value, str) and value.startswith("="):
        color = GREEN if CROSS_SHEET_LINK.match(value) else BLACK
    elif isinstance(value, (int, float)):
        color = BLUE  # hardcoded input
    else:
        color = BLACK
    cell.font = Font(name=FONT, size=10, color=color)
    if key:
        cell.fill = KEY_FILL


def title(ws, text, subtitle):
    ws["A1"] = text
    ws["A1"].font = Font(name=FONT, size=14, bold=True, color="1F3864")
    ws["A2"] = subtitle
    ws["A2"].font = Font(name=FONT, size=9, italic=True, color="595959")


def header(ws, row, labels, start_col=1):
    for i, lab in enumerate(labels):
        c = ws.cell(row=row, column=start_col + i, value=lab)
        c.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
        c.fill = HEAD_FILL
        c.alignment = Alignment(horizontal="center" if i else "left")


def section(ws, row, text, ncols):
    for col in range(1, ncols + 1):
        ws.cell(row=row, column=col).fill = SUB_FILL
    c = ws.cell(row=row, column=1, value=text)
    c.font = Font(name=FONT, size=10, bold=True)


def label(ws, row, text, bold=False, indent=0):
    c = ws.cell(row=row, column=1, value=text)
    c.font = Font(name=FONT, size=10, bold=bold)
    c.alignment = Alignment(indent=indent)


def source(ws, row, col, text):
    c = ws.cell(row=row, column=col, value=text)
    c.font = Font(name=FONT, size=8, italic=True, color="595959")


class RowMap:
    """Keeps track of which row each named line lives on, so formulas can refer to lines by name."""

    def __init__(self):
        self.rows = {}

    def __setitem__(self, key, row):
        self.rows[key] = row

    def __getitem__(self, key):
        return self.rows[key]


# ---------------- DART extraction ----------------

def load_fs(name):
    return pd.read_csv(FIN_DIR / f"{name}.csv", dtype=str)


def amount(fs, account_id, col, sj=None):
    rows = fs[fs["account_id"] == account_id]
    if sj:
        rows = rows[rows["sj_div"].isin(sj if isinstance(sj, list) else [sj])]
    if rows.empty:
        raise KeyError(f"{account_id} not found")
    value = str(rows.iloc[0][col]).replace(",", "")
    if value in ["", "nan", "-"]:
        return 0.0
    return float(value) / BN


def amount_by_name(fs, sj, name, col):
    rows = fs[(fs["sj_div"] == sj) & (fs["account_nm"].str.replace(" ", "") == name)]
    if rows.empty:
        raise KeyError(f"{name} not found")
    return float(str(rows.iloc[0][col]).replace(",", "")) / BN


def historical_data():
    """Return {line: [FY2023, FY2024, FY2025, 1H2025, 1H2026]} in KRW bn (None = not available)."""
    fy = load_fs("009450_2025_11011_CFS")
    h1 = load_fs("009450_2026_11012_CFS")
    annual = ["bfefrmtrm_amount", "frmtrm_amount", "thstrm_amount"]
    half_is = ["frmtrm_add_amount", "thstrm_add_amount"]  # 1H2025, 1H2026 cumulative

    def is_line(account_id):
        return ([amount(fy, account_id, c, "IS") for c in annual]
                + [amount(h1, account_id, c, "IS") for c in half_is])

    def bs_line(account_id):
        return [amount(fy, account_id, c, "BS") for c in annual] + [None, amount(h1, account_id, "thstrm_amount", "BS")]

    def cf_line(account_id):
        return [amount(fy, account_id, c, "CF") for c in annual] + [None, amount(h1, account_id, "thstrm_amount", "CF")]

    d = {
        "revenue_is": is_line("ifrs-full_Revenue"),
        "cogs": is_line("ifrs-full_CostOfSales"),
        "sga": is_line("dart_TotalSellingGeneralAdministrativeExpenses"),
        "op": is_line("dart_OperatingIncomeLoss"),
        "pbt": is_line("ifrs-full_ProfitLossBeforeTax"),
        "tax": is_line("ifrs-full_IncomeTaxExpenseContinuingOperations"),
        "ni": is_line("ifrs-full_ProfitLoss"),
        "cash": bs_line("ifrs-full_CashAndCashEquivalents"),
        "dep_st": bs_line("ifrs-full_ShorttermDepositsNotClassifiedAsCashEquivalents"),
        "dep_lt": bs_line("dart_LongTermDepositsNotClassifiedAsCashEquivalents"),
        "ar": bs_line("ifrs-full_CurrentTradeReceivables"),
        "inv": bs_line("ifrs-full_Inventories"),
        "ppe": bs_line("ifrs-full_PropertyPlantAndEquipment"),
        "intang": bs_line("ifrs-full_IntangibleAssetsAndGoodwill"),
        "assets": bs_line("ifrs-full_Assets"),
        "ap": bs_line("dart_ShortTermTradePayables"),
        "cl": bs_line("ifrs-full_CurrentContractLiabilities"),
        "debt_st": bs_line("ifrs-full_CurrentBorrowingsAndCurrentPortionOfNoncurrentBorrowings"),
        "debt_lt": bs_line("ifrs-full_LongtermBorrowings"),
        "lease_c": bs_line("ifrs-full_CurrentLeaseLiabilities"),
        "lease_nc": bs_line("ifrs-full_NoncurrentLeaseLiabilities"),
        "liab": bs_line("ifrs-full_Liabilities"),
        "eq_parent": bs_line("ifrs-full_EquityAttributableToOwnersOfParent"),
        "nci": bs_line("ifrs-full_NoncontrollingInterests"),
        "equity": bs_line("ifrs-full_Equity"),
        "cfo": cf_line("ifrs-full_CashFlowsFromUsedInOperatingActivities"),
        "capex_ppe": cf_line("ifrs-full_PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"),
        "capex_int": [amount(fy, "ifrs-full_PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities", c, "CF") for c in annual]
                     + [None, amount_by_name(h1, "CF", "무형자산의취득", "thstrm_amount")],
        "div_paid": cf_line("ifrs-full_DividendsPaidClassifiedAsFinancingActivities"),
    }
    # NI attributable to parent: FY2025 report tags it with the alternate ID
    d["ni_parent"] = ([amount(fy, "ifrs-full_ProfitLossAttributableToOrdinaryEquityHoldersOfParentEntity", c, "IS") for c in annual]
                      + [amount_by_name(h1, "IS", "지배기업소유주지분순이익", c) for c in half_is])
    return d


# Disclosures that exist only in the notes to the financial statements (thousand KRW in source)
NOTES = {
    # Geographic revenue: FY2024 and FY2025 annual reports, 1H2026 half-year report, note "지역에 대한 공시"
    "rev_korea": [389.731877, 411.549738, 458.396757, 228.831414, 228.582661],
    "rev_na": [660.915049, 774.931923, 865.778487, 471.574511, 504.994164],
    "rev_russia": [79.872522, 78.690989, 80.044573, 28.757106, 35.326866],
    "rev_china": [30.857741, 30.711092, 23.935346, 6.720572, 7.872262],
    "rev_other": [42.935682, 57.995700, 74.084566, 21.574697, 36.743760],
    # Total depreciation and amortization, note "비용의 성격별 분류"
    "da": [None, 47.372658, 52.812497, 25.783551, 27.340245],
    # Tax at the applicable rate, note "법인세비용" reconciliation (FY2024, FY2025)
    "tax_at_applicable_rate": [None, 46.417680, 44.180030, None, None],
}


# ---------------- workbook ----------------

def build():
    hist = historical_data()
    peers = json.loads((RAW_DIR / "reference" / "peers_yfinance.json").read_text())
    listing = pd.read_csv(RAW_DIR / "listing_KOSPI_20260925.csv", dtype={"Code": str})
    navien = listing[listing["Code"] == "009450"].iloc[0]
    treasury = pd.read_csv(RAW_DIR / "dart" / "treasury" / "009450_2025_11011.csv", dtype=str)
    treasury_shares = float(treasury[(treasury["stock_knd"] == "보통주") & (treasury["acqs_mth1"] == "총계")]
                            ["trmend_qy"].iloc[0].replace(",", ""))

    wb = Workbook()
    ws_cover = wb.active
    ws_cover.title = "Cover"
    ws_in = wb.create_sheet("Inputs")
    ws_h = wb.create_sheet("Historical")
    ws_m = wb.create_sheet("Model")
    ws_d = wb.create_sheet("DCF")
    ws_c = wb.create_sheet("Comps")

    I, H, M, D, C = RowMap(), RowMap(), RowMap(), RowMap(), RowMap()

    # ======================= Historical =======================
    title(ws_h, "Historical financials (consolidated, KRW bn)",
          "Source: DART OpenAPI, FY2025 annual report (FY2023 to FY2025) and 1H2026 half-year report. Notes items marked.")
    hcols = ["FY2023", "FY2024", "FY2025", "1H2025", "1H2026"]
    header(ws_h, 4, ["KRW bn"] + hcols + ["Source"])
    HC = ["B", "C", "D", "E", "F"]
    r = 5

    def hrow(key, text, values, fmt="bn", src="DART CFS", bold=False, indent=1):
        nonlocal r
        H[key] = r
        label(ws_h, r, text, bold=bold, indent=indent)
        for col, v in zip(HC, values):
            if v is None:
                continue
            style_value(ws_h[f"{col}{r}"], v, fmt)
        source(ws_h, r, 7, src)
        r += 1

    def hform(key, text, template, fmt="bn", cols=HC, bold=False, indent=1, src="Formula"):
        nonlocal r
        H[key] = r
        label(ws_h, r, text, bold=bold, indent=indent)
        for col in cols:
            style_value(ws_h[f"{col}{r}"], template.format(c=col, **H.rows), fmt)
        source(ws_h, r, 7, src)
        r += 1

    section(ws_h, r, "Income statement", 7); r += 1
    hrow("rev_korea", "Revenue: Korea", NOTES["rev_korea"], src="DART notes, geographic disclosure")
    hrow("rev_na", "Revenue: North America", NOTES["rev_na"], src="DART notes, geographic disclosure")
    hrow("rev_russia", "Revenue: Russia", NOTES["rev_russia"], src="DART notes, geographic disclosure")
    hrow("rev_china", "Revenue: China", NOTES["rev_china"], src="DART notes, geographic disclosure")
    hrow("rev_other", "Revenue: Other overseas", NOTES["rev_other"], src="DART notes, geographic disclosure")
    hform("revenue", "Total revenue", "=SUM({c}{rev_korea}:{c}{rev_other})", bold=True, indent=0)
    hrow("revenue_is", "Revenue per income statement", hist["revenue_is"])
    hform("rev_check", "Check: regions minus income statement", "={c}{revenue}-{c}{revenue_is}")
    hrow("cogs", "Cost of sales", hist["cogs"])
    hform("gp", "Gross profit", "={c}{revenue_is}-{c}{cogs}")
    hrow("sga", "SG&A", hist["sga"])
    hrow("op", "Operating profit", hist["op"], bold=True, indent=0)
    hrow("da", "Depreciation and amortization", NOTES["da"], src="DART notes, expenses by nature")
    hform("ebitda", "EBITDA", "={c}{op}+{c}{da}", cols=HC[1:])
    hrow("pbt", "Profit before tax", hist["pbt"])
    hrow("tax", "Income tax expense", hist["tax"])
    hrow("ni", "Net income", hist["ni"])
    hrow("ni_parent", "Net income attributable to parent", hist["ni_parent"], bold=True, indent=0)
    hrow("tax_app", "Tax at applicable rates (tax reconciliation)", NOTES["tax_at_applicable_rate"],
         src="DART notes, income tax reconciliation")

    section(ws_h, r, "Ratios", 7); r += 1
    hform("growth", "Revenue growth", "={c}{revenue_is}/{p}{revenue_is}-1".replace("{p}", "{p}"), fmt="pct", cols=[])
    H["growth"] = r - 1
    for col, prev in [("C", "B"), ("D", "C"), ("F", "E")]:
        style_value(ws_h[f"{col}{H['growth']}"], f"={col}{H['revenue_is']}/{prev}{H['revenue_is']}-1", "pct")
    source(ws_h, H["growth"], 7, "1H2026 column is growth vs 1H2025")
    hform("gpm", "Gross margin", "={c}{gp}/{c}{revenue_is}", fmt="pct")
    hform("opm", "Operating margin", "={c}{op}/{c}{revenue_is}", fmt="pct")
    hform("etr", "Effective tax rate", "={c}{tax}/{c}{pbt}", fmt="pct")
    hform("app_rate", "Tax at applicable rates / profit before tax", "={c}{tax_app}/{c}{pbt}", fmt="pct", cols=["C", "D"])
    hform("da_pct", "D&A / revenue", "={c}{da}/{c}{revenue_is}", fmt="pct", cols=HC[1:])

    section(ws_h, r, "Balance sheet (period end)", 7); r += 1
    BSC = ["B", "C", "D", "F"]
    hrow("cash", "Cash and cash equivalents", hist["cash"])
    hrow("dep_st", "Short-term deposits", hist["dep_st"])
    hrow("dep_lt", "Long-term deposits", hist["dep_lt"])
    hrow("ar", "Trade receivables", hist["ar"])
    hrow("inv", "Inventories", hist["inv"])
    hrow("ppe", "Property, plant and equipment", hist["ppe"])
    hrow("intang", "Intangible assets and goodwill", hist["intang"])
    hrow("assets", "Total assets", hist["assets"], bold=True, indent=0)
    hrow("ap", "Trade payables", hist["ap"])
    hrow("cl", "Contract liabilities", hist["cl"])
    hrow("debt_st", "Short-term borrowings", hist["debt_st"])
    hrow("debt_lt", "Long-term borrowings", hist["debt_lt"])
    hrow("lease_c", "Lease liabilities, current", hist["lease_c"])
    hrow("lease_nc", "Lease liabilities, non-current", hist["lease_nc"])
    hrow("liab", "Total liabilities", hist["liab"], bold=True, indent=0)
    hrow("eq_parent", "Equity attributable to parent", hist["eq_parent"])
    hrow("nci", "Non-controlling interests", hist["nci"])
    hrow("equity", "Total equity", hist["equity"], bold=True, indent=0)
    hform("bs_check", "Check: assets minus liabilities minus equity", "={c}{assets}-{c}{liab}-{c}{equity}", cols=BSC)
    hform("cash_dep", "Cash and deposits", "={c}{cash}+{c}{dep_st}+{c}{dep_lt}", cols=BSC)
    hform("nwc", "Net working capital (AR + inventory - AP - contract liabilities)",
          "={c}{ar}+{c}{inv}-{c}{ap}-{c}{cl}", cols=BSC)
    hform("nwc_pct", "Net working capital / revenue", "={c}{nwc}/{c}{revenue_is}", fmt="pct", cols=["B", "C", "D"])
    hform("gross_debt", "Gross debt (borrowings + leases)", "={c}{debt_st}+{c}{debt_lt}+{c}{lease_c}+{c}{lease_nc}", cols=BSC)
    hform("net_debt", "Net debt", "={c}{gross_debt}-{c}{cash_dep}", cols=BSC, bold=True, indent=0)
    hform("nfa", "Net fixed assets (PP&E + intangibles)", "={c}{ppe}+{c}{intang}", cols=BSC)

    section(ws_h, r, "Cash flow", 7); r += 1
    CFC = ["B", "C", "D", "F"]
    hrow("cfo", "Cash flow from operations", hist["cfo"])
    hrow("capex_ppe", "Purchase of PP&E", hist["capex_ppe"])
    hrow("capex_int", "Purchase of intangibles", hist["capex_int"])
    hform("capex", "Total capex", "={c}{capex_ppe}+{c}{capex_int}", cols=CFC, bold=True, indent=0)
    hform("capex_pct", "Capex / revenue", "={c}{capex}/{c}{revenue_is}", fmt="pct", cols=CFC)
    hrow("div_paid", "Dividends paid", hist["div_paid"])
    ws_h.column_dimensions["A"].width = 58
    for col in HC:
        ws_h.column_dimensions[col].width = 11
    ws_h.column_dimensions["G"].width = 42
    ws_h.freeze_panes = "B5"

    # ======================= Inputs =======================
    title(ws_in, "Inputs and assumptions",
          "Blue = hardcoded input, black = formula, green = link to another sheet, yellow = key assumption. "
          "Confirmed by the analyst on 2026-09-25.")
    header(ws_in, 4, ["Scalar input", "Value", "", "", "", "", "", "Source / rationale"])
    r = 5

    def irow(key, text, value, fmt, src, key_fill=False):
        nonlocal r
        I[key] = r
        label(ws_in, r, text, indent=1)
        style_value(ws_in[f"B{r}"], value, fmt, key=key_fill)
        source(ws_in, r, 8, src)
        r += 1

    section(ws_in, r, "Market data (25 Sep 2026)", 8); r += 1
    irow("price", "Share price (KRW)", float(navien["Close"]), "won", "FinanceDataReader KOSPI listing, close 25 Sep 2026")
    irow("listed", "Common shares listed", float(navien["Stocks"]), "num", "FinanceDataReader KOSPI listing")
    irow("treasury", "Treasury shares", treasury_shares, "num", "DART FY2025 annual report, treasury stock table")
    irow("shares", "Shares outstanding", f"=B{I['listed']}-B{I['treasury']}", "num", "Listed less treasury")

    section(ws_in, r, "Discount rate", 8); r += 1
    rf = pd.read_csv(RAW_DIR / "reference" / "fred_korea_10y.csv", index_col=0)["IRLTLT01KRM156N"].dropna()
    ctry = pd.read_excel(RAW_DIR / "reference" / "damodaran_ctryprem.xlsx", sheet_name="ERPs by country", header=None)
    erp = float(ctry[ctry[0] == "Korea"].iloc[0][4])
    betas = pd.read_excel(RAW_DIR / "reference" / "damodaran_betaGlobal.xls", sheet_name="Industry Averages", header=None)
    hdr = betas.index[betas[0].astype(str).str.contains("Industry Name", na=False)][0]
    betas.columns = betas.iloc[hdr]
    beta_u = float(betas[betas["Industry Name"] == "Building Materials"].iloc[0]["Unlevered beta"])
    irow("rf", "Risk-free rate", round(float(rf.iloc[-1]) / 100, 5), "pct2",
         f"Korea 10Y government bond yield, {str(rf.index[-1])[:7]}, FRED IRLTLT01KRM156N", True)
    irow("erp", "Equity risk premium", round(erp, 5), "pct2", "Damodaran country risk premiums, Jan 2026, Korea total ERP", True)
    irow("beta_u", "Unlevered beta", round(beta_u, 4), "dec", "Damodaran global industry betas, Jan 2026, Building Materials", True)
    irow("t_marg", "Marginal tax rate (debt shield, relevering)", 0.264, "pct",
         "Korea statutory rate incl. local tax, Damodaran country tax rates")
    irow("spread", "Debt spread over risk-free", 0.004, "pct2",
         "Damodaran synthetic rating, smaller firms: coverage > 12.5x = AAA. FY25 EBIT / interest paid = 15.3x")
    irow("kd", "Pre-tax cost of debt", f"=B{I['rf']}+B{I['spread']}", "pct2", "Risk-free rate + spread")
    irow("g", "Terminal growth", 0.02, "pct", "Bank of Korea inflation target", True)

    section(ws_in, r, "Operating assumptions", 8); r += 1
    irow("tax", "Tax rate on EBIT",
         f"=AVERAGE(Historical!C{H['app_rate']}:D{H['app_rate']})", "pct",
         "Average of tax at applicable rates / PBT, FY2024 and FY2025 (excludes deferred tax swings)")
    irow("opm_2h26", "Operating margin, 2H2026E",
         f"=(Historical!D{H['op']}-Historical!E{H['op']})/(Historical!D{H['revenue_is']}-Historical!E{H['revenue_is']})",
         "pct", "Equal to 2H2025 actual margin. 1H2026 includes undisclosed US tariff refunds, so it is not extrapolated")
    irow("opm_lt", "Operating margin, FY2027E onward", 0.095, "pct", "FY2023 to FY2025 average 9.4%, range 8.8% to 9.8%", True)
    irow("da_pct", "D&A / revenue", 0.035, "pct", "FY2024 and FY2025 both 3.5%")
    irow("nwc_pct", "Net working capital / revenue", 0.26, "pct", "FY2024 26.3%, FY2025 27.7%")
    irow("dps", "DPS, FY2026E onward (KRW)", 750.0, "won", "Held at FY2025 DPS of KRW 750 (DART dividend table). No policy change assumed")
    irow("acq", "Commax acquisition, cash consideration", 31.729097, "bn", "DART 1H2026 notes, business combination (paid 2026)")
    irow("upside_band", "Rating band (+/-)", 0.15, "pct", "Overweight above +15%, Underweight below -15%, else Neutral")

    r += 1
    I["ts_header"] = r
    header(ws_in, r, ["Time-series input", "", "FY2026E", "FY2027E", "FY2028E", "FY2029E", "FY2030E", "Source / rationale"])
    r += 1
    TS = ["C", "D", "E", "F", "G"]

    def tsrow(key, text, values, src):
        nonlocal r
        I[key] = r
        label(ws_in, r, text, indent=1)
        for col, v in zip(TS, values):
            style_value(ws_in[f"{col}{r}"], v, "pct", key=True)
        source(ws_in, r, 8, src)
        r += 1

    tsrow("g_na", "Revenue growth: North America", [0.07, 0.07, 0.06, 0.05, 0.04],
          "1H26 +7.1%. Slowing from +17.2% (FY24), +11.7% (FY25)")
    tsrow("g_korea", "Revenue growth: Korea (incl. Commax)", [0.0, 0.03, 0.03, 0.03, 0.03],
          "1H26 flat even with Commax consolidated")
    tsrow("g_russia", "Revenue growth: Russia", [0.0] * 5, "FY23 to FY25 CAGR +0.1%, sanctions risk")
    tsrow("g_china", "Revenue growth: China", [-0.05] * 5, "FY23 to FY25 CAGR -12.1%")
    tsrow("g_other", "Revenue growth: Other overseas", [0.20, 0.15, 0.12, 0.10, 0.08], "FY23 to FY25 CAGR +31.4%, small base")
    tsrow("capex_pct", "Capex / revenue", [0.07, 0.05, 0.045, 0.045, 0.045],
          "1H26 8.1%. Seotan expansion completed Jul 2026. Pre-expansion FY23: 5.4%")
    ws_in.column_dimensions["A"].width = 44
    ws_in.column_dimensions["B"].width = 13
    for col in TS:
        ws_in.column_dimensions[col].width = 10
    ws_in.column_dimensions["H"].width = 90

    # ======================= Model =======================
    title(ws_m, "Three-statement model (KRW bn)",
          "FY2025A from Historical. FY2026E onward driven by Inputs. Simplified balance sheet: other net assets and debt held flat.")
    MC = ["B", "C", "D", "E", "F", "G"]  # FY2025A, FY2026E..FY2030E
    header(ws_m, 4, ["KRW bn", "FY2025A", "FY2026E", "FY2027E", "FY2028E", "FY2029E", "FY2030E", "Note"])
    r = 5
    PROJ = MC[1:]

    def mrow(key, text, first, template, fmt="bn", bold=False, indent=1, note="", cols=None):
        """first: formula for FY2025A (or None). template: projection formula using {c} (this col), {p} (prior col)."""
        nonlocal r
        M[key] = r
        label(ws_m, r, text, bold=bold, indent=indent)
        if first is not None:
            style_value(ws_m[f"B{r}"], first, fmt)
        for col in (cols or PROJ):
            prev = MC[MC.index(col) - 1]
            style_value(ws_m[f"{col}{r}"], template.format(c=col, p=prev, **{k: v for k, v in {**M.rows}.items()}), fmt)
        if note:
            source(ws_m, r, 8, note)
        r += 1

    def inp(key, col=None):
        return f"Inputs!${'B' if col is None else col}${I[key]}"

    section(ws_m, r, "Income statement", 8); r += 1
    for key, text, gkey in [("rev_na", "Revenue: North America", "g_na"), ("rev_korea", "Revenue: Korea", "g_korea"),
                            ("rev_russia", "Revenue: Russia", "g_russia"), ("rev_china", "Revenue: China", "g_china"),
                            ("rev_other", "Revenue: Other overseas", "g_other")]:
        M[key] = r
        label(ws_m, r, text, indent=1)
        style_value(ws_m[f"B{r}"], f"=Historical!D{H[key]}", "bn")
        for col in PROJ:
            prev = MC[MC.index(col) - 1]
            style_value(ws_m[f"{col}{r}"], f"={prev}{r}*(1+Inputs!{col}{I[gkey]})", "bn")
        r += 1
    mrow("revenue", "Total revenue", f"=SUM(B{M['rev_na']}:B{M['rev_other']})",
         "=SUM({c}" + str(M["rev_na"]) + ":{c}" + str(M["rev_other"]) + ")", bold=True, indent=0)
    mrow("growth", "Revenue growth", None, "={c}{revenue}/{p}{revenue}-1", fmt="pct")
    M["op"] = r
    label(ws_m, r, "Operating profit", bold=True)
    style_value(ws_m[f"B{r}"], f"=Historical!D{H['op']}", "bn")
    style_value(ws_m[f"C{r}"], f"=Historical!F{H['op']}+(C{M['revenue']}-Historical!F{H['revenue_is']})*{inp('opm_2h26')}", "bn")
    for col in MC[2:]:
        style_value(ws_m[f"{col}{r}"], f"={col}{M['revenue']}*{inp('opm_lt')}", "bn")
    source(ws_m, r, 8, "FY26E = 1H26 actual + 2H26 revenue x 2H margin")
    r += 1
    mrow("opm", "Operating margin", f"=B{M['op']}/B{M['revenue']}", "={c}{op}/{c}{revenue}", fmt="pct")
    mrow("da", "D&A", f"=Historical!D{H['da']}", "={c}{revenue}*" + inp("da_pct"))
    mrow("ebitda", "EBITDA", f"=B{M['op']}+B{M['da']}", "={c}{op}+{c}{da}", bold=True, indent=0)
    M["gross_debt"] = r + 17  # placeholder, fixed below once rows are known (see balance sheet section)
    r_int = r
    r += 1  # net interest row filled after balance sheet rows exist
    mrow("pbt", "Profit before tax", f"=Historical!D{H['pbt']}", "={c}{op}-{c}" + str(r_int))
    mrow("tax", "Income tax", f"=Historical!D{H['tax']}", "={c}{pbt}*" + inp("tax"))
    mrow("ni", "Net income", f"=Historical!D{H['ni']}", "={c}{pbt}-{c}{tax}", bold=True, indent=0,
         note="Minority share of Commax ignored (NCI 1% of equity)")
    mrow("eps", "EPS (KRW)", f"=B{M['ni']}*1000000000/{inp('shares')}", "={c}{ni}*1000000000/" + inp("shares"), fmt="won")
    mrow("dps", "DPS (KRW)", f"={inp('dps')}", "=" + inp("dps"), fmt="won")
    mrow("div", "Dividends", None, "={c}{dps}*" + inp("shares") + "/1000000000")
    mrow("roe", "ROE (on opening equity)", None, "=0", fmt="pct")  # formula set once the equity row exists

    section(ws_m, r, "Balance sheet (year end, simplified)", 8); r += 1
    bs_start = r
    M["cash"] = r; r += 1
    M["nwc"] = r; r += 1
    M["nfa"] = r; r += 1
    M["other"] = r; r += 1
    M["net_assets"] = r; r += 1
    M["gross_debt"] = r; r += 1
    M["equity"] = r; r += 1
    M["bs_check"] = r; r += 1

    section(ws_m, r, "Cash flow statement", 8); r += 1
    M["cf_ni"] = r; r += 1
    M["cf_da"] = r; r += 1
    M["cf_dnwc"] = r; r += 1
    M["cf_cfo"] = r; r += 1
    M["capex"] = r; r += 1
    M["acq"] = r; r += 1
    M["cf_div"] = r; r += 1
    M["cf_debt"] = r; r += 1
    M["cf_net"] = r; r += 1

    # net interest (needs balance sheet rows)
    label(ws_m, r_int, "Net interest expense", indent=1)
    style_value(ws_m[f"B{r_int}"], f"=Historical!D{H['op']}-Historical!D{H['pbt']}", "bn")
    for col in PROJ:
        prev = MC[MC.index(col) - 1]
        style_value(ws_m[f"{col}{r_int}"],
                    f"={prev}{M['gross_debt']}*{inp('kd')}-{prev}{M['cash']}*{inp('rf')}", "bn")
    source(ws_m, r_int, 8, "Opening debt x cost of debt - opening cash x risk-free. FY25A: OP - PBT (incl. other items)")
    # ROE formula now that the equity row exists
    for col in PROJ:
        prev = MC[MC.index(col) - 1]
        ws_m[f"{col}{M['roe']}"].value = f"={col}{M['ni']}/{prev}{M['equity']}"

    def put(key, text, first, template, fmt="bn", bold=False, indent=1, note="", cols=None):
        row = M[key]
        label(ws_m, row, text, bold=bold, indent=indent)
        if first is not None:
            style_value(ws_m[f"B{row}"], first, fmt)
        for col in (cols or PROJ):
            prev = MC[MC.index(col) - 1]
            style_value(ws_m[f"{col}{row}"], template.format(c=col, p=prev, **M.rows), fmt)
        if note:
            source(ws_m, row, 8, note)

    put("cash", "Cash and deposits", f"=Historical!D{H['cash_dep']}", "={p}{cash}+{c}{cf_net}", note="Plug from cash flow")
    put("nwc", "Net working capital", f"=Historical!D{H['nwc']}", "={c}{revenue}*" + inp("nwc_pct"))
    put("nfa", "Net fixed assets", f"=Historical!D{H['nfa']}", "={p}{nfa}+{c}{capex}-{c}{da}")
    put("other", "Other net assets", f"=B{M['gross_debt']}+B{M['equity']}-B{M['cash']}-B{M['nwc']}-B{M['nfa']}",
        "={p}{other}+{c}{acq}", note="FY25A balancing item from reported totals. Grows only by acquisitions")
    put("net_assets", "Total net assets", f"=SUM(B{M['cash']}:B{M['other']})",
        "=SUM({c}" + str(M["cash"]) + ":{c}" + str(M["other"]) + ")", bold=True, indent=0)
    put("gross_debt", "Gross debt", f"=Historical!D{H['gross_debt']}", "={p}{gross_debt}+{c}{cf_debt}")
    put("equity", "Total equity", f"=Historical!D{H['equity']}", "={p}{equity}+{c}{ni}-{c}{div}")
    put("bs_check", "Check: net assets - debt - equity (must be 0)",
        f"=B{M['net_assets']}-B{M['gross_debt']}-B{M['equity']}", "={c}{net_assets}-{c}{gross_debt}-{c}{equity}")

    put("cf_ni", "Net income", None, "={c}{ni}")
    put("cf_da", "Add: D&A", None, "={c}{da}")
    put("cf_dnwc", "Less: increase in net working capital", None, "=-({c}{nwc}-{p}{nwc})")
    put("cf_cfo", "Cash flow from operations", None, "={c}{cf_ni}+{c}{cf_da}+{c}{cf_dnwc}", bold=True, indent=0)
    put("capex", "Capex", f"=Historical!D{H['capex']}", "={c}{revenue}*Inputs!{c}" + str(I["capex_pct"]))
    put("acq", "Acquisitions", None, "=0")
    style_value(ws_m[f"C{M['acq']}"], f"={inp('acq')}", "bn")
    put("cf_div", "Dividends paid", None, "={c}{div}")
    put("cf_debt", "Net borrowing", None, "=0", note="Debt held flat")
    put("cf_net", "Net change in cash", None, "={c}{cf_cfo}-{c}{capex}-{c}{acq}-{c}{cf_div}+{c}{cf_debt}",
        bold=True, indent=0)
    ws_m.column_dimensions["A"].width = 44
    for col in MC:
        ws_m.column_dimensions[col].width = 11
    ws_m.column_dimensions["H"].width = 70
    ws_m.freeze_panes = "B5"

    # ======================= DCF =======================
    title(ws_d, "DCF valuation (FCFF, KRW bn)",
          "Valuation date 30 Jun 2026 (latest balance sheet). Cash flows from 2H2026. Mid-period discounting.")
    r = 4
    header(ws_d, r, ["Cost of capital", "Value", "", "", "", "", "Note"]); r += 1

    def drow(key, text, value, fmt, note="", bold=False, key_fill=False):
        nonlocal r
        D[key] = r
        label(ws_d, r, text, bold=bold, indent=0 if bold else 1)
        style_value(ws_d[f"B{r}"], value, fmt, key=key_fill)
        if note:
            source(ws_d, r, 7, note)
        r += 1

    drow("mcap", "Market cap", f"={inp('price')}*{inp('shares')}/1000000000", "bn", "Price x shares outstanding")
    drow("debt", "Gross debt, 30 Jun 2026", f"=Historical!F{H['gross_debt']}", "bn")
    drow("de", "Debt / equity", f"=B{D['debt']}/B{D['mcap']}", "dec")
    drow("beta_l", "Levered beta", f"={inp('beta_u')}*(1+(1-{inp('t_marg')})*B{D['de']})", "dec",
         "Unlevered beta x (1 + (1 - t) x D/E)")
    drow("ke", "Cost of equity", f"={inp('rf')}+B{D['beta_l']}*{inp('erp')}", "pct2", "CAPM")
    drow("kd_at", "After-tax cost of debt", f"={inp('kd')}*(1-{inp('t_marg')})", "pct2")
    drow("we", "Equity weight", f"=B{D['mcap']}/(B{D['mcap']}+B{D['debt']})", "pct")
    drow("wacc", "WACC", f"=B{D['we']}*B{D['ke']}+(1-B{D['we']})*B{D['kd_at']}", "pct2", bold=True, key_fill=True)
    r += 1

    DC = ["B", "C", "D", "E", "F"]  # 2H2026E, FY2027E..FY2030E
    MODEL_COL = {"B": "C", "C": "D", "D": "E", "E": "F", "F": "G"}
    D["fcff_header"] = r
    header(ws_d, r, ["Free cash flow to firm", "2H2026E", "FY2027E", "FY2028E", "FY2029E", "FY2030E", "Note"]); r += 1

    def frow(key, text, first, template, fmt="bn", bold=False, note=""):
        nonlocal r
        D[key] = r
        label(ws_d, r, text, bold=bold, indent=0 if bold else 1)
        style_value(ws_d[f"B{r}"], first, fmt)
        for col in DC[1:]:
            prev = DC[DC.index(col) - 1]
            style_value(ws_d[f"{col}{r}"], template.format(c=col, p=prev, m=MODEL_COL[col],
                                                           pm=MODEL_COL[prev], **D.rows), fmt)
        if note:
            source(ws_d, r, 7, note)
        r += 1

    frow("rev", "Revenue", f"=Model!C{M['revenue']}-Historical!F{H['revenue_is']}", "=Model!{m}" + str(M["revenue"]),
         note="2H26 = FY26E - 1H26 actual")
    frow("ebit", "EBIT (operating profit)", f"=Model!C{M['op']}-Historical!F{H['op']}", "=Model!{m}" + str(M["op"]))
    frow("tax", "Less: tax on EBIT", f"=-B{r-1}*{inp('tax')}", "=-{c}{ebit}*" + inp("tax"))
    frow("nopat", "NOPAT", f"=B{D['ebit']}+B{D['tax']}", "={c}{ebit}+{c}{tax}", bold=True)
    frow("da", "Add: D&A", f"=Model!C{M['da']}-Historical!F{H['da']}", "=Model!{m}" + str(M["da"]))
    frow("capex", "Less: capex", f"=-(Model!C{M['capex']}-Historical!F{H['capex']})", "=-Model!{m}" + str(M["capex"]))
    frow("dnwc", "Less: increase in net working capital", f"=-(Model!C{M['nwc']}-Historical!F{H['nwc']})",
         "=-(Model!{m}" + str(M["nwc"]) + "-Model!{pm}" + str(M["nwc"]) + ")",
         note="2H26 vs 30 Jun 2026 actual NWC")
    frow("fcff", "Free cash flow to firm", f"=B{D['nopat']}+B{D['da']}+B{D['capex']}+B{D['dnwc']}",
         "={c}{nopat}+{c}{da}+{c}{capex}+{c}{dnwc}", bold=True)
    D["t"] = r
    label(ws_d, r, "Discount period, mid-point (years from 30 Jun 2026)", indent=1)
    for col, t in zip(DC, [0.25, 1.0, 2.0, 3.0, 4.0]):
        style_value(ws_d[f"{col}{r}"], t, "yr")
    source(ws_d, r, 7, "2H26 mid-point 0.25y, then full years centred at 1.0, 2.0, 3.0, 4.0")
    r += 1
    frow("df", "Discount factor", f"=1/(1+$B${D['wacc']})^B{D['t']}", "=1/(1+$B$" + str(D["wacc"]) + ")^{c}" + str(D["t"]),
         fmt="dec")
    frow("pv", "PV of FCFF", f"=B{D['fcff']}*B{D['df']}", "={c}{fcff}*{c}{df}")
    D["rev_lt"] = r
    label(ws_d, r, "Memo: revenue at long-term margin (for sensitivity)", indent=1)
    style_value(ws_d[f"B{r}"], "=0", "bn")
    for col in DC[1:]:
        style_value(ws_d[f"{col}{r}"], f"={col}{D['rev']}", "bn")
    r += 2

    header(ws_d, r, ["Valuation", "Value", "", "", "", "", "Note"]); r += 1
    drow("sum_pv", "Sum of PV of FCFF", f"=SUM(B{D['pv']}:F{D['pv']})", "bn")
    drow("tv", "Terminal value at end FY2030", f"=F{D['fcff']}*(1+{inp('g')})/(B{D['wacc']}-{inp('g')})", "bn",
         "FCFF FY2030 x (1 + g) / (WACC - g)")
    drow("tv_t", "Terminal discount period (years)", 4.5, "yr", "End of FY2030 = 4.5 years after 30 Jun 2026")
    drow("pv_tv", "PV of terminal value", f"=B{D['tv']}/(1+B{D['wacc']})^B{D['tv_t']}", "bn")
    drow("ev", "Enterprise value", f"=B{D['sum_pv']}+B{D['pv_tv']}", "bn", bold=True)
    drow("tv_share", "Terminal value as % of EV", f"=B{D['pv_tv']}/B{D['ev']}", "pct")
    drow("net_debt", "Less: net debt, 30 Jun 2026", f"=Historical!F{H['net_debt']}", "bn")
    drow("nci", "Less: non-controlling interests, 30 Jun 2026", f"=Historical!F{H['nci']}", "bn")
    drow("eq_value", "Equity value", f"=B{D['ev']}-B{D['net_debt']}-B{D['nci']}", "bn", bold=True)
    drow("per_share", "Equity value per share (KRW)", f"=B{D['eq_value']}*1000000000/{inp('shares')}", "won", bold=True, key_fill=True)
    drow("price", "Current price (KRW)", f"={inp('price')}", "won")
    drow("upside", "Upside / (downside)", f"=B{D['per_share']}/B{D['price']}-1", "pct", bold=True)
    drow("rating", "Rating", f'=IF(B{D["upside"]}>{inp("upside_band")},"Overweight",IF(B{D["upside"]}<-{inp("upside_band")},"Underweight","Neutral"))',
         "text", bold=True)
    drow("ev_ebitda_26", "Implied EV / EBITDA FY2026E", f"=B{D['ev']}/Model!C{M['ebitda']}", "x")
    drow("ev_ebitda_27", "Implied EV / EBITDA FY2027E", f"=B{D['ev']}/Model!D{M['ebitda']}", "x")
    drow("pe_27", "Implied P/E FY2027E", f"=B{D['eq_value']}/Model!D{M['ni']}", "x")
    drow("tv_mult", "Implied terminal EV / EBITDA (FY2030)", f"=B{D['tv']}/Model!G{M['ebitda']}", "x",
         "Sanity check on the Gordon growth terminal value")
    r += 1

    # ---- sensitivity 1: WACC x g ----
    fc = f"$B${D['fcff']}:$F${D['fcff']}"
    tt = f"$B${D['t']}:$F${D['t']}"
    bridge = f"-$B${D['net_debt']}-$B${D['nci']}"
    shares = inp("shares")
    D["sens1"] = r
    label(ws_d, r, "Sensitivity: value per share (KRW), WACC (rows) x terminal growth (columns)", bold=True); r += 1
    g_vals = [0.01, 0.015, 0.02, 0.025, 0.03]
    w_vals = [0.069, 0.074, 0.079, 0.084, 0.089]
    for j, gv in enumerate(g_vals):
        style_value(ws_d.cell(row=r, column=2 + j), gv, "pct")
    ghead = r; r += 1
    for wv in w_vals:
        style_value(ws_d[f"A{r}"], wv, "pct2")
        for j in range(len(g_vals)):
            gc = f"{get_column_letter(2 + j)}${ghead}"
            w = f"$A{r}"
            formula = (f"=(SUMPRODUCT({fc}/(1+{w})^{tt})+$F${D['fcff']}*(1+{gc})/({w}-{gc})/(1+{w})^$B${D['tv_t']}"
                       f"{bridge})*1000000000/{shares}")
            style_value(ws_d.cell(row=r, column=2 + j), formula, "won")
        r += 1
    source(ws_d, ghead, 7, "Base case WACC and g sit near the centre. Rows are WACC.")
    r += 1

    # ---- sensitivity 2: long-term operating margin x WACC ----
    D["sens2"] = r
    label(ws_d, r, "Sensitivity: value per share (KRW), long-term operating margin (rows) x WACC (columns)", bold=True); r += 1
    for j, wv in enumerate(w_vals):
        style_value(ws_d.cell(row=r, column=2 + j), wv, "pct2")
    whead = r; r += 1
    rl = f"$B${D['rev_lt']}:$F${D['rev_lt']}"
    tax = inp("tax")
    opm = inp("opm_lt")
    g = inp("g")
    for mv in [0.085, 0.095, 0.105, 0.115, 0.125]:
        style_value(ws_d[f"A{r}"], mv, "pct")
        for j in range(len(w_vals)):
            w = f"{get_column_letter(2 + j)}${whead}"
            m = f"$A{r}"
            adj_last = f"($F${D['fcff']}+$F${D['rev_lt']}*({m}-{opm})*(1-{tax}))"
            formula = (f"=(SUMPRODUCT(({fc}+{rl}*({m}-{opm})*(1-{tax}))/(1+{w})^{tt})"
                       f"+{adj_last}*(1+{g})/({w}-{g})/(1+{w})^$B${D['tv_t']}{bridge})*1000000000/{shares}")
            style_value(ws_d.cell(row=r, column=2 + j), formula, "won")
        r += 1
    source(ws_d, whead, 7, "Margin applies from FY2027E. 2H2026E is fixed. FY23 to FY25 margins: 8.8% to 9.8%")
    ws_d.column_dimensions["A"].width = 52
    for col in DC:
        ws_d.column_dimensions[col].width = 12
    ws_d.column_dimensions["G"].width = 60

    # ======================= Comps =======================
    title(ws_c, "Trading comparables",
          f"Peer data: {peers['source']}, fetched {peers['fetched_at'][:10]}. Local currency, millions. "
          "Multiples are computed here from raw values.")
    header(ws_c, 4, ["Company", "Ticker", "Currency", "Market cap (m)", "EV (m)", "EBITDA TTM (m)", "Net income TTM (m)",
                     "EV/EBITDA", "P/E TTM", "P/E fwd", "P/B", "ROE", "Op. margin"])
    r = 5
    first = r
    for p in peers["peers"]:
        ws_c[f"A{r}"] = p["name"]
        ws_c[f"B{r}"] = p["ticker"]
        ws_c[f"C{r}"] = p["currency"]
        for col, k in [("D", "marketCap"), ("E", "enterpriseValue"), ("F", "ebitda"), ("G", "netIncomeToCommon")]:
            style_value(ws_c[f"{col}{r}"], round(p[k] / 1e6, 1), "num")
        style_value(ws_c[f"H{r}"], f"=E{r}/F{r}", "x")
        style_value(ws_c[f"I{r}"], f"=D{r}/G{r}", "x")
        for col, k, fmt in [("J", "forwardPE", "x"), ("K", "priceToBook", "x"), ("L", "returnOnEquity", "pct"),
                            ("M", "operatingMargins", "pct")]:
            if p[k] is None:
                ws_c[f"{col}{r}"] = "n/a"
            else:
                style_value(ws_c[f"{col}{r}"], round(p[k], 4), fmt)
        for col in "ABC":
            ws_c[f"{col}{r}"].font = Font(name=FONT, size=10)
        r += 1
    last = r - 1
    C["median"] = r
    label(ws_c, r, "Peer median", bold=True)
    for col, fmt in [("H", "x"), ("I", "x"), ("J", "x"), ("K", "x"), ("L", "pct"), ("M", "pct")]:
        style_value(ws_c[f"{col}{r}"], f"=MEDIAN({col}{first}:{col}{last})", fmt)
    r += 2

    label(ws_c, r, "Kyung Dong Navien (KRW bn)", bold=True); r += 1
    rows_c = {}

    def crow(key, text, formula, fmt, note=""):
        nonlocal r
        rows_c[key] = r
        label(ws_c, r, text, indent=1)
        style_value(ws_c[f"B{r}"], formula, fmt)
        if note:
            source(ws_c, r, 3, note)
        r += 1

    crow("mcap", "Market cap", f"=DCF!B{D['mcap']}", "bn")
    crow("ev", "Enterprise value", f"=B{rows_c['mcap']}+Historical!F{H['net_debt']}+Historical!F{H['nci']}", "bn",
         "Market cap + net debt + NCI, 30 Jun 2026")
    crow("ebitda_ltm", "EBITDA, LTM to 1H2026",
         f"=Historical!D{H['op']}+Historical!D{H['da']}-(Historical!E{H['op']}+Historical!E{H['da']})"
         f"+Historical!F{H['op']}+Historical!F{H['da']}", "bn",
         "FY2025 - 1H2025 + 1H2026. Includes undisclosed US tariff refunds in 1H2026")
    crow("ni_ltm", "Net income to parent, LTM",
         f"=Historical!D{H['ni_parent']}-Historical!E{H['ni_parent']}+Historical!F{H['ni_parent']}", "bn")
    crow("ev_ebitda", "EV / EBITDA, LTM", f"=B{rows_c['ev']}/B{rows_c['ebitda_ltm']}", "x")
    crow("pe", "P/E, LTM", f"=B{rows_c['mcap']}/B{rows_c['ni_ltm']}", "x")
    crow("pe_fwd", "P/E, FY2027E (model)", f"=B{rows_c['mcap']}/Model!D{M['ni']}", "x",
         "FY2027E is the first year with no tariff refund assumed")
    crow("pb", "P/B, 30 Jun 2026", f"=B{rows_c['mcap']}/Historical!F{H['eq_parent']}", "x")
    r += 1
    label(ws_c, r, "Implied value per share at peer median (KRW)", bold=True); r += 1
    crow("imp_ev_ebitda", "At median EV / EBITDA (LTM)",
         f"=(H{C['median']}*B{rows_c['ebitda_ltm']}-Historical!F{H['net_debt']}-Historical!F{H['nci']})*1000000000/{shares}",
         "won", "Cross-check only, not blended into the target")
    crow("imp_pe", "At median P/E (LTM)", f"=I{C['median']}*B{rows_c['ni_ltm']}*1000000000/{shares}", "won")
    crow("imp_pe_fwd", "At median forward P/E on FY2027E net income", f"=J{C['median']}*Model!D{M['ni']}*1000000000/{shares}", "won")
    crow("dcf", "DCF value per share", f"=DCF!B{D['per_share']}", "won")
    ws_c.column_dimensions["A"].width = 44
    for col in "BCDEFGHIJKLM":
        ws_c.column_dimensions[col].width = 13

    # ======================= Cover =======================
    title(ws_cover, "Kyung Dong Navien (009450 KS): valuation model",
          "Built with src/build_model.py from DART filings. All outputs are live formulas.")
    rows = [
        ("Share price, 25 Sep 2026 (KRW)", f"={inp('price')}", "won"),
        ("DCF value per share (KRW)", f"=DCF!B{D['per_share']}", "won"),
        ("Upside / (downside)", f"=DCF!B{D['upside']}", "pct"),
        ("Rating", f"=DCF!B{D['rating']}", "text"),
        ("WACC", f"=DCF!B{D['wacc']}", "pct2"),
        ("Terminal growth", f"={inp('g')}", "pct"),
        ("Terminal value as % of EV", f"=DCF!B{D['tv_share']}", "pct"),
        ("Check: balance sheet balances (sum of abs. differences)", f"=SUMPRODUCT(ABS(Model!B{M['bs_check']}:G{M['bs_check']}))", "bn"),
        ("Check: regional revenue ties to income statement", f"=SUMPRODUCT(ABS(Historical!B{H['rev_check']}:F{H['rev_check']}))", "bn"),
        ("Check: historical balance sheets balance", f"=SUMPRODUCT(ABS(Historical!B{H['bs_check']}:F{H['bs_check']}))", "bn"),
    ]
    r = 4
    header(ws_cover, r, ["Summary", "Value"]); r += 1
    for text, formula, fmt in rows:
        label(ws_cover, r, text, indent=1)
        style_value(ws_cover[f"B{r}"], formula, fmt)
        r += 1
    r += 1
    header(ws_cover, r, ["Legend", ""]); r += 1
    for text, color in [("Blue text: hardcoded input or reported figure", BLUE), ("Black text: formula", BLACK),
                        ("Green text: link to another sheet", GREEN)]:
        c = ws_cover.cell(row=r, column=1, value=text)
        c.font = Font(name=FONT, size=10, color=color)
        r += 1
    c = ws_cover.cell(row=r, column=1, value="Yellow fill: key assumption")
    c.fill = KEY_FILL
    c.font = Font(name=FONT, size=10)
    r += 2
    header(ws_cover, r, ["Sources", ""]); r += 1
    for text in ["DART OpenAPI (opendart.fss.or.kr): FY2025 annual report, 1H2026 half-year report, notes, filings",
                 "FinanceDataReader: KOSPI listing and prices, 25 Sep 2026",
                 "FRED IRLTLT01KRM156N: Korea 10-year government bond yield",
                 "Damodaran Online, Jan 2026: country risk premiums, global industry betas, synthetic ratings",
                 "Yahoo Finance via yfinance: peer market data (see Comps sheet for fetch date)"]:
        label(ws_cover, r, text, indent=1)
        r += 1
    ws_cover.column_dimensions["A"].width = 60
    ws_cover.column_dimensions["B"].width = 16

    # comment on the key judgement call
    ws_in[f"B{I['opm_2h26']}"].comment = Comment(
        "1H2026 cost of sales includes US tariff refunds (DART 1H2026 notes, expenses by nature). "
        "The amount is not disclosed, so 2H2026 uses the 2H2025 margin instead of the 1H2026 margin.", "Analyst")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT_PATH)
    return OUT_PATH


if __name__ == "__main__":
    print("Saved", build())

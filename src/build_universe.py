"""Phase 1: build the KOSPI screening universe and collect DART data.

Steps (row counts at each step go to outputs/data_quality_report.md):
  1. KOSPI listing from FinanceDataReader (cached)
  2. Keep common stocks only (code ends in "0")
  3. Drop SPACs, REITs and listed infrastructure funds (name rules below)
  4. Keep market cap >= MIN_MARKET_CAP_KRW (common + preferred market cap)
  5. Pull DART: company info, FY financials, dividends, Value-Up disclosures
  6. Drop EPS <= 0 or BPS <= 0 (i.e. parent net income <= 0 or parent equity <= 0)
  7. Flag financials (banks, insurance, securities, cards, financial holding companies)

Output: data/processed/universe.csv
"""

import pandas as pd

import dart_data
from config import (ANNUAL_REPORT_CODE, FISCAL_YEAR, LISTING_DATE, MIN_MARKET_CAP_KRW,
                    OUTPUT_DIR, PROCESSED_DIR, RAW_DIR, VALUEUP_END, VALUEUP_KEYWORD,
                    VALUEUP_PREVIEW_KEYWORD, VALUEUP_START)

NET_INCOME_PARENT_ID = "ifrs-full_ProfitLossAttributableToOwnersOfParent"
EQUITY_PARENT_ID = "ifrs-full_EquityAttributableToOwnersOfParent"
NET_INCOME_ID = "ifrs-full_ProfitLoss"
EQUITY_ID = "ifrs-full_Equity"
NET_INCOME_PARENT_ALT_ID = "ifrs-full_ProfitLossAttributableToOrdinaryEquityHoldersOfParentEntity"
NCI_ID = "ifrs-full_NoncontrollingInterests"
COMMON_SHARE_LABELS = ["보통주", "보통주식", "의결권 있는 주식", "-"]  # in priority order


# ---------- name-based exclusions ----------

def is_spac(name):
    return "스팩" in name


def is_reit(name):
    # "메리츠금융지주" contains "리츠" but is a financial holding company, not a REIT
    return "리츠" in name and not name.startswith("메리츠")


def is_infra_fund(name):
    return name in ["맥쿼리인프라", "KB발해인프라"]


# ---------- financial sector flag ----------

def is_financial(induty_code, name):
    """KSIC-based flag.

    64 (financial services), 65 (insurance), 66 (auxiliary finance) are financial,
    EXCEPT 64992 (holding companies), which covers LG, SK, GS etc. A 64992 company
    counts as financial only if its name says it is a financial holding ("금융").
    """
    code = str(induty_code)
    if code.startswith("64992"):
        return "금융" in name
    return code[:2] in ["64", "65", "66"]


# ---------- DART field extraction ----------

def to_number(value):
    if value is None or pd.isna(value):
        return None
    text = str(value).replace(",", "").strip()
    if text in ["", "-", "nan", "None"]:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def pick_amount(fs, statements, account_id, col="thstrm_amount"):
    """Amount for account_id from the first statement type that has it.

    col="thstrm_amount" is the current fiscal year, "frmtrm_amount" the prior year
    (as restated in the current annual report).
    """
    if col not in fs.columns:  # e.g. a newly listed company has no prior-year column
        return None
    for sj in statements:
        rows = fs[(fs["sj_div"] == sj) & (fs["account_id"] == account_id)]
        if len(rows) > 0:
            return to_number(rows.iloc[0][col])
    return None


def extract_financials(stock_code):
    """Parent NI and equity for FY and FY-1. CFS first; OFS if no consolidated statements."""
    for fs_div in ["CFS", "OFS"]:
        fs = dart_data.financial_statements(stock_code, FISCAL_YEAR, ANNUAL_REPORT_CODE, fs_div)
        if fs.empty:
            continue
        currency = ",".join(sorted(fs["currency"].dropna().unique())) if "currency" in fs else None
        if fs_div == "OFS":
            # Separate statements have no minority interest, so total = parent
            return {"fs_div": fs_div, "currency": currency, "fin_rule": "OFS totals",
                    "net_income_parent": pick_amount(fs, ["IS", "CIS"], NET_INCOME_ID),
                    "equity_parent": pick_amount(fs, ["BS"], EQUITY_ID),
                    "net_income_parent_prior": pick_amount(fs, ["IS", "CIS"], NET_INCOME_ID, "frmtrm_amount"),
                    "equity_parent_prior": pick_amount(fs, ["BS"], EQUITY_ID, "frmtrm_amount")}
        current = extract_parent_amounts(fs, "thstrm_amount")
        prior = extract_parent_amounts(fs, "frmtrm_amount")
        return {"fs_div": fs_div, "currency": currency, **current,
                "net_income_parent_prior": prior["net_income_parent"],
                "equity_parent_prior": prior["equity_parent"]}
    return {"fs_div": None, "currency": None, "fin_rule": None,
            "net_income_parent": None, "equity_parent": None,
            "net_income_parent_prior": None, "equity_parent_prior": None}


def extract_parent_amounts(fs, col):
    """Parent NI and equity from consolidated statements.

    Companies tag the same numbers differently, so we try, in order:
      1. Standard parent-attributable account IDs
      2. Alternate NI ID used by some filers (...OrdinaryEquityHoldersOfParentEntity)
      3. Parent equity = total equity - non-controlling interests (both reported)
      4. If parent equity equals total equity (no minority interest), parent NI = total NI
    Every value is a reported figure or an exact identity of reported figures.
    """
    rules = []
    ni = pick_amount(fs, ["IS", "CIS"], NET_INCOME_PARENT_ID, col)
    if ni is None:
        ni = pick_amount(fs, ["IS", "CIS"], NET_INCOME_PARENT_ALT_ID, col)
        if ni is not None:
            rules.append("alt NI id")

    eq = pick_amount(fs, ["BS"], EQUITY_PARENT_ID, col)
    total_eq = pick_amount(fs, ["BS"], EQUITY_ID, col)
    if eq is None and total_eq is not None:
        nci_rows = fs[(fs["sj_div"] == "BS") & (fs["account_id"] == NCI_ID)]
        if len(nci_rows) > 0:
            nci = to_number(nci_rows.iloc[0][col]) if col in fs.columns else None
            if nci is not None:
                eq = total_eq - nci
                rules.append("equity = total - NCI")
        else:
            # No non-controlling interest line on the balance sheet: all equity is the parent's
            eq = total_eq
            rules.append("no NCI line, equity = total")

    if ni is None and eq is not None and total_eq is not None and eq == total_eq:
        ni = pick_amount(fs, ["IS", "CIS"], NET_INCOME_ID, col)
        if ni is not None:
            rules.append("no NCI, NI = total NI")

    return {"fin_rule": "; ".join(rules) if rules else "standard",
            "net_income_parent": ni, "equity_parent": eq}


def extract_dividends(stock_code):
    """Common-stock DPS and reported payout ratio from the annual report dividend table."""
    dv = dart_data.dividends(stock_code, FISCAL_YEAR, ANNUAL_REPORT_CODE)
    out = {"dps_common": None, "eps_reported": None, "payout_reported_pct": None}
    if dv.empty:
        return out

    # Filers label the common-share row differently. "-" means the company has one share class.
    dps_all = dv[dv["se"].str.contains("주당 현금배당금", na=False)].copy()
    dps_all["knd"] = dps_all["stock_knd"].astype(str).str.strip()
    dps_rows = dps_all.iloc[0:0]
    for label in COMMON_SHARE_LABELS:
        dps_rows = dps_all[dps_all["knd"] == label]
        if len(dps_rows) > 0:
            break
    if len(dps_rows) > 0:
        out["dps_common"] = to_number(dps_rows.iloc[0]["thstrm"])

    eps_rows = dv[dv["se"].str.contains("주당순이익", na=False)]
    if len(eps_rows) > 0:
        out["eps_reported"] = to_number(eps_rows.iloc[0]["thstrm"])

    payout_rows = dv[dv["se"].str.contains("현금배당성향", na=False)]
    if len(payout_rows) > 0:
        out["payout_reported_pct"] = to_number(payout_rows.iloc[0]["thstrm"])

    # A company that paid nothing reports "-", which is a real zero, not missing data
    if out["dps_common"] is None and len(dps_rows) > 0:
        out["dps_common"] = 0.0
    if out["dps_common"] == 0.0 and out["payout_reported_pct"] is None:
        out["payout_reported_pct"] = 0.0
    return out


def extract_valueup(stock_code):
    df = dart_data.disclosures(stock_code, VALUEUP_START, VALUEUP_END)
    out = {"valueup_plan": False, "valueup_first_plan_date": None,
           "valueup_first_preview_date": None, "valueup_filings": 0}
    if df.empty:
        return out

    hits = df[df["report_nm"].str.contains(VALUEUP_KEYWORD, na=False)]
    out["valueup_filings"] = len(hits)
    previews = hits[hits["report_nm"].str.contains(VALUEUP_PREVIEW_KEYWORD, na=False)]
    plans = hits[~hits["report_nm"].str.contains(VALUEUP_PREVIEW_KEYWORD, na=False)]

    if len(previews) > 0:
        out["valueup_first_preview_date"] = previews["rcept_dt"].min()
    if len(plans) > 0:
        out["valueup_plan"] = True
        out["valueup_first_plan_date"] = plans["rcept_dt"].min()
    return out


# ---------- main pipeline ----------

def main():
    steps = []  # (step description, rows remaining)

    listing = pd.read_csv(RAW_DIR / f"listing_KOSPI_{LISTING_DATE}.csv", dtype={"Code": str})
    steps.append(("KOSPI listing (FinanceDataReader)", len(listing)))

    # Market cap per company = common + all preferred lines sharing the first 5 code characters
    listing["company_key"] = listing["Code"].str[:5]
    total_mcap = listing.groupby("company_key")["Marcap"].sum().rename("mcap_total")

    df = listing[listing["Code"].str.endswith("0")].copy()
    steps.append(("Common stocks only (code ends in 0)", len(df)))

    dropped_names = {
        "SPAC": df[df["Name"].apply(is_spac)]["Name"].tolist(),
        "REIT": df[df["Name"].apply(is_reit)]["Name"].tolist(),
        "Infrastructure fund": df[df["Name"].apply(is_infra_fund)]["Name"].tolist(),
    }
    df = df[~df["Name"].apply(is_spac)]
    steps.append(("Drop SPACs", len(df)))
    df = df[~df["Name"].apply(is_reit)]
    steps.append(("Drop REITs", len(df)))
    df = df[~df["Name"].apply(is_infra_fund)]
    steps.append(("Drop listed infrastructure funds", len(df)))

    df = df.join(total_mcap, on="company_key")
    df = df[df["mcap_total"] >= MIN_MARKET_CAP_KRW].copy()
    steps.append((f"Market cap >= KRW {MIN_MARKET_CAP_KRW / 1e9:,.0f}bn", len(df)))

    records = []
    for i, row in enumerate(df.itertuples(index=False), start=1):
        code = row.Code
        print(f"[{i}/{len(df)}] {code} {row.Name}", flush=True)
        info = dart_data.company_info(code)
        rec = {
            "code": code,
            "name": row.Name,
            "name_eng": info.get("corp_name_eng"),
            "price": row.Close,
            "shares_common": row.Stocks,
            "mcap_common": row.Marcap,
            "mcap_total": row.mcap_total,
            "corp_code": info.get("corp_code"),
            "induty_code": info.get("induty_code"),
            "fiscal_month": info.get("acc_mt"),
        }
        rec.update(extract_financials(code))
        rec.update(extract_dividends(code))
        rec.update(extract_valueup(code))
        records.append(rec)

    uni = pd.DataFrame(records)
    uni["is_financial"] = [is_financial(c, n) for c, n in zip(uni["induty_code"], uni["name"])]

    # Missing values BEFORE the profitability filter, so gaps are visible, not silently dropped
    missing = uni[["corp_code", "induty_code", "fs_div", "net_income_parent", "equity_parent",
                   "dps_common", "payout_reported_pct"]].isna().sum()
    no_financials = uni[uni["net_income_parent"].isna() | uni["equity_parent"].isna()][["code", "name", "fs_div"]]
    non_dec_fy = uni[uni["fiscal_month"] != "12"][["code", "name", "fiscal_month"]]

    has_data = uni["net_income_parent"].notna() & uni["equity_parent"].notna()
    uni_ok = uni[has_data].copy()
    steps.append(("DART FY financials available", len(uni_ok)))

    # Market cap is in KRW, so financials reported in another currency would give a wrong P/B
    non_krw = uni_ok[uni_ok["currency"] != "KRW"][["code", "name", "currency"]]
    uni_ok = uni_ok[uni_ok["currency"] == "KRW"].copy()
    steps.append(("Financials reported in KRW", len(uni_ok)))

    uni_ok = uni_ok[(uni_ok["net_income_parent"] > 0) & (uni_ok["equity_parent"] > 0)].copy()
    steps.append(("Drop EPS <= 0 or BPS <= 0", len(uni_ok)))

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    uni.to_csv(PROCESSED_DIR / "universe_all_pulled.csv", index=False)
    uni_ok.to_csv(PROCESSED_DIR / "universe.csv", index=False)

    write_report(steps, dropped_names, missing, no_financials, non_krw, non_dec_fy, uni_ok)
    print("\nDone. Rows in final universe:", len(uni_ok))


def write_report(steps, dropped_names, missing, no_financials, non_krw, non_dec_fy, uni_ok):
    lines = ["# Phase 1 data quality report", "",
             f"Listing date: {LISTING_DATE}. Financials: FY{FISCAL_YEAR} annual report (DART).", "",
             "## Rows at each filter step", "", "| Step | Rows |", "|---|---|"]
    lines += [f"| {s} | {n} |" for s, n in steps]

    lines += ["", "## Dropped by name rule", ""]
    for kind, names in dropped_names.items():
        lines.append(f"- {kind} ({len(names)}): {', '.join(names) if names else 'none'}")

    lines += ["", "## Missing values in pulled DART data (before profitability filter)", "",
              "| Field | Missing |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in missing.items()]

    lines += ["", "## Companies without usable FY financials (excluded)", ""]
    if no_financials.empty:
        lines.append("none")
    else:
        lines += [f"- {r.code} {r.name} (fs_div: {r.fs_div})" for r in no_financials.itertuples()]

    lines += ["", "## Financials not in KRW (excluded, no FX conversion)", ""]
    if non_krw.empty:
        lines.append("none")
    else:
        lines += [f"- {r.code} {r.name} ({r.currency})" for r in non_krw.itertuples()]

    lines += ["", "## Non-December fiscal year (kept, flagged)", ""]
    if non_dec_fy.empty:
        lines.append("none")
    else:
        lines += [f"- {r.code} {r.name} (fiscal month {r.fiscal_month})" for r in non_dec_fy.itertuples()]

    fin = uni_ok["is_financial"]
    lines += ["", "## Final universe composition", "",
              f"- Total: {len(uni_ok)}",
              f"- Financials: {int(fin.sum())}, non-financials: {int((~fin).sum())}",
              f"- Filed a Value-Up plan: {int(uni_ok['valueup_plan'].sum())}",
              f"- Consolidated (CFS): {int((uni_ok['fs_div'] == 'CFS').sum())}, "
              f"separate (OFS): {int((uni_ok['fs_div'] == 'OFS').sum())}"]

    (OUTPUT_DIR / "data_quality_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

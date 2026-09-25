"""Phase 2: ROE-justified P/B screen.

Variables (5): P/B, ROE, dividend yield, payout ratio, Value-Up plan flag.
  P/B          = (common + preferred market cap) / parent equity
  ROE          = parent net income / parent equity   (= EPS / BPS, same share count)
  div yield    = FY common DPS / current common price
  payout       = FY common DPS / FY consolidated EPS, both from the DART dividend table.
                 If EPS is not reported, DART's reported cash payout ratio is used instead.

Core model (non-financials only):
  log(P/B) = a + b * ROE_winsorized + sector fixed effects + e,  HC3 robust SEs
  residual e < 0 means the stock trades below the P/B its ROE and sector justify.

Sanity check: justified P/B = (ROE - g) / (COE - g) with one market-wide COE.

Outputs: data/processed/screen_results.csv, outputs/candidates.csv,
         outputs/regression_summary.txt, charts in outputs/charts/
"""

import json

import FinanceDataReader as fdr
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from config import CHART_DIR, OUTPUT_DIR, PROCESSED_DIR, RAW_DIR
from sectors import MIN_SECTOR_SIZE, sector_from_ksic

# ---------- justified P/B assumptions (sanity check only, not the DCF) ----------
KOREA_ERP_SOURCE = "Damodaran ctryprem.xlsx, Jan 2026 update, 'ERPs by country', Korea total ERP"
KOREA_10Y_SOURCE = "FRED IRLTLT01KRM156N (OECD), Korea 10Y government bond yield, latest month"
TERMINAL_G = 0.02  # Bank of Korea inflation target (2%), used as a long-run nominal growth proxy
BETA = 1.0         # market-average stock, by construction


def load_korea_erp():
    df = pd.read_excel(RAW_DIR / "reference" / "damodaran_ctryprem.xlsx",
                       sheet_name="ERPs by country", header=None)
    row = df[df[0] == "Korea"].iloc[0]
    return float(row[4])  # column 4 = Total Equity Risk Premium


def load_korea_10y():
    path = RAW_DIR / "reference" / "fred_korea_10y.csv"
    if not path.exists():
        fdr.DataReader("FRED:IRLTLT01KRM156N", "2024-01-01").to_csv(path)
    s = pd.read_csv(path, index_col=0)["IRLTLT01KRM156N"].dropna()
    return float(s.iloc[-1]) / 100, str(s.index[-1])[:7]


def winsorize(series, lower=0.01, upper=0.99):
    lo, hi = series.quantile(lower), series.quantile(upper)
    return series.clip(lo, hi)


def build_variables(uni):
    df = uni.copy()
    df["pb"] = df["mcap_total"] / df["equity_parent"]
    df["roe"] = df["net_income_parent"] / df["equity_parent"]
    # Prior-year ROE, used only to flag one-off or peak-cycle earnings (not in the model)
    df["roe_prior"] = df["net_income_parent_prior"] / df["equity_parent_prior"]
    df["roe_jump_pp"] = (df["roe"] - df["roe_prior"]) * 100
    df["div_yield"] = df["dps_common"] / df["price"]
    eps_ok = df["eps_reported"] > 0
    df["payout"] = (df["dps_common"] / df["eps_reported"]).where(eps_ok, df["payout_reported_pct"] / 100)
    df["log_pb"] = np.log(df["pb"])
    df["sector_raw"] = df["induty_code"].apply(sector_from_ksic)

    # Sectors with too few members are pooled into "Other", so no fixed effect is fitted
    # on one or two firms (a one-firm sector would get a residual of exactly zero)
    counts = df["sector_raw"].value_counts()
    small = counts[counts < MIN_SECTOR_SIZE].index
    df["sector"] = df["sector_raw"].where(~df["sector_raw"].isin(small), "Other")
    return df


def fit_model(df):
    df = df.copy()
    df["roe_w"] = winsorize(df["roe"])
    model = smf.ols("log_pb ~ roe_w + C(sector)", data=df).fit(cov_type="HC3")
    df["fitted_log_pb"] = model.fittedvalues
    df["residual"] = model.resid
    df["discount_pct"] = np.exp(df["residual"]) - 1  # actual P/B vs model P/B
    # Sector-adjusted log P/B: remove each sector's fixed effect, keep the ROE relationship.
    # Plotting this against ROE shows the model as one line; residual = vertical distance.
    df["sector_adj_log_pb"] = df["log_pb"] - (df["fitted_log_pb"] - model.params["Intercept"]
                                              - model.params["roe_w"] * df["roe_w"])

    # ROE-only model, used for the sector chart. With sector fixed effects every sector's mean
    # residual is zero by construction, so sector-level discounts show up only without them.
    pooled = smf.ols("log_pb ~ roe_w", data=df).fit(cov_type="HC3")
    df["residual_pooled"] = pooled.resid
    return model, df


def add_justified_pb(df, coe, g):
    df = df.copy()
    df["justified_pb"] = (df["roe"] - g) / (coe - g)
    df["pb_vs_justified"] = df["pb"] / df["justified_pb"] - 1
    return df


def pick_candidates(df):
    roe_median = df["roe"].median()
    payout_median = df["payout"].median()
    resid_cut = df["residual"].quantile(0.25)
    mask = ((df["residual"] <= resid_cut) & (df["roe"] > roe_median)
            & (df["payout"] < payout_median))
    cands = df[mask].sort_values("residual")
    cutoffs = {"residual_bottom_quartile": resid_cut, "roe_median": roe_median,
               "payout_median": payout_median}
    return cands, cutoffs


def main():
    uni = pd.read_csv(PROCESSED_DIR / "universe.csv", dtype={"code": str, "induty_code": str})
    df = build_variables(uni)

    missing_payout = df["payout"].isna().sum()
    nonfin = df[~df["is_financial"]].dropna(subset=["payout"]).copy()
    fin = df[df["is_financial"]].copy()

    model, nonfin = fit_model(nonfin)

    erp = load_korea_erp()
    rf, rf_month = load_korea_10y()
    coe = rf + BETA * erp
    nonfin = add_justified_pb(nonfin, coe, TERMINAL_G)
    fin = add_justified_pb(fin, coe, TERMINAL_G)

    # Sanity check: do the two methods agree on who looks cheap?
    valid = nonfin["justified_pb"] > 0
    rank_corr = nonfin.loc[valid, "residual"].corr(
        np.log(nonfin.loc[valid, "pb"] / nonfin.loc[valid, "justified_pb"]), method="spearman")

    cands, cutoffs = pick_candidates(nonfin)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    nonfin.to_csv(PROCESSED_DIR / "screen_results.csv", index=False)
    fin.to_csv(PROCESSED_DIR / "screen_financials.csv", index=False)
    cand_cols = ["code", "name", "name_eng", "sector", "pb", "roe", "roe_prior", "roe_jump_pp",
                 "div_yield", "payout", "valueup_plan",
                 "valueup_first_plan_date", "residual", "discount_pct", "justified_pb",
                 "mcap_total"]
    cands[cand_cols].to_csv(OUTPUT_DIR / "candidates.csv", index=False)

    (OUTPUT_DIR / "regression_summary.txt").write_text(str(model.summary()), encoding="utf-8")

    stats = {
        "n_nonfinancial": int(len(nonfin)),
        "n_financial": int(len(fin)),
        "dropped_missing_payout": int(missing_payout),
        "roe_coef": float(model.params["roe_w"]),
        "roe_se_hc3": float(model.bse["roe_w"]),
        "roe_pvalue": float(model.pvalues["roe_w"]),
        "r_squared": float(model.rsquared),
        "n_sectors": int(nonfin["sector"].nunique()),
        "rf": rf, "rf_month": rf_month, "erp": erp, "coe": coe, "g": TERMINAL_G,
        "rf_source": KOREA_10Y_SOURCE, "erp_source": KOREA_ERP_SOURCE,
        "justified_rank_corr": float(rank_corr),
        "n_candidates": int(len(cands)),
        "n_candidates_valueup": int(cands["valueup_plan"].sum()),
        "median_pb": float(nonfin["pb"].median()),
        "median_roe": float(nonfin["roe"].median()),
        "share_below_justified": float((nonfin.loc[valid, "pb"] < nonfin.loc[valid, "justified_pb"]).mean()),
        **{k: float(v) for k, v in cutoffs.items()},
    }
    (OUTPUT_DIR / "screen_stats.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")

    import charts
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    charts.pb_vs_roe(nonfin, cands, model)
    charts.residual_by_sector(nonfin)

    print(json.dumps(stats, indent=2))
    print("\nCandidates:")
    print(cands[["code", "name", "sector", "pb", "roe", "roe_prior", "payout", "valueup_plan",
                 "discount_pct"]].to_string(index=False))


if __name__ == "__main__":
    main()

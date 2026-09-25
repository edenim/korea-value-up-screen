"""Phase 3: event study around each company's first Value-Up plan disclosure.

Event day 0   = first trading day on or after the DART receipt date (rcept_dt).
               Filings made after the close move the price the next day; the [-1, +5]
               window covers that case.
Market model  = R_i = alpha + beta * R_KOSPI, estimated on trading days [-250, -30].
AR            = actual return - market model prediction.
CAR[-1, +5]   = sum of AR over the 7-day window.
Test          = cross-sectional t-stat of mean CAR (mean / (sd / sqrt(N))).

Preview notices (기업가치제고계획예고) are excluded: the event is the first actual plan.

Outputs: data/processed/event_study_car.csv, outputs/event_study_stats.json,
         outputs/charts/event_study_car.png
"""

import json
import time

import FinanceDataReader as fdr
import numpy as np
import pandas as pd

from config import API_SLEEP, CHART_DIR, OUTPUT_DIR, PROCESSED_DIR, RAW_DIR

EST_START, EST_END = -250, -30
WIN_START, WIN_END = -1, 5
MIN_EST_DAYS = 200
PRICE_START = "2023-01-01"
PRICE_END = "2026-09-25"


def cached_prices(symbol):
    folder = RAW_DIR / "prices"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{symbol}.csv"
    if path.exists():
        return pd.read_csv(path, index_col=0, parse_dates=True)
    df = fdr.DataReader(symbol, PRICE_START, PRICE_END)
    time.sleep(API_SLEEP)
    df.to_csv(path)
    return df


def event_car(stock_ret, market_ret, event_date):
    """Return (CAR, AR series by relative day) or (None, reason) if the event cannot be used."""
    data = pd.concat([stock_ret.rename("r"), market_ret.rename("m")], axis=1).dropna()
    dates = data.index
    pos = dates.searchsorted(event_date)  # first trading day on/after the filing date
    if pos >= len(dates):
        return None, "event after price data ends"
    if pos + EST_START < 0:
        return None, "not enough history for estimation window"
    if pos + WIN_END >= len(dates):
        return None, "event window runs past price data"

    est = data.iloc[pos + EST_START: pos + EST_END + 1]
    if len(est) < MIN_EST_DAYS:
        return None, "too few estimation days"
    beta, alpha = np.polyfit(est["m"], est["r"], 1)

    win = data.iloc[pos + WIN_START: pos + WIN_END + 1]
    ar = win["r"] - (alpha + beta * win["m"])
    ar.index = range(WIN_START, WIN_END + 1)
    return float(ar.sum()), ar


def main():
    uni = pd.read_csv(PROCESSED_DIR / "universe.csv", dtype={"code": str})
    events = uni[uni["valueup_plan"]].copy()
    events["event_date"] = pd.to_datetime(events["valueup_first_plan_date"].astype(str).str[:8],
                                          format="%Y%m%d")

    market = cached_prices("KS11")["Close"].pct_change()

    rows, skipped, ar_paths = [], [], []
    for r in events.itertuples(index=False):
        prices = cached_prices(r.code)
        if prices.empty:
            skipped.append((r.code, r.name, "no price data"))
            continue
        car, detail = event_car(prices["Close"].pct_change(), market, r.event_date)
        if car is None:
            skipped.append((r.code, r.name, detail))
            continue
        rows.append({"code": r.code, "name": r.name, "name_eng": r.name_eng,
                     "event_date": r.event_date.date(), "is_financial": r.is_financial,
                     "car": car})
        ar_paths.append(detail)

    res = pd.DataFrame(rows)
    res.to_csv(PROCESSED_DIR / "event_study_car.csv", index=False)

    def summarize(cars):
        n = len(cars)
        mean, sd = cars.mean(), cars.std(ddof=1)
        return {"n": int(n), "mean_car": float(mean), "median_car": float(cars.median()),
                "t_stat": float(mean / (sd / np.sqrt(n))) if n > 1 else None,
                "share_positive": float((cars > 0).mean())}

    by_month = res.groupby(pd.to_datetime(res["event_date"]).dt.to_period("M")).size()
    stats = {
        "all": summarize(res["car"]),
        "non_financials": summarize(res.loc[~res["is_financial"], "car"]),
        "financials": summarize(res.loc[res["is_financial"], "car"]),
        "skipped": [{"code": c, "name": n, "reason": why} for c, n, why in skipped],
        "busiest_event_months": {str(k): int(v) for k, v in by_month.sort_values(ascending=False).head(5).items()},
        "window": [WIN_START, WIN_END], "estimation": [EST_START, EST_END],
    }
    (OUTPUT_DIR / "event_study_stats.json").write_text(json.dumps(stats, indent=2, ensure_ascii=False),
                                                       encoding="utf-8")

    mean_path = pd.concat(ar_paths, axis=1).mean(axis=1).cumsum()
    import charts
    charts.event_study_car(mean_path, stats["all"]["n"])
    print(json.dumps({k: v for k, v in stats.items() if k != "skipped"}, indent=2))
    print("skipped:", len(skipped))


if __name__ == "__main__":
    main()

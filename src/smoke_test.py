"""Phase 0 smoke test: check both data sources return data.

1. FinanceDataReader: current KOSPI listing (price, market cap, shares). No login needed.
2. DART: Samsung Electronics exchange disclosures, to confirm the API key works.

Run from the project root:
    .venv/bin/python src/smoke_test.py
"""

import os
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"


def check_env():
    """Load .env and stop early if the DART key is missing."""
    load_dotenv(ROOT / ".env")
    if not os.getenv("DART_API_KEY"):
        sys.exit("Missing DART_API_KEY. Copy .env.example to .env and fill it in.")


def test_listing():
    import FinanceDataReader as fdr

    today = date.today().strftime("%Y%m%d")
    cache_path = RAW_DIR / f"listing_KOSPI_{today}.csv"

    if cache_path.exists():
        print(f"Loading cached file: {cache_path.name}")
        df = pd.read_csv(cache_path, dtype={"Code": str})
    else:
        df = fdr.StockListing("KOSPI")
        if df is None or df.empty:
            sys.exit("FinanceDataReader returned no KOSPI listing. Stopping.")
        df.to_csv(cache_path, index=False)
        print(f"Saved raw response: {cache_path.name}")

    print(f"KOSPI listing shape: {df.shape}")
    print(df[["Code", "Name", "Close", "Marcap", "Stocks"]].head())


def test_dart():
    import OpenDartReader

    dart = OpenDartReader(os.environ["DART_API_KEY"])
    df = dart.list("005930", start="2024-05-01", kind="I")
    if df is None or df.empty:
        sys.exit("DART returned no filings for Samsung Electronics. Stopping.")

    print(f"\nSamsung Electronics exchange disclosures since 2024-05-01: {len(df)}")
    print(df[["rcept_dt", "report_nm"]].head())


def main():
    check_env()
    test_listing()
    test_dart()


if __name__ == "__main__":
    main()

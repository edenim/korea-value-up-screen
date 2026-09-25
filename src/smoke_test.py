"""Phase 0 smoke test: pull KOSPI fundamentals for one recent business day.

Run from the project root:
    python src/smoke_test.py
"""

import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
REQUIRED_ENV_VARS = ["KRX_ID", "KRX_PW", "DART_API_KEY"]


def check_env():
    """Load .env and stop early if any credential is missing."""
    load_dotenv(ROOT / ".env")
    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        sys.exit(f"Missing env vars: {missing}. Copy .env.example to .env and fill them in.")


def main():
    check_env()

    # Import after load_dotenv so pykrx sees KRX_ID / KRX_PW
    from pykrx import stock

    date = stock.get_nearest_business_day_in_a_week()
    cache_path = RAW_DIR / f"fundamental_KOSPI_{date}.csv"

    if cache_path.exists():
        print(f"Loading cached file: {cache_path.name}")
        df = pd.read_csv(cache_path, index_col=0, dtype={0: str})
    else:
        df = stock.get_market_fundamental(date, market="KOSPI")
        if df is None or df.empty:
            sys.exit(f"get_market_fundamental returned no data for {date}. Stopping.")
        df.to_csv(cache_path)
        print(f"Saved raw response: {cache_path.name}")

    print(f"Date: {date}")
    print(f"Shape: {df.shape}")
    print(df.head())


if __name__ == "__main__":
    main()

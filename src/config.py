"""Project-wide parameters. Change values here, not inside the pipeline scripts."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
CHART_DIR = ROOT / "outputs" / "charts"
OUTPUT_DIR = ROOT / "outputs"

# Universe
MIN_MARKET_CAP_KRW = 500e9  # KRW 500bn, measured on common + preferred market cap
LISTING_DATE = "20260925"   # date of the cached FinanceDataReader KOSPI listing

# Financials: latest full fiscal year with an annual report (filed by March 2026)
FISCAL_YEAR = 2025
ANNUAL_REPORT_CODE = "11011"

# Value-Up disclosures
VALUEUP_START = "2024-05-01"
VALUEUP_END = "2026-09-25"
VALUEUP_KEYWORD = "기업가치제고계획"
VALUEUP_PREVIEW_KEYWORD = "예고"  # preview notices, filed before the actual plan

# Politeness between live API calls (seconds)
API_SLEEP = 0.3

"""Cached wrappers around OpenDartReader.

Every live response is saved under data/raw/dart/<kind>/ so reruns never hit the API twice.
An empty response is also cached (as an empty file) so a company with no data is not refetched.
"""

import json
import os
import time

import OpenDartReader
import pandas as pd
from dotenv import load_dotenv

from config import API_SLEEP, RAW_DIR, ROOT

load_dotenv(ROOT / ".env")
_dart = None


def get_dart():
    global _dart
    if _dart is None:
        _dart = OpenDartReader(os.environ["DART_API_KEY"])
    return _dart


def corp_code(stock_code):
    """8-digit DART corp code for a 6-character stock code.

    OpenDartReader treats codes containing letters (new format, e.g. '0126Z0') as company
    names and fails to find them, so we look the code up ourselves and pass the corp code.
    """
    table = get_dart().corp_codes
    match = table[table["stock_code"] == stock_code]
    if match.empty:
        raise ValueError(f"No DART corp code for stock code {stock_code}")
    return match.iloc[0]["corp_code"]


def _cached_table(kind, name, fetch):
    """Return a DataFrame from cache, or call fetch() and cache the result."""
    folder = RAW_DIR / "dart" / kind
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}.csv"

    if path.exists():
        if path.stat().st_size == 0:
            return pd.DataFrame()
        return pd.read_csv(path, dtype=str)

    df = fetch()
    time.sleep(API_SLEEP)
    if df is None or len(df) == 0:
        path.write_text("")
        return pd.DataFrame()
    df = df.astype(str)
    df.to_csv(path, index=False)
    return df


def company_info(stock_code):
    folder = RAW_DIR / "dart" / "company"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{stock_code}.json"

    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))

    info = get_dart().company(corp_code(stock_code))
    time.sleep(API_SLEEP)
    if info.get("status") != "000":
        raise RuntimeError(f"DART company() failed for {stock_code}: {info}")
    path.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
    return info


def disclosures(stock_code, start, end):
    """Exchange disclosures (kind='I'). Queried per company, as advised for DART."""
    return _cached_table(
        "list_I", stock_code,
        lambda: get_dart().list(corp_code(stock_code), start=start, end=end, kind="I"),
    )


def financial_statements(stock_code, year, reprt_code, fs_div):
    """Full financial statements. fs_div is 'CFS' (consolidated) or 'OFS' (separate)."""
    def fetch():
        try:
            return get_dart().finstate_all(corp_code(stock_code), year, reprt_code=reprt_code, fs_div=fs_div)
        except ValueError:
            # OpenDartReader raises when DART has no data for this combination
            return None

    return _cached_table("finstate", f"{stock_code}_{year}_{reprt_code}_{fs_div}", fetch)


def dividends(stock_code, year, reprt_code):
    return _cached_table(
        "dividend", f"{stock_code}_{year}_{reprt_code}",
        lambda: get_dart().report(corp_code(stock_code), "배당", year, reprt_code=reprt_code),
    )

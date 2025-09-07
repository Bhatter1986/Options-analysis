import os
import requests
import pandas as pd
from functools import lru_cache

# Base URLs
INSTRUMENTS_COMPACT_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"
INSTRUMENTS_DETAILED_URL = "https://images.dhan.co/api-data/api-scrip-master-detailed.csv"
INSTRUMENTS_SEGMENT_URL = "https://api.dhan.co/v2/instrument/{exchangeSegment}"

# Cache instruments for faster reloads
@lru_cache(maxsize=1)
def get_instruments_csv(force_refresh: bool = False) -> pd.DataFrame:
    """
    Fetches the compact instruments CSV from Dhan.
    Cached by default, use force_refresh=True to reload.
    """
    if force_refresh:
        get_instruments_csv.cache_clear()

    resp = requests.get(INSTRUMENTS_COMPACT_URL)
    resp.raise_for_status()
    df = pd.read_csv(pd.compat.StringIO(resp.text))
    return df


@lru_cache(maxsize=1)
def get_instruments_detailed_csv(force_refresh: bool = False) -> pd.DataFrame:
    """
    Fetches the detailed instruments CSV from Dhan.
    Cached by default, use force_refresh=True to reload.
    """
    if force_refresh:
        get_instruments_detailed_csv.cache_clear()

    resp = requests.get(INSTRUMENTS_DETAILED_URL)
    resp.raise_for_status()
    df = pd.read_csv(pd.compat.StringIO(resp.text))
    return df


def get_instruments_by_segment(exchange_segment: str) -> dict:
    """
    Fetch instruments list for a specific exchange segment.
    Example: NSE_EQ, NSE_FNO, BSE_EQ
    """
    url = INSTRUMENTS_SEGMENT_URL.format(exchangeSegment=exchange_segment)
    headers = {
        "access-token": os.getenv("DHAN_API_KEY", "")
    }
    resp = requests.get(url, headers=headers)
    resp.raise_for_status()
    return resp.json()


# 🔑 Backward Compatibility Wrapper
def get_instruments(force_refresh: bool = False) -> pd.DataFrame:
    """
    Alias for get_instruments_csv so old imports don't break.
    """
    return get_instruments_csv(force_refresh=force_refresh)


def search_instruments(keyword: str, force_refresh: bool = False) -> pd.DataFrame:
    """
    Search instruments by symbol/keyword in compact list.
    """
    df = get_instruments_csv(force_refresh=force_refresh)
    return df[df['SEM_SYMBOL_NAME'].str.contains(keyword, case=False, na=False)]

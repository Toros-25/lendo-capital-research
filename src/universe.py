"""
Universe definition for Tasks 2–5.

Top 50 S&P 500 constituents by market cap + SPY as market proxy.

Snapshot approach: pulling live market cap for all ~500 S&P 500 constituents
via yfinance would require hundreds of sequential API calls (~5–10 min) and
risks rate-limiting. Instead we use a dated snapshot.

Source: SlickCharts S&P 500 market-cap ranking
        (https://www.slickcharts.com/sp500) combined with public filings.
Snapshot date: 2025-08-30
Note: BRK-B uses the yfinance-compatible hyphen form (not dot).
"""

# Fixed date range: 5 years of daily data ending on the snapshot date.
END_DATE: str = "2025-08-30"
START_DATE: str = "2020-08-30"

# Top 50 S&P 500 constituents by market cap as of 2025-08-30 (snapshot).
SP500_TOP50: list[str] = [
    # Rank 1-10
    "NVDA", "AAPL", "MSFT", "AMZN", "META",
    "GOOGL", "TSLA", "AVGO", "BRK-B", "LLY",
    # Rank 11-20
    "JPM", "WMT", "V", "UNH", "XOM",
    "MA", "COST", "NFLX", "ORCL", "PG",
    # Rank 21-30
    "JNJ", "BAC", "CRM", "AMD", "HD",
    "ABBV", "KO", "MRK", "CVX", "PLTR",
    # Rank 31-40
    "ACN", "PEP", "NOW", "TMO", "CSCO",
    "ISRG", "GE", "LIN", "IBM", "AXP",
    # Rank 41-50
    "TXN", "GS", "PM", "AMGN", "INTU",
    "SPGI", "RTX", "BKNG", "UBER", "QCOM",
]

# SPY is an ETF (not an S&P 500 constituent) added separately as market proxy.
UNIVERSE: list[str] = SP500_TOP50 + ["SPY"]


def get_sector_map(
    tickers: list[str],
    cache_dir: str = "data/raw",
) -> dict[str, str]:
    """
    Return GICS sector for each ticker, cached to ``{cache_dir}/sector_map.json``.

    SPY is silently excluded from the returned dict — it is an ETF with no GICS
    sector assignment and is not a meaningful input to sector-based analysis.

    The cache is checked first; only tickers absent from the cache trigger a
    yfinance API call (rate-limited at 0.1 s between calls). The updated cache
    is written back after each run.

    Parameters
    ----------
    tickers   : list of ticker strings (SPY is skipped)
    cache_dir : directory that contains (or will contain) ``sector_map.json``

    Returns
    -------
    dict[str, str]
        ``{ticker: sector}`` for every non-SPY ticker in *tickers* that has a
        known sector.  Tickers for which yfinance returns no sector information
        are mapped to ``"Unknown"``.
    """
    import json
    import time
    from pathlib import Path

    import yfinance as yf

    cache_path = Path(cache_dir) / "sector_map.json"

    if cache_path.exists():
        with open(cache_path) as fh:
            sector_cache: dict[str, str] = json.load(fh)
    else:
        sector_cache = {}

    missing = [t for t in tickers if t != "SPY" and t not in sector_cache]
    for t in missing:
        info = yf.Ticker(t).info
        sector_cache[t] = info.get("sector") or "Unknown"
        time.sleep(0.1)

    if missing:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w") as fh:
            json.dump(sector_cache, fh, indent=2, sort_keys=True)

    return {t: sector_cache[t] for t in tickers if t != "SPY" and t in sector_cache}

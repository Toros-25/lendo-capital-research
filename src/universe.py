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

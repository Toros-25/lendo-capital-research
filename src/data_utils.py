"""
OHLCV data loading and resampling utilities.

Downstream return calculations must use ``adj_close``, not ``close``.

Column semantics (yfinance ≥ 1.7 with ``auto_adjust=False``):
  - ``close``     — split-adjusted close: Yahoo back-adjusts for stock splits
                    so the series is continuous, but dividends are NOT removed.
  - ``adj_close`` — fully adjusted close: adjusted for BOTH splits AND
                    dividends (the dividend amount is subtracted from all prior
                    prices on ex-dividend date).

Why ``adj_close`` for returns: dividends are real economic returns. If you
compute returns from ``close``, you miss all dividend income, which materially
understates total return for high-yield stocks (e.g. XOM yields ~4 %/yr, so
``close``-only cumulative returns drift ~25 % low over 5 years).
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def load_ohlcv(
    tickers: list[str],
    start: str,
    end: str,
    cache_dir: str = "data/raw",
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Download or load cached daily OHLCV bars for the given tickers.

    Uses ``adj_close`` for downstream return calculations. ``close`` is the
    split-adjusted close (yfinance ≥ 1.7 behavior with ``auto_adjust=False``):
    it accounts for splits but NOT dividends. ``adj_close`` accounts for both
    splits and dividends, giving the economically correct return series.

    Parameters
    ----------
    tickers:
        List of Yahoo Finance ticker symbols.
    start:
        Start date, inclusive, as "YYYY-MM-DD".
    end:
        End date, inclusive, as "YYYY-MM-DD".
    cache_dir:
        Directory for the parquet cache file. Created if absent.
    force_refresh:
        Re-download from the API even if a cache file already exists.

    Returns
    -------
    pd.DataFrame
        Tidy (long) format with columns:
        ``date, ticker, open, high, low, close, adj_close, volume``.
        Rows are sorted by (date, ticker).
    """
    cache_path = Path(cache_dir) / "ohlcv_daily.parquet"
    Path(cache_dir).mkdir(parents=True, exist_ok=True)

    if not force_refresh and cache_path.exists():
        logger.info("Loading OHLCV from cache: %s", cache_path)
        return pd.read_parquet(cache_path)

    logger.info(
        "Downloading daily OHLCV for %d tickers (%s → %s)",
        len(tickers),
        start,
        end,
    )

    raw = yf.download(
        tickers=tickers,
        start=start,
        end=end,
        auto_adjust=False,  # explicit: retain both Close and Adj Close columns
        progress=False,
    )

    # yfinance 1.7+ always returns MultiIndex columns with names
    # ['Price', 'Ticker'] regardless of the number of tickers.
    frames: list[pd.DataFrame] = []
    failed: list[str] = []

    for ticker in tickers:
        try:
            df_t = raw.xs(ticker, axis=1, level="Ticker").copy()

            if df_t.dropna(how="all").empty:
                logger.warning("No valid data for %s — skipping", ticker)
                failed.append(ticker)
                continue

            df_t = df_t.rename(
                columns={
                    "Adj Close": "adj_close",
                    "Close": "close",
                    "High": "high",
                    "Low": "low",
                    "Open": "open",
                    "Volume": "volume",
                }
            )

            required = ["open", "high", "low", "close", "adj_close", "volume"]
            missing = [c for c in required if c not in df_t.columns]
            if missing:
                logger.warning(
                    "Ticker %s missing columns %s — skipping", ticker, missing
                )
                failed.append(ticker)
                continue

            df_t = df_t[required].copy()

            # Drop rows where every OHLCV column is NaN for this ticker.
            # The batch download index spans all dates for all tickers, so
            # late-IPO tickers (e.g. PLTR) get all-NaN rows before they
            # started trading. This is distinct from the whole-ticker check
            # above: that guard catches a completely failed download; this
            # drops only the pre-listing phantom rows.
            pre_drop_len = len(df_t)
            df_t = df_t.dropna(how="all")
            dropped = pre_drop_len - len(df_t)
            if dropped:
                first_date = df_t.index[0].date() if not df_t.empty else "n/a"
                logger.info(
                    "%s: dropped %d all-NaN rows before first trading date %s",
                    ticker,
                    dropped,
                    first_date,
                )

            df_t.index.name = "date"
            df_t = df_t.reset_index()
            df_t["ticker"] = ticker
            df_t = df_t[["date", "ticker"] + required]
            frames.append(df_t)

        except Exception as exc:  # noqa: BLE001
            logger.warning("Error processing ticker %s: %s", ticker, exc)
            failed.append(ticker)

    if failed:
        logger.warning(
            "%d ticker(s) failed or returned no data: %s", len(failed), failed
        )

    if not frames:
        raise ValueError("No data was successfully downloaded for any ticker.")

    result = (
        pd.concat(frames, ignore_index=True)
        .sort_values(["date", "ticker"])
        .reset_index(drop=True)
    )

    result["date"] = pd.to_datetime(result["date"])

    result.to_parquet(cache_path, index=False)
    logger.info("Cached %d rows to %s", len(result), cache_path)

    return result


def resample_ohlcv(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    """
    Resample daily OHLCV bars to a lower frequency per ticker.

    Aggregation rules:
    - open      → first value in the period
    - high      → maximum in the period
    - low       → minimum in the period
    - close     → last value in the period
    - adj_close → last value in the period
    - volume    → sum over the period

    Parameters
    ----------
    df:
        Tidy daily DataFrame as returned by :func:`load_ohlcv`.
    freq:
        Pandas offset alias. Common values:
        ``"W"`` (weekly, ending Sunday),
        ``"ME"`` (month-end),
        ``"YE"`` (year-end).

    Returns
    -------
    pd.DataFrame
        Same schema as input (``date, ticker, open, high, low, close,
        adj_close, volume``) at the requested frequency.
    """
    agg_rules: dict[str, str] = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "adj_close": "last",
        "volume": "sum",
    }

    frames: list[pd.DataFrame] = []
    for ticker, group in df.groupby("ticker", sort=True):
        resampled = (
            group.set_index("date")
            .resample(freq)
            .agg(agg_rules)
            .dropna(how="all")
            .reset_index()
        )
        resampled["ticker"] = ticker
        frames.append(resampled)

    result = pd.concat(frames, ignore_index=True)
    result = result[
        ["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]
    ]
    return result.sort_values(["date", "ticker"]).reset_index(drop=True)


def compute_returns(
    df: pd.DataFrame,
    method: str = "simple",
    price_col: str = "adj_close",
) -> pd.DataFrame:
    """
    Compute per-ticker returns from OHLCV data at any frequency.

    Works identically on daily data from :func:`load_ohlcv` /
    :func:`clean_ohlcv` and on pre-resampled weekly, monthly, or annual bars
    from :func:`resample_ohlcv`.

    Parameters
    ----------
    df:
        Tidy (long) DataFrame with at least columns ``date``, ``ticker``,
        and ``price_col``. Must be sortable by ``(ticker, date)``.
    method:
        ``"simple"`` (default): R_t = (P_t − P_{t−1}) / P_{t−1}
        ``"log"``             : r_t = ln(P_t / P_{t−1})
    price_col:
        Column to compute returns from. **Must be** ``adj_close`` for
        economically correct results. ``adj_close`` already accounts for
        stock splits *and* dividends (verified via NVDA split and XOM
        dividend checks in Tasks 2–3). Using ``close`` instead would miss
        all dividend income; re-adjusting here would double-adjust.

    Returns
    -------
    pd.DataFrame
        Input columns plus a ``"return"`` column, sorted by
        ``(ticker, date)``. The first row for each ticker is always NaN —
        there is no prior price to compute a return from. For PLTR, whose
        series genuinely starts on 2020-09-30 (not padded), this first-row
        NaN is correct, not a bug.

    Time-aggregation vs. cross-sectional-aggregation
    -------------------------------------------------
    These two methods have *opposite* aggregation properties and must not
    be mixed up in Tasks 5+.

    **Log returns aggregate additively across TIME:**
        r_{1→n} = r_1 + r_2 + … + r_n

        The multi-period log return equals the sum of the per-period log
        returns. This makes log returns convenient for time-series analysis
        and compounding a single asset's return over long horizons.

    **Simple returns aggregate correctly across ASSETS at a point in time:**
        R_portfolio,t = Σ w_i · R_{i,t}

        A portfolio's simple return is the weighted average of its
        constituents' simple returns. Log returns do *not* have this
        property — averaging log returns across tickers does not give the
        correct portfolio log return, because ln(Σ w_i P_i) ≠ Σ w_i ln(P_i).

    **Forward pointer to Task 5:** Use simple returns for portfolio-level
    calculations (weighted combinations of stocks). Use log returns for
    time-series analysis of a single asset or for volatility estimation.
    Never average log returns across tickers to derive a portfolio return.

    Notes
    -----
    The ``groupby("ticker")`` before ``pct_change()`` / ``shift()`` is
    critical. Without it, a naked ``shift(1)`` on a ticker-sorted DataFrame
    computes a spurious "return" from the last row of ticker A to the first
    row of ticker B — a silent corruption with no error message.
    """
    if method not in ("simple", "log"):
        raise ValueError(f"method must be 'simple' or 'log', got {method!r}")

    out = df.sort_values(["ticker", "date"]).copy()

    if method == "simple":
        out["return"] = out.groupby("ticker")[price_col].pct_change()
    else:
        out["return"] = out.groupby("ticker")[price_col].transform(
            lambda x: np.log(x / x.shift(1))
        )

    return out.sort_values(["ticker", "date"]).reset_index(drop=True)


def clean_ohlcv(
    df: pd.DataFrame,
    max_fill_days: int = 2,
    return_outlier_threshold: float = 0.50,
    volume_spike_multiple: float = 5.0,
    volume_lookback_days: int = 20,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    """
    Clean daily OHLCV data and produce a structured quality report.

    Returns the cleaned DataFrame and a dict of labelled report DataFrames
    covering every category of data issue found or modification made. Nothing
    is changed silently.

    Parameters
    ----------
    df:
        Raw daily DataFrame as returned by :func:`load_ohlcv`.
    max_fill_days:
        Maximum consecutive trading days to forward-fill for within-life gaps.
        Default 2. Gaps longer than this are left as NaN and flagged.
    return_outlier_threshold:
        Flag ticker-dates where ``adj_close`` daily return exceeds this
        magnitude. Default 0.50 (±50%). Uses ``adj_close`` intentionally —
        raw ``close`` would false-flag split dates (e.g. NVDA June 2024).
    volume_spike_multiple:
        Flag ticker-dates where volume exceeds this multiple of the trailing
        ``volume_lookback_days``-day average. Default 5×. Chosen because 5×
        is statistically extreme for large-caps (>4σ on a lognormal volume
        distribution) and almost always coincides with a real event (earnings,
        index rebalance, M&A), not a data error. We flag rather than remove.
    volume_lookback_days:
        Rolling window for the volume baseline. Default 20 (≈1 trading month).

    Returns
    -------
    cleaned : pd.DataFrame
        Same schema as input. Within-life price gaps of ≤ ``max_fill_days``
        are forward-filled; volume is set to NaN on filled rows (a filled
        volume of 0 would be mistaken for a genuine zero-volume day).
        Longer gaps remain NaN. Pre-listing rows are never touched.
    report : dict[str, pd.DataFrame]
        Keys:
        - ``"pre_listing_gaps"``    — rows whose date precedes the ticker's
          first trade date (should be empty; load_ohlcv already strips these).
        - ``"within_life_gaps"``    — dates in the market calendar that are
          absent for a ticker between its first and last trade dates.
        - ``"partial_nans"``        — existing rows with any NaN in price/
          volume columns (different problem: column-level corruption).
        - ``"calendar_misalign"``   — market-calendar dates missing for
          multiple established tickers simultaneously (suggests a batch-
          download calendar shift, not an individual ticker event).
        - ``"filled_rows"``         — every (ticker, date) pair that was
          forward-filled by this function, with original NaN columns listed.
        - ``"return_outliers"``     — ticker-dates where adj_close return
          exceeds ±``return_outlier_threshold``.
        - ``"volume_spikes"``       — ticker-dates where volume exceeds
          ``volume_spike_multiple``× trailing average.

    Fill policy
    -----------
    Trade-offs considered for within-life gaps
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    DROP: semantically cleanest — no fabricated data. But downstream return
    computation silently produces NaN or inf returns at the gap, which can
    corrupt cumulative-return series or cause silent errors in Tasks 4–5.
    For large-cap equities a 1-day gap is almost never a genuine halt, so
    dropping is not more honest than filling.

    INTERPOLATION: smooth, but requires the next real price (look-ahead),
    which introduces bias. Ruled out.

    FORWARD-FILL with limit (chosen): carries the last known price forward.
    Equivalent to assuming the stock did not move — a reasonable placeholder
    for a brief data gap on a heavily-traded large-cap. Limit=2 covers the
    most common case (a single missing trading day) plus one extra day of
    tolerance. Gaps longer than 2 days are left as NaN and flagged; an
    extended fill would fabricate too much data without justification.

    Volume on filled rows is set to NaN (not 0 or carried forward): volume
    has no defensible "hold-last" interpretation, and a filled volume of 0
    could be mistaken for a genuine no-trade day.

    Never fill before first_trade_date: pre-listing periods have no prices
    by definition. Backwards-filling into a pre-listing period would
    fabricate trading activity that never occurred — the exact bug fixed in
    load_ohlcv() for PLTR in Task 2.
    """
    price_cols = ["open", "high", "low", "close", "adj_close"]
    all_cols = price_cols + ["volume"]

    # ------------------------------------------------------------------
    # 1. Reference market calendar (SPY trades every US market day)
    # ------------------------------------------------------------------
    spy_dates = pd.DatetimeIndex(
        sorted(df.loc[df["ticker"] == "SPY", "date"].unique())
    )

    # ------------------------------------------------------------------
    # 2. Per-ticker metadata
    # ------------------------------------------------------------------
    meta = (
        df.groupby("ticker")["date"]
        .agg(first_trade=lambda s: s.min(), last_trade=lambda s: s.max())
    )

    # ------------------------------------------------------------------
    # 3. Pre-listing gap check (should be empty after load_ohlcv fix)
    # ------------------------------------------------------------------
    pre_listing_rows = []
    for ticker, row in meta.iterrows():
        pre = df[(df["ticker"] == ticker) & (df["date"] < row["first_trade"])]
        for _, r in pre.iterrows():
            pre_listing_rows.append({"ticker": ticker, "date": r["date"]})
    pre_listing_gaps = pd.DataFrame(pre_listing_rows)
    if not pre_listing_gaps.empty:
        logger.warning(
            "%d pre-listing rows found — these should have been removed by "
            "load_ohlcv(). Re-run with force_refresh=True.",
            len(pre_listing_gaps),
        )

    # ------------------------------------------------------------------
    # 4. Within-life gap detection (missing dates in market calendar)
    # ------------------------------------------------------------------
    within_life_rows = []
    for ticker, row in meta.iterrows():
        expected = spy_dates[
            (spy_dates >= row["first_trade"]) & (spy_dates <= row["last_trade"])
        ]
        actual = pd.DatetimeIndex(
            df.loc[df["ticker"] == ticker, "date"].sort_values()
        )
        missing = expected.difference(actual)
        for d in missing:
            within_life_rows.append({"ticker": ticker, "date": d})
    within_life_gaps = pd.DataFrame(
        within_life_rows if within_life_rows else [],
        columns=["ticker", "date"],
    )
    if not within_life_gaps.empty:
        logger.warning(
            "%d within-life missing date(s) detected across %d ticker(s).",
            len(within_life_gaps),
            within_life_gaps["ticker"].nunique(),
        )

    # ------------------------------------------------------------------
    # 5. Partial-NaN detection (existing rows with column-level NaN)
    # ------------------------------------------------------------------
    partial_nan_rows = []
    for ticker, group in df.groupby("ticker"):
        bad = group[group[all_cols].isna().any(axis=1)]
        for _, r in bad.iterrows():
            null_cols = [c for c in all_cols if pd.isna(r[c])]
            partial_nan_rows.append(
                {"ticker": ticker, "date": r["date"], "null_columns": str(null_cols)}
            )
    partial_nans = pd.DataFrame(
        partial_nan_rows if partial_nan_rows else [],
        columns=["ticker", "date", "null_columns"],
    )

    # ------------------------------------------------------------------
    # 6. Calendar misalignment (multiple established tickers missing
    #    on the same date, suggesting a shared download/calendar issue)
    # ------------------------------------------------------------------
    cal_misalign_rows: list[dict] = []
    if not within_life_gaps.empty:
        per_date = within_life_gaps.groupby("date")["ticker"].apply(list).reset_index()
        per_date.columns = ["date", "missing_tickers"]
        per_date["n_missing"] = per_date["missing_tickers"].apply(len)
        # Flag dates where >1 established ticker (traded >60 days by that date)
        # is simultaneously absent — individual gaps are more likely data errors,
        # shared gaps on the same date suggest a systematic calendar issue.
        established_cutoff = 60
        for _, prow in per_date.iterrows():
            d = prow["date"]
            long_running = [
                t for t in prow["missing_tickers"]
                if (d - meta.loc[t, "first_trade"]).days >= established_cutoff
            ]
            if len(long_running) > 1:
                cal_misalign_rows.append(
                    {
                        "date": d,
                        "n_missing": len(long_running),
                        "missing_tickers": long_running,
                    }
                )
    calendar_misalign = pd.DataFrame(
        cal_misalign_rows if cal_misalign_rows else [],
        columns=["date", "n_missing", "missing_tickers"],
    )

    # ------------------------------------------------------------------
    # 7. Forward-fill within-life gaps (≤ max_fill_days)
    # ------------------------------------------------------------------
    filled_records: list[dict] = []
    cleaned_frames: list[pd.DataFrame] = []

    for ticker, group in df.groupby("ticker", sort=True):
        first_trade = meta.loc[ticker, "first_trade"]
        last_trade = meta.loc[ticker, "last_trade"]

        expected_idx = spy_dates[
            (spy_dates >= first_trade) & (spy_dates <= last_trade)
        ]

        g = group.set_index("date").reindex(expected_idx)

        # Track which rows are NaN before filling (missing dates or partial NaN)
        pre_fill_null = g[price_cols].isna().any(axis=1)

        if pre_fill_null.any():
            g[price_cols] = g[price_cols].ffill(limit=max_fill_days)

            post_fill_null = g[price_cols].isna().any(axis=1)
            newly_filled = pre_fill_null & ~post_fill_null

            # Volume: NaN on filled rows (no meaningful volume to carry forward)
            g.loc[newly_filled, "volume"] = np.nan

            for d in g.index[newly_filled]:
                filled_records.append(
                    {
                        "ticker": ticker,
                        "date": d,
                        "adj_close_filled": g.loc[d, "adj_close"],
                    }
                )

        g.index.name = "date"
        g = g.reset_index()
        g["ticker"] = ticker
        g = g[["date", "ticker"] + all_cols]
        cleaned_frames.append(g)

    filled_rows = pd.DataFrame(
        filled_records if filled_records else [],
        columns=["ticker", "date", "adj_close_filled"],
    )

    if filled_rows.empty:
        logger.info("No within-life gaps to fill — data is complete.")
    else:
        logger.info(
            "Forward-filled %d row(s) across %d ticker(s) (limit=%d days).",
            len(filled_rows),
            filled_rows["ticker"].nunique(),
            max_fill_days,
        )

    cleaned = (
        pd.concat(cleaned_frames, ignore_index=True)
        .sort_values(["date", "ticker"])
        .reset_index(drop=True)
    )
    cleaned["date"] = pd.to_datetime(cleaned["date"])

    # ------------------------------------------------------------------
    # 8. Return outlier detection (adj_close, ±return_outlier_threshold)
    # ------------------------------------------------------------------
    # Compute per-ticker pct_change directly on cleaned (sorted by [date, ticker]).
    # groupby preserves per-ticker date order so pct_change is sequential.
    # Result is aligned to cleaned's sequential integer index — no sort needed.
    adj_rets = (
        cleaned.groupby("ticker")["adj_close"]
        .transform(lambda x: x.pct_change())
        .rename("daily_ret")
    )
    outlier_mask = adj_rets.abs() > return_outlier_threshold
    return_outliers = (
        cleaned[outlier_mask][["ticker", "date", "adj_close"]]
        .copy()
        .assign(daily_ret=adj_rets[outlier_mask])
        .sort_values("daily_ret")
        .reset_index(drop=True)
    )
    if not return_outliers.empty:
        logger.warning(
            "%d adj_close return outlier(s) (|ret| > %.0f%%) found.",
            len(return_outliers),
            return_outlier_threshold * 100,
        )

    # ------------------------------------------------------------------
    # 9. Volume spike detection (> volume_spike_multiple × trailing avg)
    # ------------------------------------------------------------------
    # Compute rolling baseline on cleaned directly — groupby collects each
    # ticker's rows in date order (cleaned is sorted by [date, ticker]), so
    # shift(1).rolling() is correct without an explicit sort.  The result is
    # aligned to cleaned's sequential integer index.
    vol_ma = (
        cleaned.groupby("ticker")["volume"]
        .transform(
            lambda x: x.shift(1).rolling(volume_lookback_days, min_periods=10).mean()
        )
    )
    vol_ratio = cleaned["volume"] / vol_ma
    spike_mask = vol_ratio > volume_spike_multiple
    # Use index-aligned assignment (not .values) so each spike row gets its
    # own ticker's vol_ma and vol_ratio, not a positionally misaligned value.
    volume_spikes = cleaned[spike_mask][["ticker", "date", "volume"]].copy()
    volume_spikes["vol_ma20"] = vol_ma[spike_mask]
    volume_spikes["vol_ratio"] = vol_ratio[spike_mask]
    volume_spikes = volume_spikes.sort_values("vol_ratio", ascending=False).reset_index(drop=True)
    logger.info(
        "%d volume spike event(s) across %d ticker(s) (threshold: %.0f× trailing-%dd avg).",
        len(volume_spikes),
        volume_spikes["ticker"].nunique() if not volume_spikes.empty else 0,
        volume_spike_multiple,
        volume_lookback_days,
    )

    report: dict[str, pd.DataFrame] = {
        "pre_listing_gaps": pre_listing_gaps,
        "within_life_gaps": within_life_gaps,
        "partial_nans": partial_nans,
        "calendar_misalign": calendar_misalign,
        "filled_rows": filled_rows,
        "return_outliers": return_outliers,
        "volume_spikes": volume_spikes,
    }
    return cleaned, report

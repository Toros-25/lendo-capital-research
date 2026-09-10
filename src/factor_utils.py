"""
Factor construction utilities for Week 2.

This module builds value and momentum signals — and eventually quintile
portfolios — on top of the cleaned OHLCV data from data_utils.py.

IMPORTANT — PROXY NATURE OF THE VALUE SIGNAL
---------------------------------------------
This project has no fundamental data source (no book value, no earnings,
no Price-to-Book or Price-to-Earnings ratios). The value signal here is a
**contrarian proxy**: stocks that have fallen the most over the trailing
12 months are treated as "cheaper" / higher value. This is NOT equivalent
to a true Fama-French HML, B/M, or E/P value factor. It must be labelled
as a proxy everywhere it appears — never referred to as a "real" value
factor. The proxy is a real simplification, not a mistake.

Module layout
-------------
get_rebalance_dates(df)
    Shared monthly rebalance schedule derived from the actual trading
    calendar. All factor functions and Task 3 quintile sorting must call
    this function — never duplicate the date-generation logic.

compute_value_score(df, lookback_months=12)
    Trailing-12-month contrarian value proxy. High score = more negative
    trailing return = treated as "cheaper" under this proxy.
    Returns tidy (date, ticker, trailing_return_proxy,
    value_score_proxy, value_rank_proxy) one row per ticker per rebalance
    date. Only includes ticker-dates with full lookback history.

compute_momentum_score(df, lookback_months=12, skip_months=1)
    Standard 12-1 price momentum (Jegadeesh-Titman / Fama-French). Window
    is [t-12, t-1] — the most recent month is skipped to avoid short-term
    reversal contamination. High score = strong winner. This is NOT a proxy;
    it is the textbook definition. Returns tidy (date, ticker,
    momentum_score, momentum_rank) one row per ticker per rebalance date.

build_forward_returns(df)
    Builds the forward holding-period simple return for each (rebalance
    date, ticker) pair. Return at date t = adj_close_{t+1} / adj_close_t - 1,
    i.e. the return earned by holding from month-end t through month-end t+1.
    The last rebalance date has no forward period and is left as NaN (to be
    excluded by form_quintile_portfolios). Returns tidy (date, ticker,
    fwd_return).

form_quintile_portfolios(df, signal_col, ret_col)
    Sorts tickers into five quintile portfolios at each rebalance date by
    signal_col (descending), then computes the equal-weighted average of
    ret_col within each quintile. Q5 = highest signal = most desirable;
    Q1 = lowest signal = least desirable. Dates with no valid ret_col are
    excluded with a logged reason. Returns tidy (date, quintile,
    portfolio_return, n_holdings).
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from data_utils import compute_returns, resample_ohlcv

logger = logging.getLogger(__name__)


def get_rebalance_dates(df: pd.DataFrame) -> pd.DatetimeIndex:
    """
    Return the month-end rebalance schedule derived from the trading calendar.

    Rebalance dates are the last trading day of each calendar month that
    appears in the daily OHLCV data ``df``. This is consistent with the
    monthly rebalancing used in Week 1 Task 5 and is derived from
    ``resample_ohlcv`` so the two never drift onto different monthly grids.

    All factor functions (value, momentum) and Task 3 quintile sorting
    must call this function — never hand-roll a separate date grid.

    Parameters
    ----------
    df:
        Tidy daily OHLCV DataFrame as returned by ``load_ohlcv`` /
        ``clean_ohlcv``. Must contain ``date`` and ``ticker`` columns.

    Returns
    -------
    pd.DatetimeIndex
        Sorted month-end trading dates covering the full date range of
        ``df``.
    """
    monthly = resample_ohlcv(df, freq="ME")
    dates = pd.DatetimeIndex(sorted(monthly["date"].unique()))
    logger.info("Rebalance dates: %d month-ends (%s → %s)",
                len(dates), dates.min().date(), dates.max().date())
    return dates


def compute_value_score(
    df: pd.DataFrame,
    lookback_months: int = 12,
) -> pd.DataFrame:
    """
    Compute a contrarian value proxy score at each monthly rebalance date.

    VALUE PROXY — NOT A TRUE VALUE FACTOR
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Because this project has no fundamental data, value is proxied by the
    **negative of the trailing 12-month cumulative return**:

        trailing_return_proxy = P_t / P_{t-lookback_months} - 1
        value_score_proxy     = -trailing_return_proxy

    A **high value_score_proxy** means the stock has fallen more over the
    trailing window, which is treated as "cheaper" / higher value under
    this contrarian proxy.

    DIRECTION (critical for Task 3/4 quintile interpretation)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    value_score_proxy is defined so that:
      - High score → more negative trailing return → "cheap" / value stock
      - Low score  → more positive trailing return → "expensive" / growth stock
      - value_rank_proxy = 1 → highest value_score_proxy → most "cheap"

    Do not flip this direction when building quintiles in Task 3; Q5 should
    contain the cheapest stocks (highest value_score_proxy), Q1 the most
    expensive.

    NO SKIP-MOST-RECENT-MONTH
    ~~~~~~~~~~~~~~~~~~~~~~~~~
    Unlike momentum (Task 2), this function does NOT skip the most recent
    month. The short-term reversal rationale for that skip is a momentum-
    specific concern. Value uses the full trailing window through date t.
    Do not "fix" this to match momentum's convention.

    INSUFFICIENT HISTORY
    ~~~~~~~~~~~~~~~~~~~~
    Ticker-dates where fewer than ``lookback_months`` months of prior data
    exist are excluded with a logged warning. They are never assigned a NaN
    value that could flow silently downstream. For example, PLTR (IPO
    2020-09-30) cannot have a valid 12-month score until 2021-09-30 at the
    earliest.

    Parameters
    ----------
    df:
        Tidy daily OHLCV DataFrame (``date, ticker, adj_close, ...``).
        Must be the cleaned daily data from ``clean_ohlcv``.
    lookback_months:
        Number of prior months of history required. Default 12.

    Returns
    -------
    pd.DataFrame
        Tidy format with columns:
        ``date, ticker, trailing_return_proxy, value_score_proxy,
        value_rank_proxy``.

        One row per (rebalance date, ticker) where a valid score exists.
        ``value_rank_proxy`` is the cross-sectional rank at each rebalance
        date (1 = highest value_score_proxy = most "cheap" under this proxy).
    """
    rebal_dates = get_rebalance_dates(df)

    # Build monthly adj_close pivot: index = month-end date, columns = ticker
    monthly = resample_ohlcv(df, freq="ME")
    monthly_price = monthly.pivot(index="date", columns="ticker", values="adj_close")

    records: list[dict] = []
    excluded_log: dict[str, list[str]] = {}  # reason → list of "ticker@date" strings

    for rebal_date in rebal_dates:
        if rebal_date not in monthly_price.index:
            continue

        # We need the price lookback_months earlier.
        # Find the position of rebal_date in the monthly index.
        idx_pos = monthly_price.index.get_loc(rebal_date)

        if idx_pos < lookback_months:
            # Not enough months before this rebalance date in the data at all
            n_months_available = idx_pos
            prior_date = monthly_price.index[0]
            for ticker in monthly_price.columns:
                key = f"{ticker}@{rebal_date.date()}"
                reason = (
                    f"only {n_months_available} months of data before "
                    f"{rebal_date.date()} (need {lookback_months}); "
                    f"earliest monthly bar is {prior_date.date()}"
                )
                excluded_log.setdefault(reason, []).append(ticker)
            continue

        prior_date = monthly_price.index[idx_pos - lookback_months]
        current_prices = monthly_price.loc[rebal_date]
        prior_prices = monthly_price.loc[prior_date]

        for ticker in monthly_price.columns:
            p_now = current_prices[ticker]
            p_prior = prior_prices[ticker]

            if pd.isna(p_now) or pd.isna(p_prior):
                key = f"{ticker}@{rebal_date.date()}"
                reason = (
                    f"NaN price at {rebal_date.date()} or {prior_date.date()} "
                    f"(IPO or data gap within lookback window)"
                )
                excluded_log.setdefault(reason, []).append(ticker)
                logger.debug(
                    "Excluded %s at %s: %s", ticker, rebal_date.date(), reason
                )
                continue

            trailing_return = p_now / p_prior - 1
            value_score = -trailing_return

            records.append({
                "date": rebal_date,
                "ticker": ticker,
                "trailing_return_proxy": trailing_return,
                "value_score_proxy": value_score,
            })

    # Log excluded tickers summary
    n_universe = len(monthly_price.columns)
    for reason, tickers in excluded_log.items():
        n_excl = len(tickers)
        sample = tickers[:5]
        logger.info(
            "Excluded %d/%d tickers — %s (showing %d of %d): %s",
            n_excl, n_universe, reason, len(sample), n_excl, sample,
        )

    if not records:
        raise ValueError("No valid value scores computed — check data coverage.")

    out = pd.DataFrame(records)

    # Cross-sectional rank at each rebalance date:
    # rank descending on value_score_proxy so rank 1 = highest score = most "cheap"
    out["value_rank_proxy"] = (
        out.groupby("date")["value_score_proxy"]
        .rank(ascending=False, method="average")
    )

    out = out.sort_values(["date", "value_rank_proxy"]).reset_index(drop=True)

    logger.info(
        "compute_value_score: %d records across %d rebalance dates, "
        "%d tickers (lookback=%d months)",
        len(out),
        out["date"].nunique(),
        out["ticker"].nunique(),
        lookback_months,
    )
    return out


def compute_momentum_score(
    df: pd.DataFrame,
    lookback_months: int = 12,
    skip_months: int = 1,
) -> pd.DataFrame:
    """
    Compute 12-1 price momentum at each monthly rebalance date.

    STANDARD ACADEMIC DEFINITION — NOT A PROXY
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Unlike the value signal in this module (which is a contrarian proxy for
    missing fundamental data), momentum is the standard Jegadeesh-Titman /
    Fama-French definition:

        momentum_score = P_{t - skip_months} / P_{t - lookback_months} - 1

    With defaults (lookback_months=12, skip_months=1), this is the familiar
    "12-1" momentum: the cumulative return from 12 months before the
    rebalance date to 1 month before it, skipping the most recent month.

    WHY SKIP THE MOST RECENT MONTH
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    The short-term reversal effect: a stock that surged in the past month
    often gives back some of that gain in the very next month, contaminating
    a trend signal with a reversal pointing the opposite direction. The
    standard fix is to lag the signal by one month, using ``P_{t-1}`` as the
    end of the momentum window rather than ``P_t``.

    CONTRAST WITH VALUE: VALUE DOES NOT SKIP THE MOST RECENT MONTH
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    ``compute_value_score`` deliberately includes the full window through
    ``t`` (no skip). That function's docstring explains why — the reversal
    rationale is momentum-specific. These two functions are intentionally
    different; neither has "forgotten" what the other does.

    DIRECTION (critical for Task 3/4 quintile interpretation)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    momentum_score is NOT inverted — high score means the stock went up the
    most. This is the opposite economic interpretation from value_score_proxy
    (where high score = falling price = "cheap"). Both factors rank 1 = top
    of the signal, but:
      - Momentum rank 1 = biggest winner (high positive return over [t-12, t-1])
      - Value rank 1    = biggest loser / most "cheap" under the proxy

    This distinction is critical for Task 3: Q5 in a momentum sort is the
    winner quintile; Q5 in a value sort is the "cheapest" quintile. They are
    near-mechanically opposite when computed over similar windows, which is
    why this universe's PLTR will appear near rank 1 on momentum and near
    rank 51 on value_score_proxy simultaneously (Task 5 will analyze the
    negative correlation between the two factors explicitly).

    INSUFFICIENT HISTORY
    ~~~~~~~~~~~~~~~~~~~~
    A ticker needs valid prices at both ``t - lookback_months`` and
    ``t - skip_months``. Missing either → excluded with a logged reason,
    never silently NaN'd. Because the window ends at ``t-1`` rather than
    ``t``, momentum's per-ticker availability can differ from value's by one
    month at IPO boundaries — any such difference is expected and explained.

    Parameters
    ----------
    df:
        Tidy daily OHLCV DataFrame (``date, ticker, adj_close, ...``).
        Must be the cleaned daily data from ``clean_ohlcv``.
    lookback_months:
        Number of months to look back for the start of the momentum window.
        Default 12.
    skip_months:
        Number of most-recent months to skip (short-term reversal filter).
        Default 1 (standard 12-1 momentum).

    Returns
    -------
    pd.DataFrame
        Tidy format with columns: ``date, ticker, momentum_score,
        momentum_rank``.

        One row per (rebalance date, ticker) where a valid score exists.
        ``momentum_rank`` is the cross-sectional rank at each rebalance
        date (1 = highest momentum_score = strongest winner).
    """
    rebal_dates = get_rebalance_dates(df)

    # Build monthly adj_close pivot: index = month-end date, columns = ticker
    monthly = resample_ohlcv(df, freq="ME")
    monthly_price = monthly.pivot(index="date", columns="ticker", values="adj_close")

    records: list[dict] = []
    excluded_log: dict[str, list[str]] = {}

    for rebal_date in rebal_dates:
        if rebal_date not in monthly_price.index:
            continue

        idx_pos = monthly_price.index.get_loc(rebal_date)

        # Need prices at t-lookback_months and t-skip_months.
        # t-lookback_months requires idx_pos >= lookback_months.
        # t-skip_months    requires idx_pos >= skip_months.
        # The binding constraint is always lookback_months (>= 12 >> 1).
        if idx_pos < lookback_months:
            n_available = idx_pos
            for ticker in monthly_price.columns:
                reason = (
                    f"only {n_available} months of data before "
                    f"{rebal_date.date()} (need {lookback_months}); "
                    f"universe-wide lockout"
                )
                excluded_log.setdefault(reason, []).append(ticker)
            continue

        start_date = monthly_price.index[idx_pos - lookback_months]
        end_date   = monthly_price.index[idx_pos - skip_months]

        start_prices = monthly_price.loc[start_date]
        end_prices   = monthly_price.loc[end_date]

        for ticker in monthly_price.columns:
            p_start = start_prices[ticker]
            p_end   = end_prices[ticker]

            if pd.isna(p_start) or pd.isna(p_end):
                reason = (
                    f"NaN price at {start_date.date()} or {end_date.date()} "
                    f"for {ticker} (IPO or data gap within window)"
                )
                excluded_log.setdefault(reason, []).append(ticker)
                logger.debug(
                    "Excluded %s at %s: %s", ticker, rebal_date.date(), reason
                )
                continue

            momentum = p_end / p_start - 1

            records.append({
                "date": rebal_date,
                "ticker": ticker,
                "momentum_score": momentum,
            })

    n_universe = len(monthly_price.columns)
    for reason, tickers in excluded_log.items():
        n_excl = len(tickers)
        sample = tickers[:5]
        logger.info(
            "Excluded %d/%d tickers — %s (showing %d of %d): %s",
            n_excl, n_universe, reason, len(sample), n_excl, sample,
        )

    if not records:
        raise ValueError("No valid momentum scores computed — check data coverage.")

    out = pd.DataFrame(records)

    # Cross-sectional rank: descending, rank 1 = strongest winner
    out["momentum_rank"] = (
        out.groupby("date")["momentum_score"]
        .rank(ascending=False, method="average")
    )

    out = out.sort_values(["date", "momentum_rank"]).reset_index(drop=True)

    logger.info(
        "compute_momentum_score: %d records across %d rebalance dates, "
        "%d tickers (lookback=%d, skip=%d months)",
        len(out),
        out["date"].nunique(),
        out["ticker"].nunique(),
        lookback_months,
        skip_months,
    )
    return out


def build_forward_returns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build the forward holding-period simple return for each rebalance date.

    At rebalance date ``t``, the portfolio is formed and held until the next
    rebalance date ``t+1``. The return earned over that holding period is:

        fwd_return_t = adj_close_{t+1} / adj_close_t - 1

    This equals the monthly simple return that ``compute_returns`` places at
    date ``t+1`` (the return *into* t+1 from t). Shifting that series back
    one period (-1) assigns it to the formation date ``t``.

    LOOK-AHEAD NOTE
    ~~~~~~~~~~~~~~~
    A naive join of ``compute_returns``'s output to the scores table (without
    the shift) would attach the return *ending* at ``t`` — i.e. the return
    earned from ``t-1`` to ``t``, which is the same data that formed the
    signal. That would let the portfolio benefit from information already
    baked into the signal, a subtle look-ahead bias. The shift(-1) corrects
    this: the value stored at row ``t`` is the return not yet realized at
    formation time.

    LAST DATE HANDLING
    ~~~~~~~~~~~~~~~~~~
    The final month-end in the dataset (2025-08-31) has no subsequent bar,
    so ``fwd_return`` is NaN for all tickers at that date.
    ``form_quintile_portfolios`` will exclude those rows with a logged reason.

    Parameters
    ----------
    df:
        Tidy daily OHLCV DataFrame as returned by ``clean_ohlcv``.

    Returns
    -------
    pd.DataFrame
        Tidy format with columns: ``date, ticker, fwd_return``.
        One row per (monthly rebalance date, ticker). The last rebalance
        date has ``fwd_return = NaN`` for every ticker.
    """
    monthly = resample_ohlcv(df, freq="ME")
    monthly_ret = compute_returns(monthly, method="simple")

    # monthly_ret["return"] at date t = adj_close_t / adj_close_{t-1} - 1
    # We want fwd_return at t = return earned from t to t+1
    #                         = the "return" value that currently sits at t+1
    # shift(-1) pulls the next row's value into the current row (per ticker).
    out = monthly_ret[["date", "ticker", "return"]].copy()
    out["fwd_return"] = out.groupby("ticker")["return"].shift(-1)
    out = out.drop(columns="return")

    n_nan = out["fwd_return"].isna().sum()
    logger.info(
        "build_forward_returns: %d rows, %d with fwd_return=NaN "
        "(last month-end per ticker, expected %d)",
        len(out),
        n_nan,
        out["ticker"].nunique(),
    )
    return out.sort_values(["date", "ticker"]).reset_index(drop=True)


def form_quintile_portfolios(
    df: pd.DataFrame,
    signal_col: str,
    ret_col: str,
) -> pd.DataFrame:
    """
    Sort tickers into five quintile portfolios at each rebalance date.

    QUINTILE DIRECTION CONVENTION (critical — easy to invert by accident)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Tickers are sorted by ``signal_col`` **descending** at each date, then
    split into five equal-sized buckets by rank position:

        Q5 = top quintile    = highest signal value = most desirable
        Q4 = second quintile
        Q3 = middle quintile
        Q2 = fourth quintile
        Q1 = bottom quintile = lowest signal value  = least desirable

    Both ``value_score_proxy`` and ``momentum_score`` are already defined
    so that higher = more desirable (value: higher score = cheaper; momentum:
    higher score = stronger winner). This means Q5 is the value quintile on
    value scores and the winner quintile on momentum scores — no sign flip
    needed inside this function.

    BUCKET SIZES
    ~~~~~~~~~~~~
    Splitting is done by rank position using ``np.array_split(np.arange(n), 5)``,
    which distributes any remainder across the first buckets. For n=51:
    sizes are [11, 10, 10, 10, 10] (Q5 gets the extra ticker). For n=50:
    all buckets are [10, 10, 10, 10, 10]. Sizes are deterministic and do not
    depend on score clustering or duplicate values — unlike cutting on raw
    score quantiles, which can produce unequal buckets when scores tie.

    FORWARD RETURN
    ~~~~~~~~~~~~~~
    ``ret_col`` must already contain the *forward* holding-period return (the
    return from ``t`` to ``t+1``), not the return used to form the signal.
    Build this with ``build_forward_returns()`` before calling here.
    Rebalance dates with NaN ``ret_col`` (e.g. the final date with no next
    period) are excluded with a logged reason, never silently averaged in.

    EQUAL WEIGHTS WITHIN QUINTILE
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Portfolio return = simple average of ``ret_col`` across n_holdings
    tickers. Each holding contributes 1/n_holdings weight. Simple (not log)
    returns are used because this is a cross-sectional weighted sum —
    consistent with Week 1 Task 5's portfolio construction.

    Parameters
    ----------
    df:
        Tidy DataFrame with at least columns ``date``, ``ticker``,
        ``signal_col``, and ``ret_col``. Typically produced by merging
        the output of ``compute_value_score`` / ``compute_momentum_score``
        with the output of ``build_forward_returns``.
    signal_col:
        Column to rank and sort by (e.g. ``"value_score_proxy"`` or
        ``"momentum_score"``).
    ret_col:
        Column containing the forward holding-period return
        (e.g. ``"fwd_return"``).

    Returns
    -------
    pd.DataFrame
        Tidy format with columns:
        ``date, quintile, portfolio_return, n_holdings``.
        One row per (rebalance date, quintile). Sorted by (date, quintile).
    """
    # Identify and exclude dates with no valid forward return
    all_dates = df["date"].unique()
    valid_mask = df.groupby("date")[ret_col].transform(lambda x: x.notna().all())
    excluded_dates = sorted(df.loc[~valid_mask, "date"].unique())
    if excluded_dates:
        logger.info(
            "form_quintile_portfolios: excluding %d date(s) with missing %s "
            "(no forward return period): %s",
            len(excluded_dates),
            ret_col,
            [str(d.date()) for d in excluded_dates],
        )

    working = df[valid_mask & df[ret_col].notna()].copy()

    records: list[dict] = []
    for date, grp in working.groupby("date"):
        # Sort descending by signal: position 0 = highest score = Q5
        sorted_grp = grp.sort_values(signal_col, ascending=False).reset_index(drop=True)
        n = len(sorted_grp)

        # Split by position: np.array_split distributes remainder into first buckets.
        # With n=51: sizes [11,10,10,10,10]; with n=50: [10,10,10,10,10].
        position_splits = np.array_split(np.arange(n), 5)

        for q_idx, positions in enumerate(position_splits):
            quintile = 5 - q_idx  # first split (highest scores) → Q5
            bucket = sorted_grp.iloc[positions]
            records.append({
                "date": date,
                "quintile": quintile,
                "portfolio_return": bucket[ret_col].mean(),
                "n_holdings": len(bucket),
            })

    out = pd.DataFrame(records).sort_values(["date", "quintile"]).reset_index(drop=True)

    logger.info(
        "form_quintile_portfolios: %d rows (%d dates × 5 quintiles) "
        "using signal='%s', ret='%s'",
        len(out),
        out["date"].nunique(),
        signal_col,
        ret_col,
    )
    return out


def compute_factor_performance_stats(
    quintile_df: pd.DataFrame,
    periods_per_year: int = 12,
    rf: float = 0.0,
) -> pd.DataFrame:
    """
    Compute annualised performance statistics for each quintile portfolio.

    Annualisation convention (monthly rebalancing → 12 periods/year):
        ann_return = mean(r)  × periods_per_year
        ann_vol    = std(r)   × sqrt(periods_per_year)
        Sharpe     = (ann_return - rf) / ann_vol

    This matches the convention used in Week 1 Task 5
    (geometric for portfolios there, arithmetic here — the difference is
    small over monthly horizons and arithmetic is standard for factor
    Sharpe comparisons in the literature).

    RISK-FREE RATE
    ~~~~~~~~~~~~~~
    ``rf`` defaults to 0.0. No risk-free rate adjustment is made unless
    the caller passes one. All Sharpe ratios produced here are therefore
    excess-return Sharpes relative to 0%, consistent with Week 1. This
    is stated explicitly here so no reader mistakes them for T-bill-adjusted
    Sharpes.

    MAX DRAWDOWN
    ~~~~~~~~~~~~
    Computed from the compounded wealth index W_t = cumprod(1 + r_t),
    not from raw monthly returns. Drawdown at t = W_t / cummax(W_t) - 1.
    Max drawdown = min over all t. This is the correct definition; using
    raw monthly returns instead would understate drawdowns that span
    multiple losing months.

    Parameters
    ----------
    quintile_df:
        Tidy DataFrame with columns ``date``, ``quintile``,
        ``portfolio_return`` — as returned by ``form_quintile_portfolios``.
    periods_per_year:
        Number of return observations per year. Default 12 (monthly).
    rf:
        Annualised risk-free rate for Sharpe calculation. Default 0.0.

    Returns
    -------
    pd.DataFrame
        One row per quintile (1–5), columns:
        ``quintile, ann_return, ann_vol, sharpe, max_drawdown, n_periods``.
        Sorted by quintile ascending.
    """
    records: list[dict] = []
    for q, grp in quintile_df.groupby("quintile"):
        r = grp.sort_values("date")["portfolio_return"].values
        n = len(r)
        ann_ret = r.mean() * periods_per_year
        ann_vol = r.std(ddof=1) * np.sqrt(periods_per_year)
        sharpe  = (ann_ret - rf) / ann_vol if ann_vol > 0 else np.nan
        wealth  = np.cumprod(1 + r)
        drawdown = wealth / np.maximum.accumulate(wealth) - 1
        max_dd  = drawdown.min()
        records.append({
            "quintile":     q,
            "ann_return":   ann_ret,
            "ann_vol":      ann_vol,
            "sharpe":       sharpe,
            "max_drawdown": max_dd,
            "n_periods":    n,
        })
    out = pd.DataFrame(records).sort_values("quintile").reset_index(drop=True)
    logger.info(
        "compute_factor_performance_stats: %d quintiles, rf=%.1f%%, "
        "periods_per_year=%d",
        len(out), rf * 100, periods_per_year,
    )
    return out


def compute_spread_series(
    quintile_df: pd.DataFrame,
    long_q: int = 5,
    short_q: int = 1,
) -> pd.Series:
    """
    Build the per-date long-short spread series: return_long_q - return_short_q.

    The returned Series is indexed by date and sorted chronologically.
    Use this to compute spread Sharpe / vol / drawdown and for cross-factor
    correlation — the average of this series equals Q5_avg - Q1_avg but
    the full series is needed for anything beyond the mean.

    Parameters
    ----------
    quintile_df:
        Output of ``form_quintile_portfolios``.
    long_q:
        Quintile to go long (default 5 = highest signal = most desirable).
    short_q:
        Quintile to go short (default 1 = lowest signal = least desirable).

    Returns
    -------
    pd.Series
        Index: date. Values: long_q return − short_q return per period.
    """
    wide = quintile_df.pivot(index="date", columns="quintile", values="portfolio_return")
    spread = wide[long_q] - wide[short_q]
    spread.name = f"Q{long_q}_minus_Q{short_q}"
    return spread.sort_index()

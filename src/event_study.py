"""
Event study utilities for Week 4: earnings announcement event study.

Task 2 (this module): data preparation
  load_earnings_events   → pull usable earnings records from yfinance
  align_to_trading_days  → map each event to its correct t=0 trading day
  build_event_panel      → apply estimation/event-window quality filters

Task 3 (this module): abnormal-return computation
  estimate_market_model     → fit R_i = α + β·R_SPY on the estimation window
  compute_abnormal_returns  → compute AR_t and CAR over the event window

Task 4 (this module): aggregation and statistical testing
  compute_aar_caar          → AAR and CAAR series across all 11 event-window days
  cross_sectional_ttest     → per-day t-statistic and p-value table
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd
from scipy import stats as _scipy_stats
import yfinance as yf

# Canonical column order for AR day-offsets (−5 … +5 relative to t=0)
AR_COL_ORDER: list[str] = [
    "AR_-5", "AR_-4", "AR_-3", "AR_-2", "AR_-1",
    "AR_0",
    "AR_+1", "AR_+2", "AR_+3", "AR_+4", "AR_+5",
]


def _ar_col(offset: int) -> str:
    """Column label for the abnormal return at event-window day `offset`."""
    return "AR_0" if offset == 0 else f"AR_{offset:+d}"


def load_earnings_events(
    tickers: list[str],
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
) -> pd.DataFrame:
    """Pull usable earnings events for all tickers in [start, end].

    A usable event has non-null EPS Estimate, Reported EPS, and Surprise(%)
    — the identical usability rule used in the Task 1 feasibility check.

    Args:
        tickers: list of ticker symbols (SPY excluded by convention).
        start: window start (inclusive). Strings like "2020-08-30" are accepted.
        end: window end (inclusive).

    Returns:
        Tidy DataFrame with columns: ticker, event_date (tz-aware UTC),
        eps_estimate, eps_actual, surprise_pct. One row per usable event.
    """
    start_ts = pd.Timestamp(start, tz="UTC")
    end_ts = pd.Timestamp(end, tz="UTC")

    rows: list[dict] = []
    for ticker in tickers:
        t = yf.Ticker(ticker)
        ed = t.get_earnings_dates(limit=50)
        if ed is None or len(ed) == 0:
            time.sleep(0.25)
            continue
        ed.index = ed.index.tz_convert("UTC")
        mask = (ed.index >= start_ts) & (ed.index <= end_ts)
        window = ed[mask].dropna(subset=["EPS Estimate", "Reported EPS", "Surprise(%)"])
        for event_date, row in window.iterrows():
            rows.append(
                {
                    "ticker": ticker,
                    "event_date": event_date,
                    "eps_estimate": row["EPS Estimate"],
                    "eps_actual": row["Reported EPS"],
                    "surprise_pct": row["Surprise(%)"],
                }
            )
        time.sleep(0.25)

    if not rows:
        return pd.DataFrame(
            columns=["ticker", "event_date", "eps_estimate", "eps_actual", "surprise_pct"]
        )
    return pd.DataFrame(rows)


def align_to_trading_days(
    events_df: pd.DataFrame,
    trading_calendar: pd.DatetimeIndex,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Add t0_date to each event using per-event BMO/AMC timestamp logic.

    Convention (Task 1 methodology §4):
      BMO (hour ≤ 10 ET): t0 = event's own calendar date, rolled forward to
        the next valid trading day if that date falls on a weekend or holiday.
      AMC (hour ≥ 14 ET): t0 = first valid trading day strictly *after* the
        event's calendar date.
      Mid-day (10 < hour < 14): routed to ambiguous_df and excluded.

    Args:
        events_df: output of load_earnings_events (must contain event_date).
        trading_calendar: sorted DatetimeIndex of valid trading dates (tz-naive),
            typically SPY's dates from the cleaned OHLCV data.

    Returns:
        (aligned_df, ambiguous_df).
        aligned_df: events_df with t0_date column added (ambiguous events excluded).
        ambiguous_df: excluded events with columns ticker, event_date, hour_et.
    """
    td = pd.DatetimeIndex(trading_calendar).normalize().unique().sort_values()

    aligned: list[dict] = []
    ambiguous: list[dict] = []

    for _, row in events_df.iterrows():
        et_dt = row["event_date"].tz_convert("US/Eastern")
        hour = et_dt.hour
        cal_date = pd.Timestamp(et_dt.date())

        if hour <= 10:
            # BMO: t0 = cal_date, rolled to next valid trading day if needed
            idx = int(td.searchsorted(cal_date, side="left"))
            if idx >= len(td):
                continue
            t0 = td[idx]
        elif hour >= 14:
            # AMC: t0 = first trading day strictly after cal_date
            idx = int(td.searchsorted(cal_date, side="right"))
            if idx >= len(td):
                continue
            t0 = td[idx]
        else:
            ambiguous.append(
                {
                    "ticker": row["ticker"],
                    "event_date": row["event_date"],
                    "hour_et": hour,
                }
            )
            continue

        new_row = row.to_dict()
        new_row["t0_date"] = t0
        aligned.append(new_row)

    aligned_df = pd.DataFrame(aligned)
    ambiguous_df = (
        pd.DataFrame(ambiguous)
        if ambiguous
        else pd.DataFrame(columns=["ticker", "event_date", "hour_et"])
    )
    return aligned_df, ambiguous_df


def build_event_panel(
    events_df: pd.DataFrame,
    returns_df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build the validated event panel and rejection log.

    Two sequential filters:
      1. Estimation-window filter: the ticker must have ≥ 200 non-missing
         return observations in the [-260, -11] window relative to t0.
      2. Event-window completeness filter: all 11 trading days in the
         [-5, +5] window must have non-missing return data.

    For every surviving event, asserts that the estimation window
    (ending at t0-11) and event window (starting at t0-5) do not overlap.

    Args:
        events_df: output of align_to_trading_days (must contain t0_date).
        returns_df: wide DataFrame indexed by trading date (tz-naive), one
            column per ticker. Typically built with:
            returns_long.pivot_table(index="date", columns="ticker", values="return")

    Returns:
        (panel_df, rejection_log_df).
        panel_df columns: ticker, event_date, t0_date, eps_estimate, eps_actual,
            surprise_pct, est_start, est_end, evt_start, evt_end, est_valid_obs.
        rejection_log_df columns: ticker, event_date, reason.
        Reason values: insufficient_estimation_history, incomplete_event_window.
    """
    td = returns_df.index.sort_values().normalize()

    panel_rows: list[dict] = []
    reject_rows: list[dict] = []

    for _, event in events_df.iterrows():
        ticker = event["ticker"]
        t0 = pd.Timestamp(event["t0_date"]).normalize()

        # Locate t0 in the trading calendar
        pos = int(td.searchsorted(t0))
        if pos >= len(td) or td[pos] != t0:
            reject_rows.append(
                {
                    "ticker": ticker,
                    "event_date": event["event_date"],
                    "reason": "insufficient_estimation_history",
                }
            )
            continue

        # Estimation window: positions [pos-260, pos-11] inclusive
        est_start_pos = pos - 260
        est_end_pos = pos - 11

        if est_start_pos < 0:
            reject_rows.append(
                {
                    "ticker": ticker,
                    "event_date": event["event_date"],
                    "reason": "insufficient_estimation_history",
                }
            )
            continue

        if ticker not in returns_df.columns:
            reject_rows.append(
                {
                    "ticker": ticker,
                    "event_date": event["event_date"],
                    "reason": "insufficient_estimation_history",
                }
            )
            continue

        est_dates = td[est_start_pos : est_end_pos + 1]
        est_valid_obs = int(returns_df.loc[est_dates, ticker].notna().sum())

        if est_valid_obs < 200:
            reject_rows.append(
                {
                    "ticker": ticker,
                    "event_date": event["event_date"],
                    "reason": "insufficient_estimation_history",
                }
            )
            continue

        # Event window: positions [pos-5, pos+5] inclusive
        evt_start_pos = pos - 5
        evt_end_pos = pos + 5

        if evt_end_pos >= len(td):
            reject_rows.append(
                {
                    "ticker": ticker,
                    "event_date": event["event_date"],
                    "reason": "incomplete_event_window",
                }
            )
            continue

        evt_dates = td[evt_start_pos : evt_end_pos + 1]
        if returns_df.loc[evt_dates, ticker].isna().any():
            reject_rows.append(
                {
                    "ticker": ticker,
                    "event_date": event["event_date"],
                    "reason": "incomplete_event_window",
                }
            )
            continue

        # Non-overlap assertion: est ends at pos-11, event starts at pos-5
        est_end_date = td[est_end_pos]
        evt_start_date = td[evt_start_pos]
        assert est_end_date < evt_start_date, (
            f"Overlap for {ticker} at t0={t0}: "
            f"est_end={est_end_date}, evt_start={evt_start_date}"
        )

        panel_rows.append(
            {
                "ticker": ticker,
                "event_date": event["event_date"],
                "t0_date": t0,
                "eps_estimate": event["eps_estimate"],
                "eps_actual": event["eps_actual"],
                "surprise_pct": event["surprise_pct"],
                "est_start": est_dates[0],
                "est_end": est_dates[-1],
                "evt_start": evt_dates[0],
                "evt_end": evt_dates[-1],
                "est_valid_obs": est_valid_obs,
            }
        )

    panel_df = pd.DataFrame(panel_rows)
    rejection_df = (
        pd.DataFrame(reject_rows)
        if reject_rows
        else pd.DataFrame(columns=["ticker", "event_date", "reason"])
    )
    return panel_df, rejection_df


def estimate_market_model(
    ticker: str,
    t0_date: pd.Timestamp,
    returns_wide: pd.DataFrame,
    est_start: pd.Timestamp,
    est_end: pd.Timestamp,
) -> tuple[float, float, int]:
    """Fit the market model R_i = α + β·R_SPY on the estimation window.

    Method: scipy.stats.linregress (ordinary least squares). Only paired
    observations where both the ticker and SPY have non-missing returns are
    included; the count of such observations is returned as n_obs_used and
    should match the event's est_valid_obs from Task 2's panel.

    Args:
        ticker: ticker symbol.
        t0_date: event date (t=0); tz-naive trading-day Timestamp.
        returns_wide: wide DataFrame (date × ticker) of daily returns.
        est_start: first date of estimation window (inclusive).
        est_end: last date of estimation window (inclusive).

    Returns:
        (alpha_hat, beta_hat, n_obs_used).

    Raises:
        AssertionError: if any estimation-window date falls inside the
            event window [t0−5, t0+5].
        ValueError: if fewer than 2 valid paired observations are found.
    """
    t0 = pd.Timestamp(t0_date).normalize()
    est_end_ts = pd.Timestamp(est_end).normalize()
    est_start_ts = pd.Timestamp(est_start).normalize()

    # Non-overlap assertion: est_end must be strictly before the event window
    # (event window starts at t0 − 5 trading days)
    td = returns_wide.index.normalize().sort_values()
    t0_pos = int(td.searchsorted(t0))
    evt_start_date = td[t0_pos - 5]
    assert est_end_ts < evt_start_date, (
        f"[{ticker} t0={t0.date()}] estimation window end {est_end_ts.date()} "
        f"must precede event window start {evt_start_date.date()}"
    )

    # Estimation-window returns: label-based inclusive slice
    est_data = returns_wide.loc[est_start_ts:est_end_ts, [ticker, "SPY"]]
    valid = est_data.dropna()
    n_obs = len(valid)

    if n_obs < 2:
        raise ValueError(
            f"Only {n_obs} valid paired observations in estimation window "
            f"for {ticker} at t0={t0.date()}"
        )

    r_i = valid[ticker].to_numpy(dtype=float)
    r_m = valid["SPY"].to_numpy(dtype=float)

    # OLS: x = R_SPY (independent), y = R_ticker (dependent)
    result = _scipy_stats.linregress(r_m, r_i)
    return float(result.intercept), float(result.slope), n_obs


def compute_abnormal_returns(
    ticker: str,
    t0_date: pd.Timestamp,
    returns_wide: pd.DataFrame,
    alpha_hat: float,
    beta_hat: float,
    evt_start: pd.Timestamp,
    evt_end: pd.Timestamp,
) -> dict[str, float]:
    """Compute daily AR_t and CAR over the [-5, +5] event window.

    AR_t = R_i,t − (alpha_hat + beta_hat · R_SPY,t)
    CAR  = Σ AR_t  for t in {−5, −4, …, 0, …, +5}

    alpha_hat and beta_hat must come from estimate_market_model and are
    held fixed for all 11 days — no per-day re-fitting.

    Args:
        ticker: ticker symbol.
        t0_date: event date (t=0).
        returns_wide: wide DataFrame (date × ticker) of daily returns.
        alpha_hat, beta_hat: market-model coefficients from estimate_market_model.
        evt_start: first date of event window (t=−5 trading day).
        evt_end: last date of event window (t=+5 trading day).

    Returns:
        Dict with keys AR_-5 … AR_0 … AR_+5 and CAR (all floats).
    """
    t0 = pd.Timestamp(t0_date).normalize()
    evt_start_ts = pd.Timestamp(evt_start).normalize()
    evt_end_ts = pd.Timestamp(evt_end).normalize()

    td = returns_wide.index.normalize().sort_values()
    t0_pos = int(td.searchsorted(t0))

    # Event-window data via inclusive label slice
    evt_data = returns_wide.loc[evt_start_ts:evt_end_ts, [ticker, "SPY"]]
    assert len(evt_data) == 11, (
        f"Expected 11 event-window rows for {ticker} at t0={t0.date()}, "
        f"got {len(evt_data)}"
    )

    ar_dict: dict[str, float] = {}
    for date, row in evt_data.iterrows():
        date_pos = int(td.searchsorted(pd.Timestamp(date).normalize()))
        offset = date_pos - t0_pos
        ar = float(row[ticker]) - (alpha_hat + beta_hat * float(row["SPY"]))
        ar_dict[_ar_col(offset)] = ar

    car = sum(ar_dict[c] for c in AR_COL_ORDER)
    ar_dict["CAR"] = car
    return ar_dict


def compute_aar_caar(
    ar_df: pd.DataFrame,
) -> pd.DataFrame:
    """Compute AAR and CAAR across all events for each event-window day.

    AAR_t  = cross-sectional mean of AR_t across all N events.
    CAAR_t = running cumulative sum of AAR from day -5 through day t.

    Also computes, for each event i and day t, the partial cumulative
    abnormal return CAR_i[-5:t] = sum(AR_{-5} … AR_t) for that event.
    The cross-sectional mean of CAR_i[-5:t] reproduces CAAR_t exactly
    (second identity check) and its standard deviation is used for
    confidence interval construction in plotting.

    Args:
        ar_df: output of the Task 3 full-panel loop. Must contain columns
            AR_-5 … AR_+5 and CAR. 792 rows (one per event).

    Returns:
        DataFrame with one row per event-window day (11 rows), columns:
            day_offset (int, -5 … +5),
            aar        (float),
            caar       (float),
            caar_se    (float)  — std(CAR_i[-5:t]) / sqrt(N), for 95% CI.
    """
    n = len(ar_df)
    ar_matrix = ar_df[AR_COL_ORDER].to_numpy(dtype=float)  # (N, 11)

    aar = ar_matrix.mean(axis=0)  # (11,)
    caar = np.cumsum(aar)          # (11,) — running sum of AAR

    # Partial cumulative AR for each event: cumsum along the day axis
    partial_car = np.cumsum(ar_matrix, axis=1)  # (N, 11)
    caar_from_partial = partial_car.mean(axis=0)  # must equal caar
    assert np.allclose(caar, caar_from_partial, atol=1e-12), (
        "CAAR from cumulative AAR does not match CAAR from mean of partial CARs"
    )

    caar_se = partial_car.std(axis=1, ddof=1).mean() / np.sqrt(n)  # scalar fallback
    # Per-day SE: std across events of each day's partial CAR
    caar_se_per_day = partial_car.std(axis=0, ddof=1) / np.sqrt(n)  # (11,)

    offsets = list(range(-5, 6))
    return pd.DataFrame(
        {
            "day_offset": offsets,
            "aar": aar,
            "caar": caar,
            "caar_se": caar_se_per_day,
        }
    )


def cross_sectional_ttest(
    ar_df: pd.DataFrame,
) -> pd.DataFrame:
    """Compute cross-sectional t-test for AAR=0 on each event-window day.

    Method: for each day t, treat the N=792 AR_t values as a sample and
    test whether the cross-sectional mean is significantly different from
    zero. t-statistic = AAR_t / (std_t / sqrt(N)), df = N-1.

    INDEPENDENCE ASSUMPTION: this test assumes that the N event-window
    AR_t observations are cross-sectionally independent. The Task 2
    clustering report found meaningful overlap (105 t0_dates with 3+
    events; one date with 8 simultaneous events). When multiple events
    share the same t0_date, their AR_t values are exposed to the same
    market moves on the same calendar day, inducing positive cross-
    sectional correlation. The t-statistics below are therefore likely
    overstated in significance. A clustered standard-error correction
    (e.g. by t0_date) is the appropriate fix but is out of scope here.

    Args:
        ar_df: output of the Task 3 full-panel loop. Must contain AR_-5
            through AR_+5 columns.

    Returns:
        DataFrame with one row per event-window day (11 rows), columns:
            day_offset (int), aar (float), std (float), t_stat (float),
            p_value (float), sig (str — "***"/"**"/"*"/"" for
            1%/5%/10%/none significance levels).
    """
    n = len(ar_df)
    rows = []
    for col in AR_COL_ORDER:
        vals = ar_df[col].to_numpy(dtype=float)
        mean_ = vals.mean()
        std_ = vals.std(ddof=1)
        t_stat = mean_ / (std_ / np.sqrt(n))
        p_val = float(2 * _scipy_stats.t.sf(abs(t_stat), df=n - 1))
        if p_val < 0.01:
            sig = "***"
        elif p_val < 0.05:
            sig = "**"
        elif p_val < 0.10:
            sig = "*"
        else:
            sig = ""
        offset = int(col.replace("AR_", "").replace("+", ""))
        rows.append(
            {
                "day_offset": offset,
                "aar": mean_,
                "std": std_,
                "t_stat": t_stat,
                "p_value": p_val,
                "sig": sig,
            }
        )
    return pd.DataFrame(rows)

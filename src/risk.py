"""
Risk and return metrics for portfolio return series.

Core function: compute_risk_metrics()
    Accepts a daily simple-return series and an annualised risk-free rate,
    returns annualised return (CAGR), annualised volatility, Sharpe ratio,
    max drawdown with start/end dates, and drawdown duration to recovery.

Annualisation convention
------------------------
252 trading days per year (default).

Annualised return
    CAGR: (terminal_wealth) ^ (252 / n_days) - 1.
    Uses the actual number of trading days in the series, not a fixed 252.

Annualised vol
    daily_std(ddof=1) × √252.

Sharpe ratio
    (ann_return - rf_annual) / ann_vol.
    rf_annual is the caller's responsibility; this module never hard-codes 0%.

Max drawdown
    From the cumulative wealth index W_t = ∏(1 + r_t).
    DD_t = W_t / max(W_1..W_t) - 1.  max_dd = min(DD_t).  Reported negative.

Drawdown duration
    Trading days from the pre-drawdown peak to full recovery (W_t ≥ peak).
    If the series ends below the peak, duration = None and recovered = False.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize as _sp_minimize


def compute_risk_metrics(
    returns: pd.Series,
    rf_annual: float,
    periods_per_year: int = 252,
) -> dict:
    """
    Compute standard risk/return metrics for a daily return series.

    Parameters
    ----------
    returns : pd.Series
        Daily simple returns, indexed by date, no NaNs.
    rf_annual : float
        Annualised risk-free rate (e.g. 0.045 for 4.5%), used to compute
        the Sharpe ratio.
    periods_per_year : int
        Trading days per year for annualisation. Default 252.

    Returns
    -------
    dict with keys:
        annualized_return       float  — CAGR over the full sample
        annualized_vol          float  — daily std × √periods_per_year
        sharpe_ratio            float  — (ann_ret - rf) / ann_vol
        max_drawdown            float  — negative decimal, e.g. -0.23
        max_drawdown_start      date   — peak date preceding the max drawdown
        max_drawdown_end        date   — trough date of the max drawdown
        drawdown_duration_days  int|None — trading days peak→recovery; None if
                                           the series has not recovered by end
        recovered               bool   — False when duration is None
    """
    r = returns.dropna()
    if len(r) == 0:
        raise ValueError("returns is empty after dropping NaNs")

    # ------------------------------------------------------------------ #
    # Cumulative wealth index                                              #
    # ------------------------------------------------------------------ #
    wealth = (1 + r).cumprod()

    # ------------------------------------------------------------------ #
    # Annualised return (CAGR)                                            #
    # ------------------------------------------------------------------ #
    n_days = len(r)
    n_years = n_days / periods_per_year
    ann_return = wealth.iloc[-1] ** (1.0 / n_years) - 1.0

    # ------------------------------------------------------------------ #
    # Annualised volatility                                                #
    # ------------------------------------------------------------------ #
    ann_vol = r.std(ddof=1) * np.sqrt(periods_per_year)

    # ------------------------------------------------------------------ #
    # Sharpe ratio                                                         #
    # ------------------------------------------------------------------ #
    sharpe = (ann_return - rf_annual) / ann_vol if ann_vol > 0 else np.nan

    # ------------------------------------------------------------------ #
    # Max drawdown — peak, trough, magnitude                              #
    # ------------------------------------------------------------------ #
    running_max = wealth.cummax()
    drawdown = wealth / running_max - 1.0
    max_dd = float(drawdown.min())

    trough_date = drawdown.idxmin()
    # Peak is the last date wealth reached its high-water mark before the trough
    peak_date = wealth.loc[:trough_date].idxmax()
    peak_wealth_level = float(wealth.loc[peak_date])

    # ------------------------------------------------------------------ #
    # Drawdown duration (peak → recovery)                                 #
    # ------------------------------------------------------------------ #
    wealth_from_trough = wealth.loc[trough_date:]
    recovered_mask = wealth_from_trough >= peak_wealth_level * (1.0 - 1e-10)

    if recovered_mask.any():
        recovery_date = wealth_from_trough.loc[recovered_mask].index[0]
        peak_pos = wealth.index.get_loc(peak_date)
        recovery_pos = wealth.index.get_loc(recovery_date)
        drawdown_duration: int | None = int(recovery_pos - peak_pos)
        recovered = True
    else:
        drawdown_duration = None
        recovered = False

    return {
        "annualized_return": float(ann_return),
        "annualized_vol": float(ann_vol),
        "sharpe_ratio": float(sharpe),
        "max_drawdown": float(max_dd),
        "max_drawdown_start": peak_date,
        "max_drawdown_end": trough_date,
        "drawdown_duration_days": drawdown_duration,
        "recovered": recovered,
    }


def compute_rp_weights(
    ret_wide: pd.DataFrame,
    rebal_date,
    lookback: int = 60,
    min_obs: int = 20,
) -> "pd.Series | None":
    """
    Vol-inverse risk-parity weights using trailing history strictly before rebal_date.

    Parameters
    ----------
    ret_wide   : wide daily return DataFrame (index=date, columns=ticker)
    rebal_date : date or Timestamp — only rows strictly before this date are used
    lookback   : trailing-window length in trading days (default 60)
    min_obs    : minimum rows required; returns None if not met (default 20)

    Returns
    -------
    pd.Series indexed by ticker, normalised to sum=1, or None if < min_obs rows.
    """
    history = ret_wide[ret_wide.index < rebal_date].tail(lookback)
    if len(history) < min_obs:
        return None
    inv_vols = 1.0 / history.std(ddof=1)
    return inv_vols / inv_vols.sum()


def compute_beta(
    portfolio_returns: pd.Series,
    market_returns: pd.Series,
) -> float:
    """
    CAPM beta: cov(R_p, R_m, ddof=1) / var(R_m, ddof=1).

    Inner-joins on common dates and drops NaNs before computing.
    """
    aligned = pd.concat(
        [portfolio_returns.rename("port"), market_returns.rename("mkt")],
        axis=1,
        sort=False,
    ).dropna()
    cov_mat = aligned.cov(ddof=1)
    return float(cov_mat.loc["port", "mkt"] / cov_mat.loc["mkt", "mkt"])


def compute_diversification_ratio(
    returns_wide: pd.DataFrame,
    weights: "np.ndarray | None" = None,
) -> float:
    """
    Diversification ratio = weighted-average individual annualised vol / portfolio vol.

    Parameters
    ----------
    returns_wide : wide daily return DataFrame (index=date, columns=ticker)
    weights      : per-stock weights (must sum to 1); defaults to equal-weight

    Returns
    -------
    float — ratio > 1 means the portfolio vol is below the weighted average
    constituent vol.
    """
    n = returns_wide.shape[1]
    w = np.full(n, 1.0 / n) if weights is None else np.asarray(weights, dtype=float)
    w = w / w.sum()

    indiv_vols = returns_wide.std(ddof=1).values  # cancels with √PPY in ratio
    weighted_avg_vol = float(w @ indiv_vols)

    port_daily = returns_wide.values @ w
    port_vol = float(port_daily.std(ddof=1))

    return weighted_avg_vol / port_vol


def solve_min_variance(
    mu: np.ndarray,
    cov: np.ndarray,
    target_return: float,
    max_weight: float = 0.10,
) -> tuple[np.ndarray, bool, float, float]:
    """
    Minimum-variance portfolio for a given target annualised return.

    Parameters
    ----------
    mu  : array-like, shape (n,) — annualised expected returns per stock
    cov : array-like, shape (n, n) — annualised covariance matrix
    target_return : float — annualised target portfolio return
    max_weight : float — per-stock weight cap (default 0.10)

    Returns
    -------
    weights         np.ndarray, shape (n,)
    success         bool — True if SLSQP converged
    achieved_return float — w @ mu at the solution
    achieved_vol    float — sqrt(w @ cov @ w) at the solution
    """
    mu  = np.asarray(mu, dtype=float)
    cov = np.asarray(cov, dtype=float)
    n   = len(mu)
    w0  = np.full(n, 1.0 / n)

    result = _sp_minimize(
        fun=lambda w: float(w @ cov @ w),
        x0=w0,
        method="SLSQP",
        bounds=[(0.0, max_weight)] * n,
        constraints=[
            {"type": "eq", "fun": lambda w: w.sum() - 1.0},
            {"type": "eq", "fun": lambda w: float(w @ mu) - target_return},
        ],
        options={"ftol": 1e-12, "maxiter": 1000},
    )

    w   = result.x
    ret = float(w @ mu)
    vol = float(np.sqrt(max(w @ cov @ w, 0.0)))
    return w, result.success, ret, vol

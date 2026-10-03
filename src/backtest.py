"""
Transaction cost and turnover utilities for backtesting quintile portfolios.

Core functions
--------------
compute_turnover(weight_history)
    Monthly one-way portfolio turnover from a weight history dict produced
    by factor_utils.compute_quintile_weights().

apply_transaction_costs(returns, turnover, cost_bps)
    Deducts one-way transaction costs from a monthly return series at each
    rebalance date, in the same period as the rebalance that generated the
    turnover.

Cost convention
---------------
All costs in this module are **one-way** (not round-trip). A rebalance that
sells stock A and buys stock B incurs separate cost on each leg. The turnover
metric (sum of absolute weight changes) captures both legs — selling A adds
|Δw_A| and buying B adds |Δw_B|. Multiplying by cost_bps gives total one-way
frictional cost per rebalance.

Round-trip vs one-way:
  - One-way (this module): cost = turnover × cost_bps × 1e-4
  - Round-trip (not used): cost = turnover × 2 × cost_bps × 1e-4

The one-way convention matches academic factor research (e.g. Frazzini,
Israel & Moskowitz 2018). Tasks 2–4 must use apply_transaction_costs
consistently — do not mix conventions across analyses.

Baseline assumption
-------------------
Default cost_bps = 10 (10 basis points one-way). Reasonable for top-50
S&P 500 large-caps (tight bid-ask spreads, deep liquidity). Task 2 will
vary this parameter for break-even analysis.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_turnover(weight_history: dict) -> pd.Series:
    """
    Compute monthly one-way turnover from a per-date weight history.

    Turnover at rebalance date t:

        TO_t = Σ_i |w_t[i] - w_{t-1}[i]|

    summed over all tickers that appear at either date t or t-1.
    Tickers absent at a given date carry weight 0 (complete entry or exit).

    ONE-WAY INTERPRETATION
    ~~~~~~~~~~~~~~~~~~~~~~~
    A full portfolio rotation (sell everything, buy everything new) produces
    TO = 2.0: the outgoing positions each contribute |0 - w_old| and the
    incoming positions contribute |w_new - 0|. With cost_bps = 10 and
    TO = 2.0, apply_transaction_costs deducts 0.20% (20 bps), representing
    10 bps on each of the two legs — not 40 bps.

    LONG-SHORT NOTE
    ~~~~~~~~~~~~~~~
    For a dollar-neutral long-short portfolio where long weights sum to +1
    and short weights sum to -1 (gross notional = 2), the turnover scale is
    the same formula applied to the signed weights. A full rotation of the
    long book contributes TO += 2 and a full rotation of the short book
    another 2, for TO = 4 at maximum. This is correct — each dollar of
    gross notional incurs cost, and the long-short book has 2 dollars of
    gross notional per dollar of net capital.

    Parameters
    ----------
    weight_history:
        Mapping ``{rebalance_date (pd.Timestamp): {ticker (str): weight (float)}}``.
        Produced by ``factor_utils.compute_quintile_weights()``.
        Weights should sum to 1.0 for long-only quintile portfolios, or to 0
        (net) / 2 (gross abs) for dollar-neutral long-short portfolios.

    Returns
    -------
    pd.Series
        Monthly one-way turnover indexed by rebalance date, sorted
        chronologically. The first date has NaN — there is no prior weight
        vector to diff against (the portfolio is being formed from scratch).
    """
    if not weight_history:
        return pd.Series(dtype=float, name="turnover")

    dates = sorted(weight_history.keys())
    turnovers: list[float] = [float("nan")]  # first date: no prior portfolio

    for i in range(1, len(dates)):
        prev_date = dates[i - 1]
        curr_date = dates[i]

        prev_w = weight_history[prev_date]
        curr_w = weight_history[curr_date]

        all_tickers = set(prev_w) | set(curr_w)
        to = sum(
            abs(curr_w.get(t, 0.0) - prev_w.get(t, 0.0))
            for t in all_tickers
        )
        turnovers.append(to)

    result = pd.Series(
        turnovers,
        index=pd.DatetimeIndex(dates),
        name="turnover",
    )

    valid = [v for v in turnovers[1:] if not np.isnan(v)]
    avg_to = float(np.mean(valid)) if valid else float("nan")
    logger.info(
        "compute_turnover: %d dates, avg monthly turnover (excl. first NaN) = %.4f",
        len(dates),
        avg_to,
    )
    return result


def apply_transaction_costs(
    returns: pd.Series,
    turnover: pd.Series,
    cost_bps: float = 10.0,
) -> pd.Series:
    """
    Deduct one-way transaction costs from a monthly return series.

    COST CONVENTION — one-way, same-period deduction
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    Cost is deducted in the SAME period as the rebalance that generated the
    turnover. The rebalance occurs at the start of each holding period
    (month-end t), so the friction reduces the return earned over the
    subsequent month. Charging in the same period is conservative and
    standard in academic backtesting.

    Net return formula:

        net_return_t = gross_return_t - turnover_t × cost_bps × 1e-4

    Example: turnover = 0.40 (40% of portfolio turns over), cost_bps = 10:
        cost = 0.40 × 0.0010 = 0.040% deducted from that month's return.

    ONE-WAY vs ROUND-TRIP
    ~~~~~~~~~~~~~~~~~~~~~
    This function uses the ONE-WAY convention: 1 unit of turnover → 1 leg of
    cost. Do NOT multiply cost_bps by 2 here; that would double-count because
    compute_turnover already captures both legs (outflows AND inflows) in its
    sum of absolute weight changes.

    FIRST-PERIOD HANDLING
    ~~~~~~~~~~~~~~~~~~~~~
    The first rebalance date typically has NaN turnover (no prior portfolio).
    NaN turnover is treated as 0 cost — no cost deduction on the first
    holding period. This is the correct interpretation: if there was no prior
    portfolio, no selling occurred (only buying), and a one-way-cost model
    could reasonably charge only the entry leg. Here we treat the initial
    portfolio construction as cost-free, consistent with the standard
    academic assumption for an inception-date rebalance.

    Parameters
    ----------
    returns:
        Gross monthly return series indexed by rebalance date. May contain
        NaN (passed through unchanged).
    turnover:
        Monthly one-way turnover series from ``compute_turnover()``, indexed
        by the same rebalance dates. NaN entries (typically the first date)
        are treated as 0 cost.
    cost_bps:
        One-way transaction cost in basis points. Default 10. Applied as
        ``cost_decimal = cost_bps × 1e-4``. Task 2 will vary this parameter
        for break-even analysis; keep consistent across Tasks 2–4.

    Returns
    -------
    pd.Series
        Net (cost-adjusted) return series with the same index as ``returns``.
        Periods with NaN returns are returned unchanged (NaN propagates).
    """
    cost_decimal = cost_bps * 1e-4

    # Align turnover to the returns index.
    # Dates in returns not present in turnover → 0 cost (no rebalance info).
    # NaN turnover (first date) → also 0 cost.
    turnover_aligned = turnover.reindex(returns.index).fillna(0.0)

    net_returns = returns - turnover_aligned * cost_decimal

    n_periods = int(returns.notna().sum())
    avg_cost_bps = float((turnover_aligned * cost_decimal).mean() * 1e4)
    logger.info(
        "apply_transaction_costs: %d periods, cost_bps=%.1f (one-way), "
        "avg monthly cost = %.2f bps",
        n_periods,
        cost_bps,
        avg_cost_bps,
    )
    return net_returns


def find_breakeven_cost_bps(
    returns: pd.Series,
    turnover: pd.Series,
    low_bps: float = 0.0,
    high_bps: float = 500.0,
    tol: float = 0.01,
) -> float:
    """
    Bisection search for the one-way cost level at which annualized net return = 0.

    Annualized return metric: arithmetic mean of monthly net returns × 12.
    This matches the analytical approximation
    ``approx_be ≈ gross_ann_return / ann_turnover × 10000``
    and is monotone in cost_bps, so bisection is guaranteed to converge
    given a valid bracket.

    COST CONVENTION
    ~~~~~~~~~~~~~~~
    Uses ``apply_transaction_costs`` internally, so the same one-way,
    same-period convention applies. Do not divide by 2 or otherwise adjust
    the result to convert to round-trip — that would be inconsistent with
    the rest of the backtest.

    BRACKET REQUIREMENT
    ~~~~~~~~~~~~~~~~~~~
    Raises ``ValueError`` if the sign of annualized net return does not
    change across ``[low_bps, high_bps]``:
      - If ann_return at ``low_bps`` ≤ 0: the strategy is already
        net-negative before any frictional costs — no break-even exists.
      - If ann_return at ``high_bps`` ≥ 0: the strategy survives even at
        the ceiling cost — raise the ceiling and retry.

    Parameters
    ----------
    returns:
        Gross monthly return series (indexed by rebalance date).
    turnover:
        Monthly one-way turnover series from ``compute_turnover()``.
    low_bps:
        Lower bound of the search bracket. Default 0.
    high_bps:
        Upper bound of the search bracket. Default 500.
    tol:
        Convergence tolerance in bps. Stops when ``high_bps - low_bps < tol``.
        Default 0.01 (one-hundredth of a basis point).

    Returns
    -------
    float
        Break-even one-way cost in basis points, accurate to within ``tol``.

    Raises
    ------
    ValueError
        If the bracket does not contain a sign change.
    """
    def _ann_net_return(cost_bps: float) -> float:
        net = apply_transaction_costs(returns, turnover, cost_bps)
        return float(net.dropna().mean() * 12)

    f_low  = _ann_net_return(low_bps)
    f_high = _ann_net_return(high_bps)

    if f_low <= 0:
        raise ValueError(
            f"Annualized net return is already ≤ 0 at low_bps={low_bps:.2f} "
            f"(ann_return={f_low:.4%}). No break-even exists in [{low_bps}, {high_bps}]."
        )
    if f_high >= 0:
        raise ValueError(
            f"Annualized net return is still ≥ 0 at high_bps={high_bps:.2f} "
            f"(ann_return={f_high:.4%}). Raise high_bps and retry."
        )

    lo, hi = low_bps, high_bps
    while (hi - lo) > tol:
        mid = (lo + hi) / 2.0
        if _ann_net_return(mid) > 0:
            lo = mid
        else:
            hi = mid

    be = (lo + hi) / 2.0
    logger.info(
        "find_breakeven_cost_bps: converged to %.4f bps (tol=%.4f)",
        be, tol,
    )
    return be

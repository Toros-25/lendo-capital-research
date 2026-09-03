# Week 1 Memo — Setup & Market Data Foundations

**Date:** 2026-09-02

---

## Data Issues Found

The dataset (51 tickers × 5 years, 64,035 rows of daily OHLCV) came in clean. No missing values, no calendar misalignments, no single-day return outliers above the ±50% threshold. The one structural issue is PLTR's late IPO (2020-09-30), which pushes its first computable return to 2020-10-01. The portfolio backtest starts there so all 50 constituents have a valid return on day one.

84 volume spikes were flagged across 26 tickers (defined as 5× the 20-day rolling average). All are traceable to real market events — the largest being NFLX on 2022-04-20 at 25.6× normal volume, coinciding with its first reported subscriber loss and a −35% price drop that day. None were removed; the spikes are informative, not defects.

The most significant issue is **survivorship bias**: the universe is the top-50 S&P 500 constituents as of 2025-08-30, retroactively applied back to 2020. This excludes names that were historically large but have since declined, and includes recent outperformers like PLTR (+1,550% since IPO). All performance figures should be read with that caveat in mind.

---

## Cleaning Decisions

- **Adjusted close only.** All return calculations use `adj_close` (split- and dividend-adjusted). Using raw `close` understates XOM's cumulative 5-year return by roughly 25%.
- **Forward-fill cap.** Up to 2 consecutive missing trading days are forward-filled; volume is set to NaN on filled rows to avoid inflating volume-based signals.
- **Outliers retained.** Volume spikes are flagged in the quality report but kept in the data — they are genuine market events, not data errors.
- **NVDA split handled correctly.** The 10-for-1 split on 2024-06-10 produces a +0.75% `adj_close` return, correctly falling below the ±50% outlier threshold.
- **Portfolio start date: 2020-10-01.** This is the first date all 50 stocks have a valid return (PLTR's first full trading day after IPO). The alternative — starting 2020-08-31 with 49 stocks — adds complexity for 21 days out of 1,234.

---

## Key Observations

**Return distributions.** All five tickers tested (SPY, KO, JPM, NVDA, PLTR) reject normality (Jarque-Bera p ≈ 0) with excess kurtosis in every case. Standard risk metrics that assume Gaussian returns will understate tail risk.

**√T scaling.** The daily-to-monthly volatility scaling rule holds reasonably well for SPY, KO, JPM, and NVDA (realized ratios 0.91–1.02). It breaks down for PLTR (ratio 1.48), driven by volatility clustering and autocorrelation — so any annualized vol figure for PLTR using √252 is understated.

**Portfolio results** (2020-10-01 → 2025-08-29, monthly rebalance, rf = 0%):

| Portfolio | Ann. Return | Ann. Vol | Sharpe |
|---|---|---|---|
| Equal-weight (50 stocks) | 24.47% | 17.65% | 1.387 |
| Value-weight (50 stocks) | 21.30% | 20.63% | 1.032 |
| SPY benchmark | 15.91% | 17.39% | 0.915 |

Equal-weight outperforms value-weight on both return and Sharpe. The reason VW is *more* volatile than EW is concentration: VW is 12.67% NVDA (3.3%/day vol), which pulls aggregate risk above the diversified EW average. Both portfolios beat SPY, though the margin is inflated by survivorship bias — the universe is built with hindsight.

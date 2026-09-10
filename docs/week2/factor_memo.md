# Week 2 Factor Memo — Value Proxy & Momentum
**Lendo Capital Quant Research Internship**  
Period analysed: Aug 2021 – Jul 2025 (48 monthly holding periods)  
Prepared: 2025-09-05

---

## Methodology

**Universe:** 51 tickers — the top 50 S&P 500 constituents by market
capitalisation as of 2025-08-30, plus SPY as a market benchmark. Applied
retroactively to August 2021 (when sufficient signal history became available).

**Value signal — contrarian trailing-return proxy (not fundamental value):**
No book value, earnings, or Price-to-Book data was available for this project.
The value signal is therefore a _proxy_: `value_score_proxy = −(trailing 12-month
adj_close return)`. Stocks that fell the most over the prior year are treated as
"cheaper." This is a real simplification; it is not equivalent to a Fama-French
HML or any earnings-based value factor, and the label "value" should be read as
shorthand for this specific contrarian construction throughout.

**Momentum signal (standard definition):** 12-1 price momentum per
Jegadeesh-Titman — cumulative return from 12 months before the rebalance date to
1 month before, skipping the most recent month to avoid short-term reversal
contamination. `momentum_score = P_{t-1}/P_{t-12} − 1`. This is the textbook
definition, not a proxy.

**Quintile construction:** At each monthly rebalance date, tickers with a valid
score are sorted by that score descending and split into five equal-sized buckets
by rank position (`np.array_split`). Q5 = highest score (most desirable under
each signal's own convention); Q1 = lowest score. For value: Q5 = most fallen =
"cheapest"; for momentum: Q5 = biggest prior winner. Bucket sizes: 11/10/10/10/10
for 51 tickers, 10/10/10/10/10 for 50 (PLTR absent at the first rebalance date
due to insufficient trailing history). Equal-weighted within each quintile.

**Return convention:** Forward one-month simple return, constructed by
shifting the monthly `adj_close` return series back one period so the
return stored at rebalance date _t_ is the return earned from _t_ to _t+1_,
not the return used to form the signal. No look-ahead. Risk-free rate: 0%
(all Sharpe ratios are excess-return Sharpes vs 0%). Annualisation: ×12 for
returns, ×√12 for volatility.

---

## Results

### Annualised statistics (48 monthly periods, rf = 0%)

**Value proxy** — Q5 = cheapest (most fallen), Q1 = most expensive (most risen):

| Portfolio | Ann. Return | Ann. Vol | Sharpe | Max Drawdown |
|---|---|---|---|---|
| Q1 | **27.72%** | 23.32% | **1.19** | −25.2% |
| Q2 | 15.78% | 17.45% | 0.90 | −25.2% |
| Q3 | 15.66% | 16.98% | 0.92 | −14.7% |
| Q4 | 13.43% | 18.49% | 0.73 | −27.4% |
| Q5 | 22.98% | 23.95% | 0.96 | −27.9% |
| **Q5 − Q1** | **−4.75%** | 25.43% | **−0.19** | −46.5% |

**Momentum** — Q5 = winners, Q1 = losers:

| Portfolio | Ann. Return | Ann. Vol | Sharpe | Max Drawdown |
|---|---|---|---|---|
| Q1 | 25.20% | 24.69% | 1.02 | −29.5% |
| Q2 | 13.28% | 17.05% | 0.78 | −21.3% |
| Q3 | 15.36% | 17.15% | 0.90 | −25.4% |
| Q4 | 12.06% | 18.18% | 0.66 | −24.0% |
| Q5 | **29.05%** | 22.61% | **1.28** | −19.2% |
| **Q5 − Q1** | **+3.85%** | 25.23% | **+0.15** | −38.7% |

### Year-by-year Q5 − Q1 spread

| Year | Value Q5−Q1 | Momentum Q5−Q1 | Note |
|---|---|---|---|
| 2021 | **+16.5%** | −9.3% | Partial year (Aug–Dec) |
| 2022 | −5.2% | **+7.9%** | |
| 2023 | −4.6% | −1.5% | |
| 2024 | **−43.4%** | **+36.4%** | |
| 2025 | +1.9% | −5.8% | Partial year (Jan–Jul) |

Value's spread was negative in 4 of 5 periods. Momentum's spread changed sign
in 4 of 5 periods, with no sustained multi-year trend in either direction.

**Cross-factor spread correlation: −0.93** (Pearson, monthly, 48 observations).

Supporting charts: `quintile_monthly_returns.png`, `quintile_cumulative_returns.png`,
`spread_cumulative.png`, `spread_correlation.png` (all in `notebooks/week2/`).

---

## Discussion

### Value's inverted spread

The value proxy's Q5−Q1 spread was −4.75%/year — the opposite sign of a
classical value premium. **Survivorship bias is the leading explanation.**
The universe consists of the top 50 S&P 500 names by _today's_ (August 2025)
market cap, applied retroactively to 2021. Stocks appear in this universe
precisely because they appreciated enough to still be top-50 by 2025.
Stocks like NVDA and PLTR — which had large positive trailing returns in most
months — consistently scored "expensive" (Q1) under the proxy and then
continued rising, because they were already selected for being long-run
winners. The 2024 year-by-year figures illustrate this starkly: value's
Q1 ("most expensive") returned +73.9% that year while Q5 ("cheapest") returned
+30.6%, a −43.4% spread. NVDA gained roughly 170% in 2024 and PLTR roughly
340%; both sat in Q1 throughout most of the year.

A second structural factor amplifies this: because the value proxy is defined
as `−trailing return` and momentum is `+trailing return`, sorting on "cheap"
(value Q5) means sorting on past losers — which is close to shorting the
momentum signal. In a sample dominated by a persistent equity bull run and AI
theme stocks, shorting momentum was consistently costly.

Note that volatility does not explain Q1's outperformance: Q1's annualised
volatility (23.3%) was slightly _lower_ than Q5's (24.0%), so Q1 did not earn
its higher return by bearing more risk on a raw-vol basis.

### Momentum's positive but weak spread

Momentum showed the correct sign: winners (Q5) outperformed losers (Q1) by
+3.85%/year. However, the spread Sharpe (0.15) is low, and the year-by-year
pattern has no sustained direction. 2024 was the outlier year (+36.4% spread),
driven by the AI-theme stocks already in Q5 extending their lead. Outside 2024,
the spread averaged roughly −2% to +8% per year with sign flips in each other
period. This is consistent with a real momentum signal that is noisy in short
samples and strongly time-period-dependent.

### Why the two spread series are negatively correlated (r = −0.93)

The value proxy and momentum signals are built from the same underlying monthly
trailing return, with opposite signs. Ranking by `−trailing_return` (value) is
close to ranking by the inverse of `+trailing_return` (momentum), so the Q5
bucket of one signal contains stocks broadly similar to the Q1 bucket of the
other. Each month, the value long-short portfolio (long fallen stocks, short
risen stocks) and the momentum long-short portfolio (long risen stocks, short
fallen stocks) are therefore approximately mirror portfolios — when one earns
a positive spread, the other tends to earn a negative spread, and vice versa.

This is a **construction-specific result** for this contrarian value proxy. A
true fundamental value factor — built on Price-to-Book or earnings yield — would
not have this algebraic near-identity relationship with momentum, and the
correlation would likely be substantially less negative. The −0.93 figure should
not be generalised to value/momentum correlation in real factor models.

### Factor-neutral vs market-neutral

A long-short quintile portfolio (Q5 − Q1) is **factor-neutral** by construction
with respect to the factor it is sorted on: going long the top quintile and short
the bottom quintile mechanically cancels out average exposure to the sorted
signal. It is _not_ automatically **market-neutral**. Market neutrality requires
that the portfolio's net beta to the broad market (e.g. beta to SPY) is zero,
which must be computed and hedged separately — it does not follow from factor
sorting alone.

In this analysis, both the value and momentum Q5−Q1 portfolios had substantial
absolute returns in most periods (see the year-by-year tables: nearly all
individual quintiles earned positive annual returns in 2023 and 2024), suggesting
non-trivial long-side market beta was present in both spread portfolios. A
market-neutral version would require computing the net beta of Q5−Q1 and hedging
it with SPY or index futures — a step not taken here.

---

## Limitations

**Survivorship bias (most important).** The universe is today's top-50, applied
retroactively to 2021. Every ticker is in the sample because it survived and
appreciated enough to still rank top-50 by August 2025. This is the most likely
primary driver of the inverted value spread, not a secondary consideration.

**Small sample — 48 monthly observations.** Roughly four years of data covers
a limited range of market regimes. The year-by-year tables show spread sign
flips in most periods; drawing strong conclusions from either factor's spread
Sharpe would require substantially more data and independent market cycles.

**No out-of-sample or parameter validation.** Only one set of signal parameters
was tested: 12-month value lookback, 12-1 momentum. No alternative lookback
windows, skip periods, or rebalancing frequencies were evaluated, and no
holdout period was reserved. The reported statistics are entirely in-sample.

**The value signal is a proxy, not a value factor.** Because no fundamental
data was available (no Price-to-Book, no earnings yield), the value signal
measures trailing-return reversal. The finding that "the value proxy showed an
inverted spread" cannot be interpreted as evidence that value investing is
ineffective — it is evidence that this specific contrarian trailing-return
construction underperformed in this survivorship-biased sample. These are
different claims.

**These are historical associations, not causal claims.** The results describe
what happened in this sample over this period. They do not imply that momentum
will continue to outperform, that value is broken, or that the −0.93 correlation
will persist. All findings are sample-specific and should be treated accordingly.

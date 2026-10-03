# Week 3 Memo — Risk Metrics & Portfolio Construction
**Lendo Capital Quant Research Internship**  
Period analysed: Sep 2021 – Aug 2025 (1,003 daily observations)  
Prepared: 2025-09-14

---

## Methodology

**Universe:** 50 stocks (SP500_TOP50, excluding SPY as market benchmark). Daily
simple returns computed from `adj_close` (split and dividend adjusted). The
50-stock aligned matrix begins 2021-09-01, the first trading day after the
earliest rebalance date that yields valid risk-parity weights (60-day lookback
satisfied).

**Risk-free rate:** 2.9615% annualised — the mean of the annualised
13-week Treasury Bill yield (^IRX) over the full sample period. Applied uniformly
to all Sharpe calculations.

**Equal-Weight (EW):** 1/50 per stock at each monthly rebalance (60 rebalance
dates, 2021-09-30 – 2025-08-29). Weights drift between rebalances; reset to
equal at each month-end.

**Risk Parity (RP):** inverse-volatility weights computed from the trailing 60
trading days strictly before each rebalance date. Ticker _i_ weight is
`(1/σ_i) / Σ(1/σ_j)`, where `σ` is the sample standard deviation (ddof=1) of
daily returns. Minimum 20 observations required; no rebalance dates were skipped.

**Mean-Variance Optimization (in-sample):** tangency (max-Sharpe) portfolio via
`scipy.optimize.minimize(SLSQP)` using the full-sample mean vector and covariance
matrix. Per-stock weight cap: 10%. Budget and long-only constraints enforced.
Full-period mu and Sigma are used to score the full period — a pure in-sample
exercise with no predictive validity.

---

## Results

### Performance summary

| Portfolio | Ann. Return | Ann. Vol | Sharpe (rf=2.96%) | Max Drawdown |
|---|---|---|---|---|
| EW (walk-forward) | 19.57% | 18.45% | 0.900 | -23.9% |
| RP (walk-forward) | 16.88% | 15.95% | 0.873 | -19.3% |
| Optimized (in-sample ⚠) | 37.38% | 17.33% | 1.986 | -17.0% |

### Turnover

| Scheme | Avg monthly one-way | Annualised |
|---|---|---|
| EW | 0.0% | 0.0% |
| RP | 4.79% | 57.49% |

### Estimation instability (half-split demonstration)

| Measure | Value |
|---|---|
| One-way weight turnover: first-half vs second-half tangency | 79.85% |
| Interpretation | Nearly disjoint optimal portfolios from two sub-periods |

---

## Discussion

### 1. Estimation instability (79.85% one-way weight shift)

The most striking result of Week 3 is how violently the tangency portfolio
changes between the two halves of the sample. Fitting the optimizer on the
first sub-period (approximately Sep 2021 – Oct 2023) and then on the second
(Oct 2023 – Aug 2025) produces a one-way turnover of 79.85% —
meaning nearly 80 cents of every dollar is moved to a different stock. The
optimizer is maximally sensitive to small changes in mean estimates because
expected-return estimation error is an order of magnitude larger than covariance
estimation error (Merton 1980). A strategy that rebalanced to a new tangency
portfolio every two years would incur extraordinary trading costs while capturing
no stable alpha signal.

### 2. In-sample vs walk-forward gap

The in-sample optimized portfolio reports Sharpe 1.986 vs EW
0.900 and RP 0.873. This gap is arithmetically guaranteed:
the optimizer was given the exact same returns it is being scored on. The
37.38% annualised return and 17.33% volatility reflect the best
possible hindsight allocation, not a replicable trading strategy. In a true
out-of-sample evaluation (e.g. using expanding-window mu/Sigma), the optimized
portfolio's Sharpe would be expected to fall substantially due to estimation error.

### 3. EW vs RP tradeoffs

RP delivered lower realised volatility (15.95% vs 18.45%) and
lower maximum drawdown (-19.3% vs -23.9%), consistent with its
design objective of equalising risk contributions. The cost was a
2.69% lower annualised return and 57.49%
annualised turnover (vs 0% for EW), primarily driven by high-vol stocks (NVDA,
PLTR) cycling in and out of underweight positions as their trailing volatility
fluctuated. The Sharpe advantage for EW is small (0.028 units)
and is unlikely to be statistically significant over a four-year sample.

---

## Limitations

1. **Survivorship bias (dominant).** The universe is the 2025 top-50 S&P 500
   applied retroactively to 2021. Every constituent was a winner by construction.
   EW, RP, and all factor portfolios carry an upward return bias of unknown
   magnitude; correcting this requires point-in-time index data.

2. **In-sample optimizer.** The optimized portfolio uses full-period parameters
   to score itself on the full period. It is not a tradeable strategy and should
   not be compared to EW/RP on equal terms; it is presented solely to illustrate
   the theoretical efficiency frontier and the severity of estimation error.

3. **No transaction costs.** RP’s 57.49% annualised turnover would
   erode returns depending on bid-ask spreads and market impact.

4. **Short sample.** 1,003 trading days (~4 years) spans a single regime:
   a post-pandemic recovery followed by a rate-cycle and AI-driven bull market.
   RP's volatility-targeting advantage may be less pronounced in a regime with
   persistent cross-sectional vol dispersion or correlation spikes.

5. **Static risk-free rate.** A mean ^IRX rate of 2.9615% is used
   uniformly. The actual T-bill rate ranged from near zero in 2021 to over 5%
   in 2023–2024. A time-varying rf would reduce reported Sharpe ratios for the
   2023–2024 period materially.

6. **SPY inside the factor universe.** Task 2 found that SPY — the market
   benchmark used for beta throughout this notebook — was also present in the
   value/momentum factor universe used to build Week 2's quintile portfolios.
   This means the benchmark itself could be sorted into a quintile alongside the
   50 stocks, which is circular and biases beta estimates upward to an unknown
   degree. This is a Week 2 issue, not something corrected in Week 3 — it should
   be resolved before the factor universe is reused in a future week.

7. **Sector constraints skipped.** The plan calls for sector limits in the
   mean-variance optimization (Task 4). This repo has no sector classification
   dataset, so that constraint was not implemented — only the long-only, budget,
   and 10%-max-weight constraints were enforced. The tangency portfolio's
   concentration in a handful of names (Task 4's top-10 holdings) may reflect
   sector concentration that a sector constraint would have limited.

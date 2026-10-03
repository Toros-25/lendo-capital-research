# Week 5 Memo — Transaction Costs & Robustness
**Lendo Capital Quant Research Internship**  
Period analysed: Aug 2021 – Jul 2025 (48 monthly holding periods)  
Universe: Top-50 S&P 500 by market cap as of 2025-08-30, plus SPY (51 tickers total)  
Prepared: 2026-09-28

---

## Headline finding

Both the value proxy and the momentum factor fail every robustness check applied
in Week 5. The momentum factor shows a small positive gross return (+0.59% CAGR)
that is wiped out by trading costs at the 10 bps baseline; the value factor has
a negative gross return before any costs are applied. When sector bets are
removed, both factors' spreads reverse sign entirely, but for different reasons:
momentum's spread is driven by a Technology tilt (most over-represented in
momentum Q5/winners), while value's spread is driven by a Healthcare and Consumer
Defensive tilt (most over-represented in value Q5/cheapest). Neither factor's
spread reflects within-sector stock-picking skill. Neither factor is ready for
live deployment under current assumptions.

---

## Cost impact (Task 2)

Monthly rebalancing generates substantial turnover: the momentum long-short
portfolio turns over approximately 97% of its book per month (annualised ≈ 11.6×),
and the value long-short turns over approximately 88% per month (≈ 10.6×
annualised). At the 10 bps one-way baseline cost assumption:

| Factor | Gross CAGR | Net CAGR at 10 bps | Change |
|---|---|---|---|
| Value proxy L-S (Q5 − Q1) | −7.58% | −8.56% | −0.98 pp |
| Momentum L-S (Q5 − Q1) | +0.59% | −0.53% | −1.12 pp |

The cost drag converts momentum from marginally positive to marginally negative.
The decision-relevant break-even cost (geometric/CAGR-consistent) is **5.26 bps
one-way** for momentum — below the 10 bps baseline and almost certainly below
any realistic all-in trading cost for an institutional fund. For value, no
break-even exists because the gross CAGR is already negative. *(Source: notebook
Section 2.5 and Section 2.7a.)*

> **Note on arithmetic vs geometric:** An arithmetic-mean-based calculation
> inflates the momentum break-even to ~34 bps by ignoring the ~3.1% annual
> variance drag (σ²/2 effect). The geometric break-even of 5.26 bps is the
> decision-relevant figure. *(Section 2.7a.)*

---

## Robustness summary (Task 3 + Task 4)

The table below summarises six robustness dimensions. Each number is pulled
from the notebook — see Section 5.1 for the source cell citation.

| Dimension | Value proxy | Momentum |
|---|---|---|
| Net CAGR at 10 bps | FAIL (−8.56%) | FAIL (−0.53%) |
| CAGR break-even cost | FAIL (undefined — gross already negative) | FAIL (5.26 bps < 10 bps) |
| Sign-consistent across 3 subperiods? | FAIL (positive in 1 of 3) | FAIL (negative in 1 of 3) |
| Survives sector-neutralisation? | FLIP: −4.7% → +4.7% | FLIP: +3.8% → −4.3% |
| Lookback × freq grid: positive cells | 2 of 12 | 4 of 12 |
| Most stable lookback (lowest cross-freq σ) | lb=9m (not tested 12m convention) | lb=9m, consistently negative — not the textbook 12m |

**Subperiod analysis (Task 3):** Value's spread was positive in subperiod A
(Aug 2021 – Dec 2022, the Fed tightening cycle: +6.7%) but negative in B
(Jan 2023 – Apr 2024: −14.5%) and C (May 2024 – Jul 2025: −14.6%). Momentum
flipped in the opposite direction: negative in A (−8.4%) and positive in B/C
(+3.9%, +8.1%). This is consistent with a regime-dependence finding, not stable
signal behaviour across time. *(Section 3.1.)*

**Sector neutralisation (Task 3):** The two factors have different sector tilts,
verified by comparing average Q5 vs Q1 stock counts per rebalance date (notebook
Section 5.1b). For **momentum**, Technology is most over-represented in Q5
(winners side: +0.57 avg stocks/date vs Q1), with Communication Services second
(+0.41) — growth-sector names dominate the momentum winners book. For **value**,
Technology is approximately balanced between Q1 and Q5; instead, Healthcare
(+0.78 avg stocks/date in Q5 vs Q1) and Consumer Defensive (+0.61) are most
over-represented in value Q5 (the cheapest/most-fallen side) — defensive names
tend to underperform risk-on markets and accumulate in the "cheap" bucket. When
the signal is re-ranked within each GICS sector rather than across the full
universe, both factors' spread signs reverse — value's arithmetic L-S spread
goes from −4.7% to +4.7%, momentum's from +3.8% to −4.3%. Each factor's
reversal has a distinct sector explanation; they do not share a single
Technology-driven story. *(Section 3.4; Section 5.1b.)*

**Parameter sensitivity (Task 4):** Across a 4×3 grid of signal lookbacks (3, 6,
9, 12 months) and rebalancing frequencies (weekly, monthly, quarterly), only
6 of 24 CAGR-Sharpe cells are positive (2 for value, 4 for momentum). Momentum's
most-cited positive result (lb=12m, monthly: Sharpe +0.024) disappears at
quarterly rebalancing (−0.266) with the same 12m lookback. The most stable
lookback for momentum (lb=9m by cross-frequency standard deviation) is
sign-consistently *negative* across all three frequencies — meaning the stable
region of parameter space is loss-making. *(Section 4.4, s4_007_stats cell.)*

---

## Deployment-readiness conclusion (Task 5)

**Neither factor clears the bar for live deployment.** The specific barriers,
beyond the scorecard, are:

1. **Market impact and slippage are not modelled.** The 10 bps flat cost is a
   simplification, not a validated execution model. Real costs are
   size-dependent; at institutional scale this number would likely be higher,
   pushing both factors further into loss. *(Section 5.3.)*

2. **Everything is in-sample on a survivorship-biased universe.** The 51-ticker
   universe was fixed as of 2025-08-30 and applied retroactively. All stocks
   were pre-selected for being long-run winners. No holdout period, no
   walk-forward test, and no point-in-time-correct index membership has been
   used. *(Section 5.3; Week 2 CLAUDE.md §Survivorship bias.)*

3. **The value signal is a trailing-return proxy, not a fundamental factor.**
   A proper value strategy would require Price-to-Book or earnings data not
   available in this project. *(Section 5.3; Week 2 memo.)*

4. **The parameter sensitivity is unexplained.** Momentum's sign-change
   across the lookback×frequency grid is consistent with overfitting to a
   specific baseline; a deployment decision would need a principled
   out-of-sample parameter-selection process. *(Section 5.3.)*

---

*All numeric claims in this memo are sourced from executed notebook cells in
`notebooks/week5/transaction_costs_robustness.ipynb`. The traceability
spot-check cell (Section 5, `s5_verify`) verifies 7 specific claims by printing
the source variable value alongside the claimed figure.*

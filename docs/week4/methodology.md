# Week 4 — Event Study Methodology

**Lendo Capital Quant Research Internship**
Date: 2025-09-17

---

## 1. Background: What an Event Study Is and What It Asks

An event study is an empirical method for measuring whether a specific, dated event causes a stock's return to deviate from what would have occurred in a counterfactual, no-event world. The central question is: after controlling for the return that a stock would be expected to earn given its normal relationship with the market, does anything unexplained remain around the event date? That unexplained residual is the *abnormal return*, and if it is systematically non-zero across many events, the event itself is the likely cause.

The method was introduced in Ball and Brown (1968), who studied whether earnings announcements convey information to stock prices. They found that stocks with positive earnings surprises (earnings above the prior consensus) drifted upward in the months leading up to and around the announcement, while stocks with negative surprises drifted downward — evidence that earnings news is informative and prices adjust accordingly. MacKinlay (1997) codified the modern econometric framework: define a normal-return model, estimate it on a clean pre-event window, subtract the predicted return from the realized return around the event, and aggregate the residuals to test statistical significance.

Since Ball and Brown, event studies have been applied to M&A announcements (do target-firm shareholders earn excess returns?), dividend changes, stock splits, index additions, central-bank policy decisions, and macro data releases. The method is versatile because it does not require a structural model of firm value — it only requires a plausible description of what the stock would have returned absent the event.

---

## 2. The Three Normal-Return Models

Every event study requires a choice of *normal-return model* — the counterfactual that defines what return the stock should have earned on event day. Three models are standard in the literature.

### 2.1 Market Model

The market model estimates a stock-specific linear relationship between a stock's return and a market-index return using a pre-event estimation window:

```
R_i,t = α_i + β_i · R_m,t + ε_i,t
```

where R_i,t is the return on stock i at time t, R_m,t is the market return, α_i is the stock's intercept (average excess return), β_i is the stock's market sensitivity (beta), and ε_i,t is the zero-mean residual. The parameters α̂_i and β̂_i are estimated by OLS on the estimation window. The abnormal return on each event-window day is then:

```
AR_i,t = R_i,t − (α̂_i + β̂_i · R_m,t)
```

This model explicitly controls for market-wide moves: if the market rises 2% on event day and the stock has β = 1.5, the model expects a 3% return. Only what remains above that expected 3% is treated as abnormal.

### 2.2 Market-Adjusted Model

The market-adjusted model is a special case that imposes α = 0 and β = 1 for every stock:

```
AR_i,t = R_i,t − R_m,t
```

This requires no estimation window — the model is specified rather than estimated. Its advantage is simplicity. Its disadvantage is that it treats every stock as having the same market sensitivity. PLTR (β historically above 2) and KO (β historically around 0.6) are treated identically, which produces systematically mismeasured abnormal returns for high- and low-beta stocks.

### 2.3 Mean-Adjusted Model

The mean-adjusted model uses a stock's own average return from a pre-event estimation window as the normal return:

```
AR_i,t = R_i,t − R̄_i
```

where R̄_i is the mean daily return over the estimation window. This ignores the market entirely — a stock that underperformed the market on a day of broad selling would show a negative abnormal return even if it fell less than expected given its beta. In event periods that coincide with broad market moves (e.g., an earnings announcement during a market selloff), this model will confound event effects with market effects.

### 2.4 Chosen Model: Market Model with SPY as R_m

This project uses the **market model**, with SPY as the market return proxy. SPY is already in our universe from Week 1 and has clean daily adj_close returns in the parquet cache, so no additional data is needed.

The market model is the preferred choice for individual equity event studies for three reasons:

1. **Stocks differ materially in market sensitivity.** Our universe includes PLTR (high-growth, high-beta) alongside KO and WMT (defensive, low-beta). Imposing β = 1 for all (market-adjusted) or ignoring the market entirely (mean-adjusted) introduces cross-sectional misspecification that the market model avoids.

2. **It is the dominant approach in the published literature** (MacKinlay 1997, Fama et al. 1969, Campbell et al. 1997), making our results directly comparable to benchmark studies and interpretable to any finance professional familiar with the field.

3. **SPY is an ideal proxy** because it tracks the S&P 500, the index to which all 50 of our universe stocks belong. The explanatory power (R²) of a market model using SPY will be high for most of our tickers — typically 0.3–0.8 for large-cap U.S. equities — so the residual variance after removing market returns is small, improving the precision of abnormal-return estimates.

The market-adjusted model is inappropriate here because of the beta heterogeneity problem described above. The mean-adjusted model is inappropriate because it does not control for systematic market moves, which is particularly damaging during volatile periods (2020 COVID crash, 2022 rate-hike cycle) that overlap with our estimation windows.

---

## 3. Event Type: Earnings Announcements (Option A)

### 3.1 Feasibility Check

We checked two candidate event types before making the decision:

- **Option A — Earnings announcements**: stock-specific, ~50 tickers × ~20 quarters over 5 years ≈ 1,000 potential events. Requires an earnings-surprise metric (actual EPS vs. estimate), which is not in the existing OHLCV pipeline.
- **Option B — FOMC meeting dates**: macro event, the same ~8 dates per year apply to every stock simultaneously (~40 events over 5 years, all stocks share the same event dates).

The decision rule: if the earnings data coverage ratio (usable events / theoretical maximum) is ≥ 50%, use Option A; otherwise fall back to Option B.

For Option A, we used `yfinance.Ticker.get_earnings_dates(limit=50)`, which returns a DataFrame indexed by `Earnings Date` with three columns: `EPS Estimate`, `Reported EPS`, and `Surprise(%)`. We defined a usable event as one where all three fields are non-null (computable surprise percentage) and the date falls in the 2020-08-30 to 2025-08-30 window.

Theoretical maximum: 50 tickers × 20 calendar quarters = **1,000 events**

Per-ticker results:

| Ticker | Events in window | Usable | Timing |
|--------|-----------------|--------|--------|
| NVDA | 20 | 20 | AMC |
| AAPL | 20 | 20 | AMC |
| MSFT | 20 | 20 | AMC |
| AMZN | 20 | 20 | mixed |
| META | 20 | 20 | AMC |
| GOOGL | 20 | 20 | AMC |
| TSLA | 20 | 20 | AMC |
| AVGO | 20 | 20 | mixed |
| BRK-B | 20 | 20 | BMO |
| LLY | 20 | 20 | BMO |
| JPM | 20 | 20 | BMO |
| WMT | 20 | 20 | BMO |
| V | 20 | 20 | AMC |
| UNH | 20 | 20 | BMO |
| XOM | 20 | 20 | BMO |
| MA | 20 | 20 | BMO |
| COST | 20 | 20 | mixed |
| NFLX | 20 | 20 | AMC |
| ORCL | 20 | 20 | AMC |
| PG | 20 | 20 | BMO |
| JNJ | 20 | 20 | BMO |
| BAC | 20 | 20 | mixed |
| CRM | 19 | 19 | AMC |
| AMD | 20 | 20 | mixed |
| HD | 20 | 20 | BMO |
| ABBV | 20 | 20 | BMO |
| KO | 20 | 20 | BMO |
| MRK | 20 | 20 | BMO |
| CVX | 20 | 20 | mixed |
| PLTR | 20 | 20 | mixed |
| ACN | 20 | 20 | BMO |
| PEP | 20 | 20 | BMO |
| NOW | 20 | 20 | AMC |
| TMO | 20 | 20 | BMO |
| CSCO | 20 | 20 | AMC |
| ISRG | 20 | 20 | AMC |
| GE | 20 | 20 | BMO |
| LIN | 20 | 20 | mixed |
| IBM | 20 | 20 | AMC |
| AXP | 20 | 20 | mixed |
| TXN | 20 | 20 | AMC |
| GS | 20 | 20 | BMO |
| PM | 20 | 20 | BMO |
| AMGN | 20 | 20 | mixed |
| INTU | 20 | 20 | AMC |
| SPGI | 20 | 20 | BMO |
| RTX | 20 | 20 | BMO |
| BKNG | 20 | 20 | AMC |
| UBER | 20 | 20 | mixed |
| QCOM | 20 | 20 | mixed |

**Aggregate usable events: 999 / 1,000 → 99.9000%**

CRM has 19 events instead of 20 because its Q2 FY2021 earnings (quarter ending July 31, 2020 — CRM fiscal year ends January 31, so Q2 = May–Jul) were released on 2020-08-25, five days before the start of our data window (2020-08-30); the event falls outside the window, and the 19 usable CRM events represent all events that can in principle be studied.

**Decision: the 99.9000% coverage ratio exceeds the 50% threshold. This study uses Option A — earnings announcements.**

### 3.2 Why Not Option B (FOMC)?

FOMC dates would give approximately 40 event-dates over 5 years, each shared by all 50 stocks simultaneously. This creates severe event-clustering: the standard event-study independence assumption (that abnormal returns across events are uncorrelated) is violated when every stock has the same t=0 date. Cross-sectional aggregation on a shared event date does not reduce noise — it compounds it. The earnings approach, where each stock has its own idiosyncratic event date, largely avoids this problem (occasional coincidences aside).

---

## 4. Event-Date Convention

**t = 0 is defined per-event based on the announcement timestamp returned by yfinance.**

yfinance returns an exact timestamp for every earnings event (e.g. `2025-01-30 16:00:00-05:00`). Task 2's `align_to_trading_days()` function uses this timestamp to assign t=0 correctly for each individual event:

- **BMO (announcement hour ≤ 10 ET)**: the market opens after the news is public, so t=0 = the announcement date itself.
- **AMC (announcement hour ≥ 14 ET)**: the market's first opportunity to react is the next morning, so t=0 = the next trading day after the announcement date.

### 4.1 Per-ticker timing classification

The "Timing" column in the coverage table is a per-ticker summary, not a per-event data gap. Every individual event has a fully determined timestamp. A ticker is labelled "mixed" only when its announcement timing varies across quarters — for example, AMZN announced BMO in some quarters and AMC in others. No single event has ambiguous timing; the correct t=0 is computable from each event's own timestamp using the thresholds above.

The timing distribution across the 50-ticker universe:

| Timing | Tickers | Count |
|--------|---------|-------|
| BMO (hour ≤ 10 ET, consistent across quarters) | BRK-B, LLY, JPM, WMT, UNH, XOM, MA, PG, JNJ, HD, ABBV, KO, MRK, ACN, PEP, TMO, GE, GS, PM, SPGI, RTX | 21 |
| AMC (hour ≥ 14 ET, consistent across quarters) | NVDA, AAPL, MSFT, META, GOOGL, TSLA, V, NFLX, ORCL, CRM, NOW, CSCO, ISRG, IBM, TXN, INTU, BKNG | 17 |
| Mixed (timing varies by quarter) | AMZN, AVGO, COST, BAC, AMD, CVX, PLTR, LIN, AXP, AMGN, UBER, QCOM | 12 |

For BMO announcements (21 consistent + the BMO quarters within the 12 mixed tickers), the price reaction begins on the announcement date — t=0 is that date. For AMC announcements, the reaction begins the next trading day — t=0 is shifted forward by one calendar day before mapping to the trading-day index. This per-event adjustment is applied uniformly in Task 2 and eliminates any day-level misclassification of AR_0 vs AR_+1.

---

## 5. Estimation Window

The estimation window spans **trading days [-260, -11] relative to t=0** for each event (each ticker × each earnings announcement date).

- 260 trading days ≈ 1 calendar year of pre-event history
- The window ends 11 trading days before the event date, leaving a gap between estimation and event windows (see Section 7)
- OLS regression of R_i on R_SPY over this window yields α̂_i and β̂_i specific to each event

**Practical note**: for the earliest events in the sample (roughly Q3 2020 – Q2 2021), the estimation window would reach back before the start of the OHLCV cache (2020-08-30), leaving fewer than 200 valid trading-day observations available. Task 2 enforces a hard minimum of 200 valid estimation-window observations; events that do not meet it are rejected outright — there is no shorter-window fallback. This affected 199 events, concentrated in 2020–2021 (see Task 3's Known Limitations note and the findings memo's Discussion point 8 for the downstream effect on panel composition).

---

## 6. Event Window

The event window spans **trading days [-5, +5] relative to t=0** — 11 trading days in total.

The window extends 5 days before the announcement to capture any pre-announcement drift or information leakage, and 5 days after to capture the full price adjustment (including any post-earnings drift in the immediate short run).

---

## 7. Non-Overlap of Estimation and Event Windows

The estimation window ends at **t = −11** (inclusive). The event window begins at **t = −5** (inclusive). These windows do not overlap: the most recent day included in estimation (t = −11) is 6 trading days earlier than the first day of the event window (t = −5). The buffer days t = −10, −9, −8, −7, −6 are excluded from both windows.

**Why this separation matters**: the market model parameters α̂ and β̂ are estimated to represent the stock's *normal* behavior in the absence of the event. If the event window were included in the estimation, event-induced abnormal returns would contaminate the regression and pull the estimated parameters toward the event period, systematically reducing the measured abnormal returns. The gap ensures that the estimated parameters reflect pre-event, business-as-usual return behavior only.

The 6-trading-day buffer (rather than the minimum possible 1-day buffer) also protects against anticipatory leakage: if informed traders begin positioning 3–4 days before the announcement, including those days in the estimation window would pull α̂ toward abnormal pre-event returns. Ending estimation at t = −11 keeps those anticipatory days entirely outside both windows.

---

## 8. Formal Definitions

All formulas use the market model with SPY as R_m.

**Abnormal return (daily, per event):**

```
AR_i,t = R_i,t − (α̂_i + β̂_i · R_SPY,t)
```

**Cumulative abnormal return (over the event window for a single event):**

```
CAR_i = Σ AR_i,t   for t ∈ [−5, +5]
```

**Average abnormal return (cross-sectional average across all N events on event-window day t):**

```
AAR_t = (1/N) · Σ_i AR_i,t
```

**Cumulative average abnormal return (running sum of AAR through event-window day τ):**

```
CAAR(τ) = Σ_{t=−5}^{τ} AAR_t
```

AAR and CAAR are computed in Task 4 (statistical testing); AR and CAR are computed in Task 3 (abnormal return estimation). No AR/CAR calculations are performed in this task.

---

## 9. Summary of Design Choices

| Parameter | Value | Justification |
|-----------|-------|---------------|
| Normal-return model | Market model | Controls for individual β; standard in literature |
| Market proxy | SPY | Already in universe; S&P 500 index tracker |
| Event type | Earnings announcements | 999/1,000 = 99.9000% data coverage |
| Event-date source | yfinance `get_earnings_dates()` | Direct pull; all three EPS fields available |
| t=0 convention | Per-event: BMO → announcement date; AMC → next trading day | Resolved per-event via yfinance timestamp hour (see §4.1) |
| Estimation window | [−260, −11] trading days | ~1 year of pre-event history; ends before event window |
| Event window | [−5, +5] trading days | Captures pre-announcement drift and post-announcement adjustment |
| Buffer between windows | 6 trading days (t = −10 to −5 excluded) | Prevents event-period contamination of α̂, β̂ estimates |

---

## References

- Ball, R. and Brown, P. (1968). "An Empirical Evaluation of Accounting Income Numbers." *Journal of Accounting Research*, 6(2), 159–178.
- MacKinlay, A.C. (1997). "Event Studies in Economics and Finance." *Journal of Economic Literature*, 35(1), 13–39.
- Fama, E.F., Fisher, L., Jensen, M.C., and Roll, R. (1969). "The Adjustment of Stock Prices to New Information." *International Economic Review*, 10(1), 1–21.
- Campbell, J.Y., Lo, A.W., and MacKinlay, A.C. (1997). *The Econometrics of Financial Markets*. Princeton University Press, Chapter 4.

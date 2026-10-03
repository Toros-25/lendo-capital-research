# Week 4 Findings Memo — Earnings Announcement Event Study
**Lendo Capital Quant Research Internship**  
Period analysed: 2020-08-30 – 2025-08-30 (792 events)  
Prepared: 2025-09-17

---

## Methodology

Universe: 50 S&P 500 constituents by market cap as of 2025-08-30, with SPY as market proxy. Of 999 usable earnings events, 7 were excluded for ambiguous announcement timing and 200 for insufficient estimation-window history, leaving a final panel of 792 events. The market model, event window, and t=0 convention are documented in full in [`methodology.md`](methodology.md).

---

## Results

### AAR and t-statistics (N = 792, df = 791)

| Day | AAR (%) | t-stat | p-value | Sig |
|-----|---------|--------|---------|-----|
| −5 | 0.0914 | 1.889 | 0.059 | * |
| −4 | −0.0130 | −0.262 | 0.793 | |
| −3 | 0.0286 | 0.570 | 0.569 | |
| −2 | 0.0119 | 0.247 | 0.805 | |
| −1 | 0.0673 | 1.251 | 0.211 | |
| **0** | **0.4485** | **1.985** | **0.047** | ** |
| **+1** | **0.1776** | **2.382** | **0.017** | ** |
| +2 | 0.0391 | 0.638 | 0.524 | |
| +3 | −0.0270 | −0.460 | 0.645 | |
| +4 | 0.0055 | 0.099 | 0.921 | |
| +5 | −0.0168 | −0.307 | 0.759 | |

Significance codes: `**` p < 0.05 · `*` p < 0.10. Full-window CAAR at day +5: **0.81%**.

CAAR plot with 95% CI: `../notebooks/week4/caar_event_window.png`  
By-surprise-direction CAAR: `../notebooks/week4/caar_by_surprise.png`

---

## Discussion

**1. Pre-event drift.** Days −4 through −1 show no significant abnormal returns (p-values 0.21–0.81). Day −5 clears the 10% threshold (AAR = 0.09%, p = 0.059), but a single marginal result out of five pre-event tests is not compelling on its own — the multiple-testing treatment is in point 6.

**2. Announcement-day and post-event response.** The clearest signal is at day 0 (AAR = 0.45%, p = 0.047) and day +1 (AAR = 0.18%, p = 0.017), consistent with a brief post-earnings-announcement drift. Days +2 through +5 show no further significant moves (p-values 0.52–0.92): the drift, if real, is complete within two trading days.

**3. Statistical significance vs. economic magnitude.** Days 0 and +1 are statistically significant, but the average effects are small — 0.45% and 0.18% per day. These are means across 792 heterogeneous events; statistical significance and economic magnitude are separate properties, and neither figure implies a large or exploitable effect in individual events.

**4. Event clustering.** The t-test assumes cross-sectional independence across all 792 events. The Task 2 clustering report found 105 t0_dates with three or more simultaneous events (one with eight). Events sharing a date are exposed to the same market moves, inducing positive cross-sectional correlation; the t-statistics above are likely overstated in significance. A clustered SE correction by t0_date is the appropriate remedy but was not implemented here.

**5. Confounding events.** This study makes no attempt to control for other company-specific or macro news falling inside the ±5-day window. Guidance revisions, analyst actions, or broad macro events can produce abnormal returns that the framework attributes to the earnings release. This is a structural limitation of the design.

**6. Limits of causal interpretation.** The event study identifies a statistical association between earnings announcements and returns at days 0 and +1 — it does not establish causation (see point 5). Additionally, 11 daily t-tests were run with no multiple-testing correction: at the 5% level, the expected false positives among 11 tests ≈ 0.55, so finding 2 significant days is not far from chance alone. Finally, sampling uncertainty in the estimated β̂ is not propagated into the AR calculations anywhere in this analysis.

**7. Surprise-direction asymmetry.** Positive-surprise events (n = 677) averaged a full-window CAR of +1.44%; negative-surprise events (n = 115) averaged −2.90%. The direction is intuitive. No significance test was run comparing the two groups, and this comparison is descriptive only — the difference should not be characterised as statistically significant.

**8. The 2020–2021 estimation-history gap.** No 2020 events appear in the panel, and 2021 contributes only 52 events (vs. ~198–199 in subsequent full years), because the OHLCV cache starts 2020-08-30 and events before approximately October 2021 cannot satisfy the 200-observation estimation-window requirement. The results describe earnings announcement effects during 2022–2025 (with thin 2021 coverage) and say nothing about whether those effects held in the missing period.

---

## Limitations

**Survivorship bias.** The universe is today's top-50 S&P 500 applied retroactively. Every ticker is present because it appreciated enough to rank highly by 2025; results likely reflect the characteristics of large-cap outperformers during a bull market rather than a general cross-section.

**No out-of-sample testing.** All results are in-sample over the same five-year window. No holdout period was reserved; the statistics describe what happened in this sample and should not be taken as forward-looking expectations.

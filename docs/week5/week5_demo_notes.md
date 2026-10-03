# Week 5 — Demo Notes (Chart Walk-Through)
**Lendo Capital Quant Research Internship**  
Charts folder: `notebooks/week5/`

These are talking-point notes for walking a supervisor through the five charts,
in order. Not a script — adjust to the conversation. Numbers are here so you
don't have to look them up mid-meeting.

---

## Chart 1 — `turnover_over_time.png`
*Context-setter: why transaction costs matter here.*

Start by pointing out that both the value and momentum long-short portfolios
turn over a very large fraction of their book every month. Momentum averages
about 97% monthly turnover (annualised ~11.6×), value about 88% (~10.6×).
That means almost the entire portfolio is being rebuilt each month, which
is expensive even in a large-cap, liquid universe. The key setup line is:
"Before we look at returns, it's worth knowing how much trading is required —
because with this level of turnover, even a few basis points of cost matters
a lot." *(Source: notebook Section 1.)*

---

## Chart 2 — `cumulative_momentum.png`
*The headline momentum result: a thin gross edge disappears net of costs.*

This chart shows the Q1, Q5, and long-short (Q5 − Q1) cumulative wealth for
momentum, with gross returns as solid lines and net-of-10bps as dashed lines.
The most important pair to highlight is the L-S lines: gross ends at a CAGR of
+0.59%, but the net line finishes below 1.0 (CAGR −0.53%). The visual gap
between solid and dashed L-S is entirely explained by the CAGR break-even
being only 5.26 bps — below the 10 bps baseline. A useful way to frame it:
"The gross edge exists, but it's smaller than the cost of trading it."
The arithmetic break-even of ~34 bps looks comfortable, but that's an illusion
from ignoring compounding — the geometric figure is what counts. *(Source:
notebook Section 2.5 and 2.7a.)*

---

## Chart 3 — `cumulative_value.png`
*Value: the problem is the signal, not the costs.*

Same layout as Chart 2, but for value. The key difference is that the gross L-S
line itself drifts downward — CAGR −7.58% before any costs — so the net line
at −8.56% is almost indistinguishable from gross. Costs are a secondary concern
here. The striking visual is that Q1 (most expensive stocks, the ones value is
supposed to short) consistently outperform Q5 (the "cheap" stocks the strategy
is supposed to own). Explain that this is consistent with survivorship bias:
the universe was pre-selected for being long-run winners, so the stocks that
look most expensive at any point in time kept rising because we already know
they ended up in the top-50 by 2025. *(Source: notebook Section 2.5; survivorship
discussion in Section 3.1 and CLAUDE.md.)*

---

## Chart 4 — `heatmap_robustness.png`
*The central robustness result: no reliably positive parameter region.*

This is the most important chart for the robustness discussion. Two 4×3 heat
maps: signal lookback (3, 6, 9, 12 months) on the y-axis, rebalancing frequency
(weekly, monthly, quarterly) on the x-axis, cell colour green for positive
CAGR Sharpe and red for negative. The key headline numbers:
- Only 6 of 24 cells are green across both factors combined (2 for value, 4 for
  momentum).
- The momentum/monthly/12m cell (+0.024) is the baseline from the earlier
  analysis — but move one column right to quarterly and the same 12m lookback
  gives −0.266.
- The single best cell in the whole grid is value/quarterly/12m (+0.082), which
  is not consistent across its own row (other frequencies in that row are negative).

The framing for a supervisor: "If the strategy only worked under one specific
combination of parameters that was chosen in-sample, that's a red flag for
overfitting. We'd want to see a broad green region, not an isolated green cell."
*(Source: notebook Section 4.2.)*

---

## Chart 5 — `sector_composition.png`
*Why sector concentration explains much of the apparent edge.*

Stacked bar charts showing which GICS sectors occupy each quintile for both
factors. The key observation — and a point worth making precisely, because the
two factors tell different stories — is that each factor has its own sector tilt:

- **Momentum:** Technology is most over-represented in Q5 (the winners side),
  averaging about +0.57 more stocks per rebalance date in Q5 than Q1, with
  Communication Services second (+0.41). Growth-sector names dominate the
  momentum winners book.
- **Value:** Technology is approximately balanced between Q1 and Q5. Instead,
  Healthcare (+0.78 avg differential) and Consumer Defensive (+0.61) are most
  over-represented in value Q5 — the "cheap" (most-fallen) side. Defensive
  names underperform in risk-on markets and accumulate in the cheap bucket.

When we rerank within sector rather than across the full universe — removing
these tilts — both factors' spread signs reverse: value goes from −4.7% to
+4.7%, momentum from +3.8% to −4.3% (arithmetic annual returns). That is a full
sign reversal, but with a distinct explanation for each factor. The practical
implication: neither factor's spread is measuring within-sector stock selection;
each is largely a sector-allocation bet, and those bets are different from each
other. A sector-neutral implementation of either factor would need to be
evaluated from scratch. *(Source: notebook Section 3.2, 3.4, and 5.1b.)*

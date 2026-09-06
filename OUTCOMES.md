# The outcome-recording gap: diagnosed, and it is not what it looked like

2026-09-06. Instruction was to report the actual cause with numbers before
proposing a fix. Here it is, and **the lead is a correction**.

## ⚠️ Correction: the outcomes are being recorded

The finding was that 15,207 observations under $20k FDV produced 35 outcomes —
0.23% — and therefore "the overwhelming majority of what we see is never
re-checked before it dies."

**They are re-checked. 99.1% of them.**

| band (FDV at first sight) | n | has **any** outcome | has a **realizable** outcome |
|---|---:|---:|---:|
| under 20k | 19,302 | 19,119 — **99.1%** | 40 — 0.2% |
| 20–40k | 724 | 716 — 98.9% | 18 — 2.5% |
| 40–55k | 892 | 879 — 98.5% | 16 — 1.8% |
| 55–69k approach | 246 | 244 — **99.2%** | 5 — 2.0% |
| 69–100k | 366 | 364 — 99.5% | 8 — 2.2% |
| over 100k | 732 | 727 — 99.3% | 86 — 11.7% |

The "35 outcomes" was counting rows that survived the **realizable** gate. The
rest were recorded, resolved, and found to be worthless:

    69,011 of 69,602 outcome rows (99.2%) are not realizable
       43,335  status = dead
       20,545  status = gone
        4,355  status = rugged
          776  status = alive but below the exit floor

**So this is not missing measurement. It is the measurement.** 99% of what we
observe dies, and we watched it die.

## The consequence: the denominator was already available

The survivorship concern was right, and the fix does not need new collection —
it needs the denominator we already have. Both tables below are the same data:

**Corrected — every token first seen in the band:**

| band | n | wins ≥2x | rate | 95% CI |
|---|---:|---:|---:|---|
| under 20k | 19,302 | 24 | **0.12%** | [0.08%, 0.18%] |
| 20–40k | 724 | 6 | 0.83% | [0.38%, 1.80%] |
| 40–55k | 892 | 6 | 0.67% | [0.31%, 1.46%] |
| **55–69k approach** | 246 | **0** | **0.00%** | [0.00%, 1.54%] |
| 69–100k | 366 | 3 | 0.82% | [0.28%, 2.38%] |
| **over 100k** | 732 | 65 | **8.88%** | [7.03%, 11.16%] |

**As previously reported — realizable-outcome denominator:**

| band | n | wins | rate |
|---|---:|---:|---:|
| under 20k | 40 | 24 | 60.0% |
| over 100k | 86 | 65 | 75.6% |

These reproduce the 62.9% and 80% closely enough to confirm we are measuring
the same thing. **Every rate from that table should be replaced by the one
above wherever it has been quoted.**

What survives the correction: **only the over-$100k band separates.** Its
interval [7.03%, 11.16%] overlaps nothing else. Everything from $20k to $100k
sits between 0.67% and 0.83% with fully overlapping intervals — they are one
population, not a gradient. And that is the same shape as the graduation
result: value is above the threshold, and being above the threshold is a filter,
not a forecast.

## The real defect, separately: capacity is below arrival

There *is* a structural loss, and it is not the one above.

`journal.pending()` makes a pair due only if its first observation falls inside
a **6-hour window** ending at the horizon cutoff. The per-pass slice is **80
rows per horizon** (200 at 1h). What the slice cannot reach inside 6 hours ages
out of the window and **is never scored at that horizon again** — silently, and
permanently.

| horizon | eligible | scored | still in window | **aged out unscored** | lost |
|---:|---:|---:|---:|---:|---:|
| 1h | 22,818 | 21,857 | 0 | 961 | 4.2% |
| 6h | 22,327 | 19,074 | 15 | 3,238 | 14.5% |
| 24h | 20,220 | 15,914 | 103 | **4,203** | **20.8%** |
| 168h | 6,752 | 6,088 | 30 | 634 | 9.4% |

The arithmetic behind it:

    new distinct pairs      2,308 / day   =  96 per hourly pass
    capacity at 80/pass                      80 per hourly pass
    ------------------------------------------------------------
    structural deficit                       16 per pass, 384/day

**Arrival exceeds capacity on every 80-capped horizon, permanently.** The
backlog cannot drain, so the overflow ages out of the window. The comment in
`pending()` says "nothing is dropped — stragglers stay due until the window
closes"; the window closing *is* the drop.

**Proposed fix, not yet applied** — this is a collection change and the numbers
are here for the decision:

1. Raise the per-horizon slice from 80 to **120**. That covers arrival with
   ~25% headroom. Cost: 40 extra Dexscreener calls per horizon per pass = 120
   calls, at a measured 0.116s median = **~14 seconds**. Dexscreener publishes
   300 req/min and answered 12/12 in testing; this does not touch the scarce
   GeckoTerminal budget.
2. Widen `window_h` from 6 to 12 on the 24h and 168h horizons, so a pass missed
   for any reason is recoverable rather than fatal. Costs nothing — it only
   changes which rows are *eligible*, and `actual_elapsed_h` already records the
   honest elapsed time so a late check is not a mislabelled one.

Neither is applied yet.

## The approach band is testable, and the answer is zero

It was reported as too thin to test — 177 observations, 3 outcomes. On the full
denominator it is **246 tokens and 0 wins**, upper bound 1.54%.

That is a real negative result well above `MIN_N=30`, not an absence of data.
It also does not distinguish the band from its neighbours: 40–55k is 0.67%
[0.31, 1.46] and 69–100k is 0.82% [0.28, 2.38], both overlapping zero's
interval. **Nothing in the approach band is different from anything else below
$100k.**

Tracking it anyway is still right, for a reason that has nothing to do with
this table: the hourly schedule cannot see a crossing that takes minutes, so
the band has never been observed at a cadence that could catch the event. That
is what `watchlist.py` changes.

## The pre-graduation volume drop is not real

Median `vol_h1` does fall through the bands — 5,014 → 8,623 → **715** at the
approach band. It is a composition effect, and the decomposition is decisive:

| band | n | rows with vol < $100 | % silent | median vol of the **non-silent** rows |
|---|---:|---:|---:|---:|
| 20–40k | 751 | 48 | 6.4% | 5,648 |
| 40–55k | 912 | 88 | 9.6% | 8,720 |
| **55–69k approach** | 254 | 100 | **39.4%** | 4,294 |
| 69–100k | 377 | 156 | **41.4%** | **15,905** |
| over 100k | 748 | 240 | 32.1% | 5,402 |

**The share of silent rows quadruples above $55k. Among rows with any trading
at all, volume does not drop — it rises, peaking at $15,905 in the 69–100k
band.**

The mechanism is arithmetic. A bonding-curve token's FDV is a function of how
much has been bought, so a curve token at $40k **cannot** be silent — it got
there by trading. Above graduation, FDV is a market price that persists with no
trading at all, so a dead pool keeps its last FDV and sits in the band
contributing a zero. The silent rows have a median liquidity of **$0**.

The linger hypothesis was tested and rejected: median observations-per-band is
**1.0** in every band and only 1.8–3.7% of tokens are seen twice in the same
band, so we are not over-sampling stalled tokens.

## Standing note on the rule that caught this

"Medians and distributions, never bare means" is what surfaced it — but the
median alone was *also* misleading here. The quartiles were the tell: below
$55k the p25 of `vol_h1` is $1,762–$3,091, and above it the p25 is **$1**.
A bimodal population needs its modes separated before any summary statistic
means anything.

# Liquidity trajectory beats the score, out of sample

Run 2026-09-04. Reproduce from `data/` with the join described below.

## The question

`PLUMHORNN` scored 35, was rejected, and returned a realizable 3.64x with
liquidity growing $11.4k to $22.4k. That was the first measured false negative.
The tell was the liquidity trajectory, and the model has no term for it.

## The formulation

Non-leaky, and actionable: use `liq_change_pct` **measured at the 1h check** to
predict the realizable outcome at **6h and 24h**. That information exists one
hour after entry, so a strategy could act on it, and it cannot see its own
label.

A win is `realizable AND mult >= 2`. Denominator is every pair that came due.

## In-sample, 6h, n=2160, base 2.27%

| bucket | n | wins | rate | 95% CI | lift |
|---|---:|---:|---:|---|---:|
| score >= 70 | 777 | 18 | 2.32% | [1.47%, 3.63%] | **1.0x** |
| score < 70 | 1383 | 31 | 2.24% | [1.58%, 3.16%] | 1.0x |
| **liq grew >= +50% by 1h** | 124 | 37 | **29.84%** | [22.49%, 38.40%] | **13.2x** |
| liq grew 0..+50% | 413 | 11 | 2.66% | [1.49%, 4.71%] | 1.2x |
| liq fell -50..0% | 361 | 1 | 0.28% | [0.05%, 1.55%] | 0.1x |
| **liq collapsed < -50%** | 1262 | **0** | **0.00%** | [0.00%, 0.30%] | 0.0x |

## Out of sample — temporal 70/30 split, 6h

Train 1512 rows / 35 wins. **Test 648 rows / 14 wins**, split at 09-02 03:05Z.
Test base rate 2.16%.

| rule | n | wins | rate | 95% CI | lift |
|---|---:|---:|---:|---|---:|
| score >= 70 (incumbent) | 210 | 4 | 1.90% | [0.74%, 4.79%] | **0.9x** |
| **liq grew >= +50% by 1h** | 35 | 11 | **31.43%** | [18.55%, 47.98%] | **14.5x** |
| liq grew >= 0 | 178 | 14 | 7.87% | [4.74%, 12.77%] | 3.6x |
| **liq fell (any)** | 470 | **0** | **0.00%** | [0.00%, 0.81%] | 0.0x |
| score >= 70 AND liq >= 0 | 28 | 4 | 14.29% | [5.70%, 31.49%] | 6.6x |

**11 of the 14 test wins sit in the 35 rows where liquidity grew 50% or more.**

## What this establishes

1. **The score has no edge at 6h.** 0.9x out of sample, 1.0x in sample, and the
   confidence intervals sit on top of the base rate. Measured honestly on the
   full denominator, `score >= 70` is not distinguishable from picking at
   random. This corroborates the bucket table where score<70 hit 3x more often
   than score-100, and it corroborates PLUMHORNN.

2. **Liquidity trajectory at 1h is the strongest signal found so far.** 14.5x
   out of sample, on data the rule never saw, with intervals nowhere near the
   base rate.

3. **Falling liquidity is a near-perfect kill signal.** Zero wins in 470
   out-of-sample rows and zero in 1262 in-sample rows. As a filter for what NOT
   to hold, this is the most reliable thing in the dataset.

## What it does NOT establish

- **This is not an entry signal.** It is measured an hour after entry, so it
  cannot tell you what to buy at t=0. It tells you what to hold, add to, or
  abandon at t=1h. That maps onto the BONDING-CROSS and MOMENTUM-EARLY
  strategies, not onto IMMEDIATE.
- **24h says nothing.** The 24h test window contains zero wins, so every rule
  scores 0.00% and none can be separated. Not evidence against; no evidence.
- The strongest 6h bucket rests on 35 test rows and 11 wins. Directionally
  strong, not precise.
- Survivorship in the sources still applies: `liq_change_pct` comes from
  whatever Dexscreener reported at the 1h check, and that source drops tokens
  whose reserves collapse. Drops now resolve through `resolve.py`, but rows
  collected before 2026-09-03 predate that.

## What to do

Do not re-tune the existing weights around this. The finding is that the
feature set is looking at the wrong moment, not that the coefficients are
wrong. A point-in-time snapshot of a two-minute-old pool cannot carry this
information at all - the trajectory does not exist yet at t=0.

The useful next step is a second observation at a fixed short lag, so
trajectory becomes a first-class feature rather than a by-product of the 1h
outcome check.

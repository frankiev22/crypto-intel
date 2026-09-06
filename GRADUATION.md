# Graduation prediction: promoted to primary, and it fails the same way

2026-09-06. Frank's instruction was that the 227x curve/AMM gap is **a filter,
not an edge**, and that if the AMM subset is too thin to conclude on,
graduation-prediction becomes the primary question. It was, so it was. This is
the result.

`MIN_N = 30` is enforced throughout. Every rate below carries its n, and no
conclusion is drawn from a cell below the minimum.

## The lead: it looks like a 16x edge and it is not one

Out of sample, one rule stands far above everything else this project has ever
produced:

| rule at first sight | n | graduated | rate | 95% CI | lift |
|---|---:|---:|---:|---|---:|
| **fdv >= $20,000** | 234 | 66 | **28.21%** | [22.83%, 34.29%] | **16.1x** |
| fdv >= $10,000 | 352 | 66 | 18.75% | — | 10.7x |
| buys_h1 >= 150 | 404 | 47 | 11.63% | — | 6.6x |
| txns_h1 >= 200 | 539 | 46 | 8.53% | — | 4.9x |

Temporal split at 2026-09-02 11:05Z — train n=9,596 (82 graduations), test
n=4,113 (72 graduations), test base rate **1.75%**. The split is by time, not
random, so this is a genuine out-of-sample test and the interval is wide of the
base rate by a mile.

**It is still not prediction.** Graduated tokens had a median first-sight FDV of
**$34,290** against a graduation threshold of **~$69,000**. They were already
half way there when we first saw them. The rule "FDV above $20,000" is not
forecasting a climb; it is observing that the climb has already happened.

The test that settles it — restrict to tokens first seen genuinely early, at
**FDV < $10,000** (n=3,761, base rate 0.16%):

| rule | n | graduated | rate | lift |
|---|---:|---:|---:|---:|
| buys_h1 >= 30 | 905 | **0** | 0.00% | — |
| buys_h1 >= 50 | 629 | **0** | 0.00% | — |
| vol_h1 >= $1,000 | 1,203 | **0** | 0.00% | — |
| txns_h1 >= 50 | 990 | 1 | 0.10% | 0.6x |

And at FDV < $5,000 (n=3,495), identically zero across `buys_h1` and `vol_h1`.

**Among tokens caught early, nothing tested predicts graduation.** Not one of
these cells beats the base rate, and three of them contain zero graduations
across 600–1,200 tokens each. This is the third time the same shape has appeared
— the liquidity-trajectory gradient, the graduation predictor, and now this —
and each time the feature turned out to be a restatement of progress already
made rather than a forecast of progress to come.

## The base rate, and the denominator it needs

| | n | share |
|---|---:|---:|
| distinct contract addresses observed | 20,888 | |
| first seen on a bonding curve (liq = 0) | 17,861 | 85.5% |
| **mature enough to judge (> 48h old)** | **13,709** | |
| ever seen with a pool | 154 | **1.12%** |
| ever exceeded $69,000 liquidity | 30 | **0.22%** |

"Ever seen with a pool" is a **lower bound**, not a rate. Re-observation is not
guaranteed: a token that graduated between two of our passes and was never
re-sampled counts as a non-graduation here. The true rate sits somewhere above
1.12%, and pump.fun's published 1–2% is consistent with that.

Feature medians at first sight, graduated against not (medians, per the standing
rule — every one of these fields is heavy-tailed):

| feature | graduated | not | ratio |
|---|---:|---:|---:|
| buys_h1 | 153.5 | 8 | 19.2x |
| txns_h1 | 205.5 | 16 | 12.8x |
| fdv | $34,290 | $2,902 | 11.8x |
| vol_h1 | $3,609 | $409 | 8.8x |
| sells_h1 | 18.5 | 7 | 2.6x |

Every one of these separates cleanly, and every one of them collapses to nothing
once FDV is held below $10,000. They are all measuring the same thing: how far
up the curve the token already was when we happened to look.

## Item 1 scoped: can the existing discovery path see graduations?

**Yes, and it already does. It costs nothing extra.** A pump.fun graduation
creates a new pumpswap pool, and GeckoTerminal's `new_pools` returns new *pools*
— so graduations are already arriving in the stream, just undistinguished.
Measured on one live pass, 100 pools:

| dexId | class | pools |
|---|---|---:|
| pump-fun | bonding curve | 72 |
| pumpswap | **AMM** | 10 |
| meteora-damm-v2 | **AMM** | 7 |
| meteora-dbc | bonding curve | 6 |
| raydium-launchlab | bonding curve | 3 |
| raydium-clmm | **AMM** | 1 |
| bags-fm | unknown | 1 |

**18% of the stream is already an AMM pool.** Their median FDV is **$68,284**
against a $69,000 graduation threshold — which is what a graduation event looks
like, arriving at the moment it crosses. *n=18, below MIN_N=30, so that is an
observation and not a conclusion; it needs a larger sample before it is quoted
as a characterisation.*

### The cost, before building anything

| | now | AMM-only |
|---|---:|---:|
| GeckoTerminal discovery calls / pass | 5 | 5 (unchanged) |
| pools returned | ~86–100 | ~86–100 |
| Dexscreener enrichment calls / pass | ~67 distinct | **~12** |
| enrichment wall-clock @ 0.25s pace | ~17s + latency | ~3s + latency |

**Filtering to AMM costs zero additional API calls**, because the venue is in
the discovery payload we already fetch. It removes ~82% of enrichment. The
discovery cost is unchanged and unavoidable — you must pull the pages to see the
venue.

### The finding that reframes it

Of the 16 AMM pools in that pass with a resolvable base token, **0 were tokens
already in our 20,888-address history.** Not one.

That is not a bug, it is coverage. `new_pools` is a ~5-minute window and the
pass runs hourly, so we observe roughly 4–9% of the launch stream. The curve
tokens we sample and the graduations we later see are two thin, near-disjoint
samples of different moments. The probability of catching the same token in both
is close to zero, and that is exactly what we measure.

**So the strategy changes shape.** Trying to predict which of *our* sampled curve
tokens will graduate is the wrong problem twice over: the features don't work
(above), and we almost never see the same token on both sides anyway. Watching
the graduation event directly needs no prediction at all — the event announces
itself, in a payload we already pay for, and it arrives attached to a token that
by definition now has a real two-sided pool.

**Not implemented.** Dropping 82% of intake changes what we collect, and per the
standing rule that is a decision, not an inference. The number is here so Frank
can make it. The trade is: ~7x more AMM tokens per unit of enrichment budget,
against losing the curve population entirely — which currently supplies 0.01%
of >=2x outcomes (2 wins in 14,802) and 85.5% of the cost.

## What is now open

- Whether to filter discovery to AMM. Free, reversible, 82% cheaper, and it
  abandons a population with two wins in fourteen thousand.
- Whether pages should go 5 -> 10 with the freed budget. Doubles the window to
  ~10 minutes and roughly doubles graduation capture; costs 5 GT calls and 11s.
  Page 11 returns 429, so 10 is the ceiling.
- Nothing here goes into a score. No rule in this document filters, gates or
  backfills anything.

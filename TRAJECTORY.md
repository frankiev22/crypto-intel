# Liquidity trajectory: RETRACTED as a signal, kept as a diagnosis

Run 2026-09-04. Supersedes the 2026-09-04 version of this file, which claimed
liquidity trajectory beat the score by 14.5x out of sample.

## The retraction, stated plainly

**That claim was wrong, and the error was leakage.** The rule was scored on
`mult` measured **from entry**, while the feature was measured **at the 1h
check**. A token already up 5x by 1h scores a win at 6h without moving another
cent. The feature was not predicting the outcome; it was a restatement of it.

Decomposing the eleven out-of-sample wins that produced the 14.5x:

| liq change at 1h | multiple AT 1h | multiple at 6h |
|---:|---:|---:|
| +614% | 7.25 | 7.25 |
| +537% | 6.46 | 6.46 |
| +422% | 5.29 | 5.29 |
| +404% | 5.10 | 5.10 |
| +383% | 4.89 | 4.89 |
| +378% | 4.84 | 4.84 |
| +367% | 4.73 | 4.73 |
| +335% | 4.40 | 4.40 |
| +325% | 4.30 | 4.30 |
| +100% | 3.56 | 5.18 |
| +70%  | 2.49 | 2.48 |

**11 of 11 were already >= 2x at the decision point.** In nine of them the 6h
price is identical to the 1h price - nothing happened after the decision at
all. The rule was reading the answer off the label.

## The same leak, in the +20% cliff

The finer bucketing (entry = first observation with liq > $5,000, outcome =
best realizable multiple at any horizon > 1h) reproduces cleanly - n=146
against a reported 144:

| 1h liquidity change | n | hit 2x | hit 5x | mean |
|---|---:|---:|---:|---:|
| negative | 38 | 5.3% | 0.0% | 0.89 |
| 0 to +20% | 58 | 12.1% | 1.7% | 1.37 |
| +20 to 50% | 10 | 80.0% | 10.0% | 4.66 |
| +50 to 100% | 6 | 100% | 66.7% | 5.88 |
| +100% or more | 34 | 97.1% | 61.8% | 5.93 |

Two things are wrong with it, and they compound.

**1. The denominator is survivorship.** 1,162 of 1,308 cases (88.8%) are
excluded for having no realizable later outcome, and exclusion is not random:
the negative bucket keeps 3.5% of its rows, the +100% bucket keeps 51.5%. On
the full population, with "no realizable outcome" scored as the 0x it was:

| 1h liquidity change | n | hit 2x | hit 5x | mean |
|---|---:|---:|---:|---:|
| negative | 1098 | 0.2% | 0.0% | 0.03 |
| 0 to +20% | 94 | 7.4% | 1.1% | 0.85 |
| +20 to 50% | 35 | 22.9% | 2.9% | 1.33 |
| +50 to 100% | 15 | 40.0% | 26.7% | 2.35 |
| +100% or more | 66 | 50.0% | 31.8% | 3.06 |

The gradient survives. **97.1% does not** - it was 50.0%.

**2. What is left is still the leak.** Median multiple already achieved by the
1h decision point, by bucket: negative 0.98, 0-20% 1.04, +20-50% 1.60,
+50-100% 2.68, +100%+ **6.97**. In the top bucket **98.5% were already >= 2x
before the decision was made.**

## What a 1h buyer actually earns

The honest question is the forward return: buy at the 1h price, sell at the
best later horizon, and score "could not exit" as the total loss it is.
Restricted to tokens with >= $8,000 of liquidity at 1h, because you cannot buy
into a pool that is not there:

| 1h liquidity change | n | fwd >= 2x | 95% CI | mean fwd | wiped out |
|---|---:|---:|---|---:|---:|
| negative | 45 | 4.4% | [1.2%, 14.8%] | 0.84 | 31.1% |
| 0 to +20% | 89 | 3.4% | [1.2%, 9.4%] | 0.81 | 34.8% |
| +20 to 50% | 32 | 9.4% | [3.2%, 24.2%] | 0.98 | 68.8% |
| +50 to 100% | 15 | 13.3% | [3.7%, 37.9%] | 0.76 | 60.0% |
| **+100% or more** | 59 | **0.0%** | [0.0%, 6.1%] | **0.56** | 42.4% |

**Every bucket has a mean forward multiple below 1.0.** The strongest
entry-anchored bucket is the worst forward bucket: zero winners in 59, and on
average you keep 56 cents on the dollar. Buying after liquidity has doubled is
buying the top.

## The threshold sweep, which was the specific ask

Rule: "liquidity change at 1h >= T", forward return, actionable cohort.

| T | n | fwd >= 2x | mean fwd |
|---:|---:|---:|---:|
| 0% | 195 | 4.1% | 0.76 |
| +5% | 137 | 5.8% | 0.70 |
| +10% | 125 | 4.8% | 0.68 |
| +15% | 114 | 5.3% | 0.75 |
| +20% | 106 | 4.7% | 0.71 |
| +25% | 96 | 4.2% | 0.58 |
| +30% | 87 | 4.6% | 0.63 |
| +35% | 81 | 3.7% | 0.61 |
| +40% | 77 | 2.6% | 0.60 |
| +50% | 74 | 2.7% | 0.60 |
| +100% | 59 | 0.0% | 0.56 |

**There is no cliff at +20%, and none anywhere between +10% and +40%.** The
sweep is flat inside its own noise and then falls off. Out of sample (70/30
temporal, split 09-02 06:29Z, test n=72) the best band, +20% to +100%, is
n=9 with 1 win. Nothing is established. The incumbent `score >= 70` tests at
2.7%, lift 0.97x - also nothing, which is unchanged and still true.

## Why the entry-anchored numbers looked so good: a 36-token artifact

Nine of the eleven "wins" share a signature. Every one entered at 2-8 minutes
old with reported liquidity of $121k-$359k and a price of $0.00012-$0.00036,
and every one was later quoted at $0.00120-$0.00134 with $1.20M-$1.32M of
"liquidity". 36 tokens in the record match. Inside that group, entry
liquidity / entry price is within 5% of exactly 1e9 for **35 of 35**; outside
it, 47 of 1,339. Their entry rows read:

    GRAM   vol/liq 0.004  txns 37  buys/sells 37/0   age 0.09h
    XDC    vol/liq 0.004  txns 33  buys/sells 33/0   age 0.08h
    AI     vol/liq 0.005  txns 45  buys/sells 45/0   age 0.11h
    GME    vol/liq 0.005  txns 55  buys/sells 55/0   age 0.13h

**Zero sells, every time.** Two free entry-time checks - liquidity/price within
5% of 1e9, and zero sells against >= 10 buys - flag 47 tokens, of which 41 have
later outcomes and **27 record a >= 2x (65.9%), against 2.4% for everything
else.** That 47-token group produces roughly half of every winner on the books.

They are not winners. See EXIT_DEPTH.md: the reported liquidity is the token
side of a one-sided pool valued at its own price, and the real depth is ~$10k.

## What stands, and what to do

1. **Falling liquidity remains a kill signal**, and it is the only claim in the
   original file that survives: 0.3% forward >= 2x across 969 rows, mean 0.04.
   Use it to abandon, never to buy.
2. **No entry or add rule is supported.** Delete the +20% and +50% thresholds
   from consideration rather than tuning between them.
3. **Never score a feature measured at t against an outcome measured from 0.**
   Every future rule is measured forward from its own decision point, and
   "could not exit" is scored 0, not 1.
4. **There is no 30m horizon** - the record holds 1h, 6h, 24h and 168h only, so
   the halved-latency question cannot be asked yet. Adding one is cheap and is
   the single change that would make trajectory testable as a real feature,
   because at 30m the outcome is still ahead of the measurement.

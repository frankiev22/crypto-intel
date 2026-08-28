# What the scoring data actually supports

Run of 2026-08-28. 4,906 observations, 10,698 closed outcomes, 179h covered.
Reproduce with `python track.py`.

## 1. The 161-row table was measuring the wrong thing

Joining observations to outcomes and filtering to `realizable is true` leaves
161 usable rows out of 10,698. On that subset the score looks weak at 2x and
worse than baseline at 3x.

That filter conditions on survival. `realizable` requires `status == "alive"`
and exit liquidity above the $8,000 floor, so the filter discards every dead,
gone and rugged token — 98.5% of the sample, and precisely the outcomes the
score exists to avoid.

**`realizable` must gate the WIN, never the SAMPLE.** A win is realizable and
`mult >= N`. Everything else, including going to zero, is a loss. The
denominator is every pair that came due.

| status | rows | share |
|---|---:|---:|
| dead | 7,893 | 73.8% |
| gone | 1,710 | 16.0% |
| rugged | 835 | 7.8% |
| alive | 260 | 2.4% |

## 2. On the honest denominator the score is far stronger, and 3x is not dead

2x, in-sample, all data:

| horizon | n | base rate | score>=70 | 95% CI | lift |
|---|---:|---:|---:|---|---:|
| 1h | 4,165 | 0.74% | **6.77%** (17/251) | [4.27%, 10.58%] | 9.1x |
| 6h | 3,886 | 0.49% | 3.52% (8/227) | [1.80%, 6.80%] | 7.2x |
| 24h | 2,519 | 0.20% | 1.32% (2/151) | [0.36%, 4.70%] | 6.7x |

3x, same basis:

| horizon | base rate | score>=70 | 95% CI | lift |
|---|---:|---:|---|---:|
| 1h | 0.55% | **3.98%** (10/251) | [2.18%, 7.18%] | 7.2x |
| 6h | 0.34% | 0.88% (2/227) | [0.24%, 3.16%] | 2.6x |
| 24h | 0.12% | 0.00% (0/151) | [0.00%, 2.48%] | n/a |

The earlier conclusion that the score had **no** edge at 3x, and was worse than
baseline, was an artifact of the survivor-only denominator. At 1h the 3x
confidence intervals do not overlap the base rate. At 6h and 24h, 3x rests on
2 and 0 wins and remains unproven either way.

## 3. Almost all the edge is survival, not multiple size

P(outcome is realizable at all), 1h:

| band | n | realizable | of those, >=2x |
|---|---:|---:|---:|
| score>=70 | 251 | **16.73%** | 40.5% (n=42) |
| score 45-69 | 1,324 | 0.53% | 71.4% (n=7) |
| score<45 | 2,590 | 1.58% | 22.0% (n=41) |

Given survival, a high score barely improves the multiple. What it does is make
survival ~11x more likely. That is why conditioning on survival erased the edge.
The 45-69 band surviving *less* than the <45 band is non-monotonic and rests on
7 rows; do not read anything into it yet.

## 4. Out-of-sample: the threshold holds, the weights are not identifiable

Temporal 70/30 split (not random — pairs launched in the same hour share a
regime and a random split leaks). Weights derived on train only, evaluated on
test.

**1h, 2x — test set 1,250 rows containing 3 wins, base 0.24%**

| weights | thr | n | wins | rate | 95% CI | lift |
|---|---:|---:|---:|---:|---|---:|
| fallback (live) | 70 | 60 | 2 | 3.33% | [0.92%, 11.36%] | 13.9x |
| v1 (in DB, inactive) | 70 | 60 | 2 | 3.33% | [0.92%, 11.36%] | 13.9x |
| derived from train | 70 | 84 | 3 | 3.57% | [1.22%, 9.98%] | 14.9x |

**6h, 2x — test set 1,166 rows containing 4 wins, base 0.34%**

| weights | thr | n | wins | rate | 95% CI | lift |
|---|---:|---:|---:|---:|---|---:|
| fallback (live) | 70 | 52 | 1 | 1.92% | [0.34%, 10.12%] | 5.6x |
| v1 (in DB, inactive) | 70 | 52 | 1 | 1.92% | [0.34%, 10.12%] | 5.6x |
| derived from train | 70 | 75 | 4 | 5.33% | [2.09%, 12.93%] | 15.5x |

What this does and does not establish:

- **Established:** the >=70 threshold beats base rate out of sample at both
  horizons, on data the weights never saw. That is a real filter.
- **Not established:** which weight set is best. The test sets hold 3 and 4
  wins. Every apparent difference between weight sets is a one-to-three-win
  difference. Nothing here justifies changing the live weights.
- Sweeping the threshold 60 / 70 / 80 barely changes what is selected (60 vs 59
  rows at 1h). The score is close to a step function, not a 0-100 scale.

## 5. Three defects found while doing this

**a. The derived weights were never live.** `crypto_score_weights` holds
versions 1 and 2, both `active = false`, both with `alert_threshold = -1`.
`weights.active()` has been returning FALLBACK (version 0, the original
hand-set values) for every scored row. Every number above was produced by the
hand-set weights.

**b. The liquidity lift is partly circular.** `journal.MIN_EXIT_LIQ_USD` is
derived from `scanner.CFG["min_liquidity_usd"]` — the same $8,000. So the entry
gate "liquidity >= 8k" is being scored against a label that itself requires
"exit liquidity >= 8k". Measured lift by exit floor at 1h:

| exit floor | wins | liquidity gate lift |
|---|---:|---:|
| $8,000 | 31 | 182x |
| $1,000 | 32 | 122x |
| $500 | 35 | 97x |
| none | 138 | **12x** |

Liquidity is genuinely the strongest feature, but 182x is inflated roughly
15-fold by the shared threshold. Weights derived from it put 88-93% of the
score on one gate. **Do not activate them.**

**c. `vol_h1` and `vol_h24` are the same number in 100% of 4,906 rows.**
Median age at first sighting is 2.2 minutes, so a pool's 1h and 24h volume are
identical. The `vol1h` and `volliq` gates are computed from one measurement,
not two. Combined with `age` (98.2% pass, no variance) and `buysell`
(inverted — lift 0.45 at 1h, 0.22 at 6h), the 100-point score is really a
three-signal filter — liquidity, transaction count, volume — with volume
double-counted.

## 6. What to do

1. Keep the live fallback weights. Nothing out of sample beats them.
2. Keep the >=70 threshold. It is the part that validated.
3. Grade on **2x at 1h and 6h**. Report 3x alongside; do not drop it.
4. Do not activate weights v1 or v2.
5. Break the liquidity/exit-floor coupling before deriving weights again.
6. Collect. Every conclusion here is bounded by 3-4 out-of-sample wins, and the
   only fix is more closed outcomes — which is what the hourly runner is for.

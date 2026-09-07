# Pre-commitment: the Helius re-test

**Written and committed BEFORE any result was computed.** Frank wants this to
work. So do I. That is precisely the condition under which people find edges
that are not there, so the thresholds are fixed here first and the analysis is
scored against them afterwards, whatever it says.

## The error being corrected

I applied the contamination argument in one direction only: I used bad ground
truth to invalidate the **wins**, then kept the **failures** as established
fact. If `exit_depth_usd` from Dexscreener was unreliable, a finding that died
on it is **untested**, not **disproven**. Frank caught this. It is a real
reasoning error, not a nuance.

But "retest everything" is the opposite error. A methodological failure stays
dead no matter how good the new data is.

## Triage: which failures are retestable

| finding | died of | pile | why |
|---|---|---|---|
| liquidity-trajectory gradient | **leakage** — feature read at a nominal 1h that landed at a median ~2.0h, so it reported the past | **DEAD. Methodological.** | Better reserves cannot fix a feature measured after the outcome began. No new source changes when a clock was read. **Do not resurrect.** |
| graduation predictor | **leakage**, same shape | **DEAD. Methodological.** | Same reason. |
| age-keyed magnitude gate | `age_hours` is PAIR age, not token age | **DEAD. Definitional.** | The field means something other than what the rule assumed. Not a data-quality issue. |
| score-100 band being worst / low-score inversion | moved when template pools were removed | **RETESTABLE.** | The effect is a function of which rows are fake, and fakeness was decided by the suspect field. |
| cluster density vs 1M crossings | ran against proxy labels; the milestone tracker was later found never to have fired live | **NEVER TESTED.** | Not a failure at all. There were no real labels to test against. |
| the 165 historical wins | no `exit_pair`, pools delisted | **GONE.** Unrecoverable either way. |

## Hypotheses, with thresholds fixed now

Ground truth for all of these is **quote-side reserves read from chain via
Helius**, not Dexscreener's `liquidity.usd` or its reserve split.

**H1 — the referee test. Does D1 survive when the ground truth is not supplied
by the source being audited?**
Recompute every label from on-chain reserves; re-score D1 unchanged.
- **PASSES** if precision point estimate ≥ 90% AND the 95% lower bound ≥ 75%.
- **FAILS** if the lower bound < 70%.
- Between 70 and 75 is **inconclusive** and reported as such.
- Minimum n to report at all: **20 flagged rows with on-chain labels.**

**H2 — how wrong is Dexscreener, and is it wrong selectively?**
Compare on-chain depth to Dexscreener depth per pool.
- Report the median ratio and IQR for flagged and non-flagged separately.
- **A finding** if the two populations' median ratios differ by more than 2x.
- If Dexscreener agrees with chain everywhere, then the data was fine, the
  original failures stand, and **this whole exercise returns "no change" —
  which is a legitimate and likely outcome.**

**H3 — does the paper log's verdict move?**
Reprice the closed positions from chain.
- **MATERIAL** if the median multiple moves by ≥ 0.10x absolute, or if the
  hit rate point estimate moves by ≥ 5pp.
- Anything smaller is noise at n=7 and will be reported as unchanged.

**H4 — the score bands, on clean labels.**
Realizable-2x rate by score band, template pools excluded using on-chain
evidence.
- **A finding** only if a band's rate differs from the pooled base rate with
  **non-overlapping 95% intervals** and **n ≥ 30 in that band.**
- Anything else is reported as "no separation at available n".

## Rules binding this analysis

1. **No hypothesis is added after seeing results.** Anything discovered along
   the way is logged as a new question for a future test, not reported as a
   finding from this one.
2. **Every number carries n and an interval.** Medians and distributions, never
   bare means.
3. **A result that flips direction is reported as loudly as one that survives.**
4. **"Still no entry signal" is a complete and acceptable answer.** A clean
   second no is worth more than a dirty maybe.
5. If the on-chain read cannot be validated against a known-good pool first,
   **the whole exercise is abandoned and reported as not attempted** — an
   unvalidated new source would just be a second way to be wrong.

---

# RESULTS, scored against the thresholds above

Written after the analysis. Nothing above was edited.

## H1 — the referee test: **CANNOT BE TESTED**

Threshold required **≥20 flagged rows with on-chain labels**. Got **1**.

The reason is itself the finding: **33 of D1's 38 flags sit on fluxbeam**, and the
layout-scanning reserve reader cannot reliably resolve fluxbeam vaults. 14 of 34
attempted reads were rejected by the reliability check. **D1's depth-ratio ground
truth therefore remains unverified by an independent source.**

The supply-concentration test run separately (12/14 flagged vs 3/14 controls
holding ≥90% of supply in one account, +64pp) still stands and independently
confirms the *"supply IS the pool"* half of the conjunction. The *depth ratio*
half does not.

## H2 — how wrong is Dexscreener: **NO SEPARATION DEMONSTRABLE**

n=20 readable (19 clean, 1 flagged). chain/Dexscreener ratio p25 **1.001**,
median **1.299**, p75 **1.586**; 9/19 within ±25%.

Threshold was a >2x difference between flagged and clean populations. With
flagged n=1 that comparison cannot be made. Separately, the ~30% median
over-read on clean pools means **the reader is not precise enough to adjudicate
Dexscreener** even where it works. It agrees closely on Meteora (0.99–1.08) and
loosely elsewhere.

## H3 — does the paper log's verdict move: **NOT TESTABLE**

4 of 10 closes were repriceable, and only at *current* depth. Repricing the
closes needs reserves **as of the close**, which requires archival RPC we do not
have. The median does not move because it cannot be recomputed.

Current depths corroborate the earlier finding without measuring it: `$1` $349,
WWR $21, MANGO $47, MARSCOIN $3 — against entry depths of $12k–$219k.

## H4 — score bands on clean labels: **NOT ATTEMPTED**

Depended on clean labels from H1/H2. They did not materialise.

## New question, NOT a pre-committed hypothesis — logged, not claimed

**D1 may be substantially a venue proxy.**

| rule | flagged | precision | recall |
|---|---:|---|---|
| D1 | 38 | 97.37% [86.5, 99.5] | 49.3% |
| **`dex_id == fluxbeam` alone** | 35 | **100.00% [90.1, 100.0]** | 46.7% |
| D1 excluding fluxbeam | 5 | 80.00% **[37.6, 96.4]** | 5.3% |

A single venue check matches or beats D1. Stripped of fluxbeam rows D1 flags 5
things with an interval spanning 37.6–96.4%. This does not make D1 useless — a
venue-specific detector still detects — but it is **not the general mechanism it
was described as**, and it will fail the moment the operator changes venue.

This needs its own pre-committed test. It is recorded here as a question.

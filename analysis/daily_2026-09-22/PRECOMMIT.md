# Daily research run 2026-09-22: pre-committed methods

Written before either measurement below was run. Nothing here is changed after
the data is read; anything decided later is labelled as such in the report.

## Section 1: are recorded multiples accurate?

**Sample.** Every outcome row with `checked_ts` in the 24h before the run
(union of the desktop working tree and `origin/master`) and a recorded `mult`
of 2.0 or more: 321 rows on 195 distinct contracts, 17 of the rows
gate-passing (`realizable`). Plus a seeded random 60 contracts (seed 20260922)
drawn from the other contracts in the same window that carry a `mult`.

**One Dexscreener call per contract**, `latest/dex/tokens/{address}` through
`sources.dexscreener_token`, one address per call, never batched, 0.3s between
calls.

**Live multiple** = live `priceNative` of the row's recorded `exit_pair`
(falling back to `pair`) divided by the row's `base_price_native`. Native
prices on both ends, so SOL's own move does not enter. If the recorded pair is
not in the response, the row is `pair_not_found`, not a disagreement.

**Material disagreement**: live / recorded outside [0.5, 2.0].
Direction: recorded more than 2x live is OVERSTATED; recorded under half of
live is UNDERSTATED. Worst divergence = the largest |log(live / recorded)|.

**Measurement error vs. movement.** Time passes between the check and the
re-check, so disagreement alone can be real price movement. A row is flagged
as a probable MEASUREMENT error only if, at the re-check moment, the recorded
pair's `priceNative` differs by more than 2x from the deepest pool of the same
token with the same quote asset (deepest = largest quote-side liquidity). That
is the STRATTON/GPRO signature: a price taken from a pool that does not agree
with where the token actually trades.

## Section 3: does score predict SURVIVAL independent of peak?

Open question 1 in `QUESTIONS.md`.

**Unit**: one contract, its FIRST observation row that carries a `score`,
joined to the 24h outcome on the same `pair`. Observations 2026-09-07 onward
(24h outcomes need the full horizon to have elapsed).

**Arms**: `score >= 70` (passed the launch filter, `PASS_SCORE`) vs `score < 70`.

**Survival label, liquidity-gated.** SURVIVED: 24h `status == "alive"` AND
`exit_depth_usd >= 1000` (quote side). DIED: status `dead` or `rugged`, or
`alive` with `exit_depth_usd < 1000`. UNKNOWN, excluded: status `gone` (the
pair lookup returned nothing, which is the primary-source miss rate, not
death), or `alive` with no depth measured. The unknown share is reported per
arm so a biased exclusion is visible.

**Peak control.** Early peak = max recorded `mult` across the SAME pair's 1h
and 6h outcomes, never the 24h one (that would leak the label). Strata:
peak < 1.0, 1.0 to < 2.0, >= 2.0, and "no early check" (reported, not pooled).

**Decision rule.**
- CONFIRMED: Mantel-Haenszel pooled odds ratio (high vs low score) above 1
  with the 95% CI lower bound above 1, AND high-score survival exceeds
  low-score survival in every stratum where both arms have >= 30 distinct
  contracts, AND at least two such strata exist.
- NOT SUPPORTED: the pooled CI includes 1 or lies below it.
- INSUFFICIENT: fewer than two strata with >= 30 contracts per arm.

Crude (unstratified) rates are reported beside it. `grade` (from 2026-09-17)
is run as a sensitivity check only; it does not decide.

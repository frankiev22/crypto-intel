# Question queue

## Answered
- **Does liquidity trajectory beat point-in-time score?** ~~YES, 14.5x lift~~
  **NO. RETRACTED 2026-09-04 - see "Resolved" below.** This entry is kept
  struck through rather than removed because it was quoted to Frank as a real
  result before the leakage was found. The feature was measured at 1h and the
  outcome from entry, so 11 of 11 out-of-sample wins were already >=2x before
  the decision point. Do not trade this.
- **What does `total_reserve_in_usd` measure?** It aggregates across pools
  (FLORK pools summed $0.0763 vs reported $0.0605). The GRASS "contradiction"
  is volume-as-trailing-24h-sum vs reserve-as-snapshot. Both true at once.

## Open
- ~~Does score predict SURVIVAL independent of peak multiple?~~ **TESTED
  2026-09-22: NOT SUPPORTED** under the rule pre-committed in
  `analysis/daily_2026-09-22/PRECOMMIT.md`. 15,034 contracts, 4,392 with a
  known 24h label (survived = alive with >= $1,000 quote-side depth).
  Crude: score >= 70 survives 12.6% [9.8, 15.9] (57/454) vs 1.9% [1.5, 2.3]
  (73/3,938). Pooled Mantel-Haenszel OR 2.75 [1.94, 3.89], BUT the direction
  **reverses** where the early peak was already >= 2x: high score 4.9%
  [2.1, 11.0] (5/102) vs low score 26.4% [19.9, 34.0] (39/148). The rule
  required the direction in every eligible stratum, so it fails. Two
  weaknesses in the test itself: 126 of 130 survivors were AMM pools, so the
  label mostly measures venue, which the score partly measures too; and the
  unknown share is biased (48.9% high arm vs 72.2% low arm, mostly `gone` =
  the pair lookup returned nothing). **Sharpened into the next two.**
- **(sharpened)** Among contracts already on an AMM at first sight, does score
  predict 24h survival? Removes the venue confound. Pre-commit before running.
- **(sharpened)** Why does high score go with LOWER survival among early 2x
  runners? Hypothesis to test, not a finding: the score reads the pump itself.
- **(new 2026-09-22)** Do names cluster narratives that tickers hide?
  `token_name` is persisted from 2026-09-22; test once 7 days exist. The
  fake-fund wave (108 contracts, 24 tickers) was invisible to ticker clustering.
- **(new 2026-09-22)** Drained pools that keep printing volume: EMBER's pool
  showed $163M of 24h volume on $0 of liquidity, TSLA $60.6M on $0.06. How
  often does this happen, and can the scanner or milestone ledger admit one?
- Median time-to-peak for winners (needs peak tracking, not built).
- Does cluster membership predict a 1M crossing, against real milestone labels?
- Do linked socials outperform?
- What liquidity floor AT ENTRY predicts a realizable exit?
- Does a second observation at a fixed short lag make trajectory usable as an
  ENTRY feature rather than a 1h-after signal?

## Resolved 2026-09-04 (second pass)

- **Does liquidity trajectory predict anything?** No. Retracted - see
  TRAJECTORY.md. The feature was measured at 1h, the outcome from entry, and
  11 of 11 out-of-sample wins were already >= 2x before the decision point.
  Forward from the 1h price, every bucket has a mean multiple below 1.0.
- **Where is the +20% cliff?** Nowhere. The sweep from +10% to +40% is flat
  inside its own noise, and the >= +100% bucket is the worst forward bucket
  (0 wins in 59).
- **Is there a 30m horizon?** No. The record holds 1h, 6h, 24h, 168h only.
- **How much survivorship is in the bucket tables?** 88.8% - 1,162 of 1,308
  cases are dropped for lacking a realizable later outcome, and the drop rate
  runs from 96.5% in the negative bucket to 48.5% in the top bucket.
- **Should ticker reuse be penalised?** No, and not rewarded either. Every
  variant-count bucket's confidence interval overlaps every other, and the
  ordering flips with the denominator. Recorded as `ticker_variants`, scored by
  nothing. See tickers.py.
- **What does Dexscreener's `liquidity.usd` measure?** Both sides of the pool,
  base valued at its own price. A healthy pool reads ~2.0x its true exit depth;
  one-sided launch pools read 15x-125x, and one row in the 2026-09-04 21:45Z
  pass read **58,106x** ($407,020,680 reported against $7,005 of quote side).
  See EXIT_DEPTH.md.

## Open

- **What does GeckoTerminal's `total_reserve_in_usd` measure?** Partially
  answered: not FDV (it read $40,913 where Dexscreener read $1,285,629) but
  still ~4x the quote side. Until it is pinned down, the GeckoTerminal path
  reports `exit_depth_usd: None` and the exit floor falls back to the
  both-sides figure. A GeckoTerminal-only row can still clear the floor on a
  one-sided pool. **This is the largest remaining hole in realizability.**
- **Does impersonation predict failure?** Directionally yes, not established:
  flagged n=41 at 2.4% >= 2x [0.4%, 12.6%] against clean n=1,152 at 4.8%
  [3.7%, 6.2%]. Intervals overlap. Flag recorded, no penalty weight set.
- **What is the 47-token one-sided cluster?** Two free entry checks flag it and
  it produces ~half of every recorded winner. Who mints it, and does the
  template change when the checks start rejecting it?
- **Can any entry rule be supported at all?** Nothing in the record currently
  separates. That is the honest state.

## Resolved 2026-09-05

- **Does horizon drift invalidate the gradient?** No, but it was real and worth
  finding. Drift is one-sided lag confined to the 1h horizon (median 2.00x its
  label, 51.4% past 2h). Restricted to genuine 1.0-1.5h checks the gradient
  survives; removing the one-sided template collapses it. See TRAJECTORY.md.
- **Is the score saturated at 100?** Not globally - only 4.06% of 19,745
  observations sit at 100. But **72.2% of everything scoring >= 70 is exactly
  100**, and the whole scale has just **12 distinct values**, two of which
  (30 and 45) are 59% of all mass. The pass band is effectively binary.
- **Is the score inverted?** No, and the evidence that suggested it was
  contaminated. Raw, rejected tokens beat passed ones 8.5% to 2.6%. Excluding
  the one-sided template the two are indistinguishable: passed 2.6%
  [1.7%, 3.9%], rejected 1.7% [0.8%, 3.8%]. The 45-69 band falls from 5.3% to
  0.4% once the artifact is removed. **Not inverted. Not informative either.**
  Score 100 remains the worst band at 1.5% [0.8%, 2.7%], and that survives the
  artifact filter because none of its 687 rows are template pools.

## Open

- **Is the 1h horizon worth keeping?** It cannot be measured at the current
  ~3.5h pass cadence. Either the runner fires far more often - a cost decision,
  billed minutes, Frank's call - or the shortest trustworthy horizon is 6h and
  the 1h label should be retired rather than repaired.
- **Rescaling the score:** re-deriving weights against a target where 72% of
  passes share one value is wasted work, but the fix is granularity, not
  uncapping - there is no evidence the ceiling is clipping a real signal, since
  the ceiling band performs worst.

---

## Logged, not built: the pump.fun launch bot

2026-09-07. Frank has an idea banked for a bot that mints coins on pump.fun the
moment something goes viral. **It is not being built and no part of it is being
scaffolded.** This entry exists so that if he revives it, nobody re-derives what
already exists.

Two components in this repo would be the ones it needed:

- **the fraud detector** (`detector.py`, `plausibility.py`) — D1 and D2, the
  conjunctions and their measured precision. Whatever the bot is, knowing which
  pools are fake is the same problem.
- **the narrative-cluster work** (`tickers.py`, `news.py`) — ticker variant
  counts, impersonation detection, and the per-outlet news feed that would be
  the "something went viral" trigger.

Both were built for the opposite purpose: to identify what is fake and what is
being impersonated. That they would also be the inputs to a launcher is worth
recording plainly rather than discovering later.

Nothing here is a recommendation to build it. Standing instruction: refer it
back rather than starting it.

## D1's first false positive, 2026-09-07 — and why it is NOT being fixed

`Anthropic`, orca, `liq $3,120.67 / fdv $1,658.00 = 1.8822`, 21 buys, 0 sells,
**depth/liq 0.52060** — a textbook healthy two-sided pool. It cleared D1 because
`liq/fdv >= 0.95` is a floor, and 1.88 clears a floor.

The template population clusters at `liq/fdv` **median 1.0020** (p25 1.0003,
p75 1.0018) — *at* one, not above it. A ratio of 1.88 means the cash side
outweighs the token side, which is the opposite of "the supply is the pool".

**The obvious refinement is a band rather than a floor**, e.g.
`0.95 <= liq/fdv <= 1.10`. It is deliberately NOT applied. Tuning a rule on the
first false positive it produces is in-sample fitting — the exact error that
killed four earlier findings — and D1's whole value is that it was derived
before the data existed. If this shape recurs, it earns the change with
evidence. Until then the honest number is precision 95.83% [79.8, 99.3], n=24.

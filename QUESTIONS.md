# Question queue

## Answered
- **Does liquidity trajectory beat point-in-time score?** YES. Out of sample,
  6h: liq grew >=+50% by 1h = 31.43% realizable-2x rate (14.5x lift) vs
  score>=70 at 0.9x. Falling liquidity: 0 wins in 470 test rows. TRAJECTORY.md.
- **What does `total_reserve_in_usd` measure?** It aggregates across pools
  (FLORK pools summed $0.0763 vs reported $0.0605). The GRASS "contradiction"
  is volume-as-trailing-24h-sum vs reserve-as-snapshot. Both true at once.

## Open
- Does score predict SURVIVAL independent of peak multiple?
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

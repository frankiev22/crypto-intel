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

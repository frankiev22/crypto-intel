# Reported liquidity is not exit liquidity

Measured 2026-09-04. This is the root cause under FLORK, under the liquidity
trajectory retraction, and under the standing question about what
`total_reserve_in_usd` measures.

## The finding

Dexscreener's `liquidity.usd` counts **both sides of the pool**, and the base
side is the token valued at its own price. Pulled live:

    worthless   liquidity.usd  $1,285,629
                base   981,744,468 tokens x $0.001299  = $1,275,286
                quote  98.7348 SOL                     =    ~$10,236

    TIKZZZ      liquidity.usd  $1,304,531
                base   981,741,611 tokens
                quote  98.7195 SOL

Two unrelated tokens, both on fluxbeam, both holding 981.7M of their own token
and 98.7 SOL, both quoting `priceNative` 0.00001253. It is a template.

**You can only be paid in the quote asset.** Real exit depth is ~$10,236, not
$1,285,629 - the reported figure overstates it by **125x**.

## The measurement

Fourteen tokens the record currently calls realizable winners, checked live,
one API call each:

| token | recorded mult | liquidity on record | true exit depth | ratio |
|---|---:|---:|---:|---:|
| SUNCOIN | 5.11x | $1,260,745 | $10,030 | 125.7x |
| CACA | 4.26x | $1,258,160 | $10,022 | 125.5x |
| GME | 3.82x | $1,294,731 | $10,305 | 125.6x |
| worthless | 4.73x | $1,285,629 | $10,236 | 125.6x |
| RST | 2.95x | $1,040,706 | $106 | 20.2x |
| WOFI | 2.03x | $316,532 | $130 | 15.0x |
| MACHINE | 13.13x | $93,446 | $0 | - |
| CTO | 2.15x | $430,869 | $0 | - |
| **PLUMHORNN** | 3.64x | $22,368 | $10,675 | **2.1x** |
| **AURA** | 3.56x | $59,863 | $32,592 | **2.1x** |
| TIKZZZ, AI, GRASS, XDC | - | - | dropped from the index | - |

**A healthy balanced pool reads ~2.0x**, because the figure counts both sides
and the sides are worth about the same. That is the diagnostic:

    reported liquidity / exit depth  ~2      honest pool
                                     >>2     one-sided; the base token is
                                             most of the "liquidity"

Four of the four ~125x rows land within $283 of each other on depth. The same
pool, minted repeatedly.

Note which two tokens are honest: PLUMHORNN, the false negative that started
this investigation, and AURA. The scanner rejected PLUMHORNN for having "only
1 txn in the last hour" while admitting a fleet of pools nobody can sell into.

## What changed in the code

- `resolve.exit_depth_usd(pair)` computes the quote side as
  `liquidity.quote * (priceUsd / priceNative)`, which needs no hardcoded
  knowledge of what the quote asset is, and falls back to
  `liquidity.usd - base * priceUsd`.
- `resolve()` returns `exit_depth_usd`, adds a `one_sided_pool` reason when
  depth is under 10% of reported liquidity, and judges `exitable` on depth.
- `journal.realizable()` takes `exit_depth` and applies the $8,000 exit floor
  to it whenever it is known, falling back to `liq` when it is not.
- `journal.record_outcome()` writes `exit_depth_usd` on every row from now on.
- `pricecheck.validate()` applies the dust floor to depth, and quarantines
  `quarantined_liquidity_divergent` when the two sources disagree about
  liquidity by more than 10x even where they agree on price. That is the 景甜
  gap: 29.53x recorded, the multiple correct, Dexscreener showing $0 liquidity
  against GeckoTerminal's $36,202.

## `total_reserve_in_usd`: partially answered, not closed

For `worthless`, at the same moment: Dexscreener $1,285,629, GeckoTerminal
$40,913, true quote side $10,236. So GeckoTerminal is **not** reporting FDV -
it is 31x below Dexscreener's figure - but it is still ~4x the quote side. It
is a reserve total that counts both sides, across pools. It should not be used
as exit depth either. `_geckoterminal()` therefore returns
`exit_depth_usd: None` rather than guessing, and the exit floor falls back to
the both-sides figure on that path. **That fallback is a known open gap**, and
it is the reason a GeckoTerminal-only row can still clear the floor on a
one-sided pool.

## What this does not fix

Historical rows have no `exit_depth_usd`; the field starts empty and fills
forward. Nothing is rewritten and nothing is deleted. Every outcome recorded
before 2026-09-04 was judged against both-sides liquidity and should be read
that way.

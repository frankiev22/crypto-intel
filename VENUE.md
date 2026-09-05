# Bonding curve vs AMM: the dimension the dataset never had

2026-09-05. The single most important missing column, now captured. Everything
below is measured, not reasoned.

## The base rate, at last

**2.10% of tokens we have observed ever reached $69,000 of reported liquidity**
— 397 of 18,920. Pump.fun's published graduation rate is 1–2%. Our number lands
inside their band, which independently validates the proxy and gives this
project its first honest denominator. **Random looks like two per cent.** Every
hit rate quoted before now had nothing to be compared against.

## The category error, inverted

The concern was that we had been reading bonding-curve reserve as AMM exit
depth. Checked live rather than assumed:

    MOON       dex=pumpfun    liq=$0   base=None   quote=None    fdv=$24
    DRIP       dex=pumpfun    liq=$0   base=None   quote=None    fdv=$2,896
    $HotWhale  dex=pumpfun    liq=$0   base=None   quote=None    fdv=$2,901
    DGAF       dex=meteora    liq=$1   base=1313.358  quote=0.003412

**Dexscreener reports `liquidity.usd = 0` with no reserve split for a
bonding-curve pair.** It does not pass curve reserve off as pool depth. So the
error is the opposite one: curve tokens arrive with nothing, fail the liquidity
floor, and we score and journal them anyway.

## And that is most of what we do

| | tokens | share |
|---|---:|---:|
| all tokens ever observed | 18,920 | |
| first seen with **no pool** (curve) | 16,233 | **85.8%** |
| first seen with a pool (AMM) | 2,687 | 14.2% |
| zero liquidity at **every** observation | 16,002 | 84.6% |

## The two populations are not comparable — 227x apart

Tokens with a first observation and a later outcome, n=17,270:

| population | n | >= 2x | 95% CI | median mult | p99 mult |
|---|---:|---:|---|---:|---:|
| **curve (liq=0 at entry)** | 14,802 | **0.01%** | [0.00%, 0.04%] | 0.000 | 0.000 |
| **amm (pool at entry)** | 2,468 | **2.27%** | [1.75%, 2.93%] | 0.000 | 5.103 |

**Two wins in 14,802 curve tokens.** The intervals do not come close to
touching. These must never be pooled again, and every earlier analysis in this
repo that did pool them was diluting a 2.27% population with a 0.01% one.

## Score bands, split

    -- curve --                      -- amm --
    band      n     >=2x             band      n     >=2x     95% CI
    45-69  5,620    0.00%            100     747    1.20%   [0.64%, 2.27%]
    0-44   9,182    0.01%            70-99   264    4.55%   [2.62%, 7.78%]
                                     45-69   813    1.97%   [1.21%, 3.17%]
                                     0-44    644    2.95%   [1.90%, 4.56%]

Two things fall out. **No curve token has ever scored above 69** — the scorer
already refuses them, so the 85.8% of budget spent enriching them buys nothing.
And inside the AMM population, **70–99 beats 100 with non-overlapping intervals**
(4.55% [2.62, 7.78] against 1.20% [0.64, 2.27]). The ceiling is where the
losers are, and that now holds within a single venue class rather than across a
confounded mixture.

The template pattern lives **entirely** in the AMM population — 59 rows, none in
the curve population — as it must, since liq/fdv cannot be computed from a pair
that reports no reserves.

## Where the venue comes from: free, and already in hand

GeckoTerminal's new-pools discovery response carries it at
`relationships.dex.data.id`, in a payload the scanner already fetches and threw
away. No extra call. One live stream:

    pump-fun         37   bonding curve
    meteora-damm-v2   9   AMM
    pumpswap          8   AMM (graduated pump.fun)
    meteora-dbc       6   dynamic bonding curve

72% pre-graduation. `venue.py` classifies it; `scanner.scan()` records
`dex_id`, `venue_type` and `is_graduated` on every observation.

**The efficiency consequence is the biggest one here.** Skipping curve pairs at
discovery is free and would let the same enrichment budget cover roughly seven
times as many AMM tokens — which is a direct attack on stream coverage, the
headline metric. *Not implemented yet: it changes what we collect, and dropping
85.8% of the intake needs a decision, not an inference. Curve tokens that later
graduate would be seen later rather than never, but they would be seen later.*

## On-chain features: one shipped, one blocked, and a negative result

`onchain.py`, public Solana RPC, free and keyless.

**Mint / freeze authority — works, and is worthless here.** Queried 228 tokens
(57 winners, 171 matched non-winners):

| | n | wins | rate |
|---|---:|---:|---:|
| mint authority live | 1 | 0 | 0.0% |
| mint authority revoked | 227 | 57 | 25.1% |
| freeze authority live | 0 | — | — |
| freeze authority revoked | 228 | 57 | 25.0% |

**227 of 228 have both authorities already revoked.** The launchpads revoke them
automatically at launch, so in our universe the feature is a constant. A
zero-variance feature cannot discriminate and must not go in a score. It would
matter for tokens from arbitrary deployers; ours are not that.

Worth noting separately: **the template pools pass this check.** `worthless` and
`TIKZZZ` both have mint and freeze revoked. Conventional rug checks do not catch
them.

**Holder concentration — blocked on free tools.**
`getTokenLargestAccounts` returns HTTP 429 *"Too many requests for a specific
RPC call"* on `api.mainnet-beta.solana.com`. Tested at 0s, 5s, 15s, 30s and 45s
spacing: **0 of 5 succeeded.** The method is rate-limited per-method on the
public endpoint. `getAccountInfo` and `getTokenSupply` work fine, so this is not
a general throttle. Concentration needs a keyed RPC provider.

**A trap noted for whoever builds it:** `getTokenLargestAccounts` returns the
pool's own token account, which for a fresh launch holds nearly all supply. A
naive top-10 share is ~99% for every token, healthy or not — it would look like
a devastating signal while measuring nothing. `onchain.concentration()` already
reports the raw share, the share excluding the largest account, and whether the
largest account matches `liq_base`.

**Retrospective use has a direction rule.** On-chain state does not disappear, so
unlike Dexscreener the RPC answers for every token we have ever seen. But it is
*current* state:

    authority live NOW     => it was live at observation.   Sound.
    authority revoked NOW  => says nothing about observation time.

Only the first direction may be used on history.

## Deployer history: not built

Third on the priority list and reportedly the most predictive. It needs
transaction history for the mint account, which is `getSignaturesForAddress`
plus per-transaction parsing — many calls per token, on the same public RPC that
already method-limits the cheaper call above. Deferred rather than half-built.

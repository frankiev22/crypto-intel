# Pool discovery, rebuilt on derivation: what changed, what it corrected, what it still cannot do

**2026-09-23.** Frank: *"I would probably rather fix pool discovery. That's been a
problem for us. We can't publish shit data."* And: *"We have to be sure we have
our facts and receipts correct. Our data cannot be inaccurate."*

Rule: `PRECOMMIT_pool_state.md`, written before the derivation ran against the
record, with two **dated amendments** (§3a, §3b) that are corrections to the rule
itself rather than silent edits.

⛔ **Nothing here says a token is sellable.** A pool holding $41.07 of WSOL
returned `NO_SELL_ROUTE` from Jupiter, measured. The exit is
`chainfields.round_trip()` and only that.

---

## 1. The bug, stated as a mechanism and now PROVEN rather than inferred

We priced a token by looking up **one pool address someone else gave us**. For a
pump.fun token that address is usually its **bonding curve**, which still exists
after the token bonds and holds **nothing**, while the money sits in a PumpSwap
pool nobody told us about.

⭐ **All three `gone` contracts that turned out sellable had a recorded pair equal
to their own derived bonding curve:**

| token | recorded pair = derived curve | curve quote | the pool that actually holds it | its quote |
|---|---|---|---|---|
| NOOS | `4zhiY2VkGG4Ae3JQxM2cS15hzT1P9u7jD2L7EJCWuxSh` | $0 | `BiWTskxEzfMK1EeXdD2o7e8cP2iCNgZf7utwxcaHfYSE` | **$398.11** |
| JEANB | `5Cozv7kaYAhWjFq44MkZLzKNWNSPZnwpUAZyqAS1rHEA` | $0 | `9Vtqt6UruSVL8otRwYHughNLszXTE7E2hga2Z9AyYw6B` | **$439.39** |
| LOOONGJAK | `DyVDpYveqAUGB6riJwankicxHmhWAfjYc82NMq5BJuvq` | $0 | `7FfGFgaGobmcZNnmnC6kYTxwVTX2HQvGYAuWV5bYawN1` | **$361.97** |

⛔ **Correction to my own earlier report: I said 2 of 3 had a wrong recorded pair.
It is 3 of 3.** The earlier flag measured whether the ladder happened to also
surface the curve, not whether the pair was the right pool.

---

## 2. The method, and why no offset is guessed

A pool's address is either a **PDA** (a pure function of the mint) or **findable
by a memcmp** on the mint inside the pool's own account. Neither depends on how
much the pool holds, which is the failure mode of the token-account ladder: it
reaches the largest holders and it missed 2 of 15 sellable tokens whose vault was
not in the top 100 by base amount.

⛔⛔ **A guessed memcmp offset returns zero rows, and zero rows reads as "no
pool".** That is the `authority_live=None` bug, so every offset is **measured** by
finding the mint's 32 raw bytes inside a pool already known to belong to it
(`analysis/pool_offsets/probe.py` → `data/pools/offsets.json`, carrying the pool
each offset came from).

| venue | measured mint offsets | note |
|---|---|---|
| `pumpfun_curve` | PDA `["bonding-curve", mint]` | no offset needed |
| `pumpswap` | 43, 75 | ⭐ slot 43 exists only because of on-chain fixtures where OUR mint is the base |
| `raydium_v4` | 400 | ⚠️ **one-sided** (vaults under a shared authority) |
| `raydium_cpmm` | 168, 200 | ⭐ **added 2026-09-23**, in Frank's spec and never queried before |
| `raydium_clmm` | 73, 105, 454 | ⛔ **454 is a REWARD-mint slot**, not a traded pair |
| `meteora_dlmm` | 88, 120 | |
| `meteora_dynamic` | 8, 40 | |
| `meteora_dbc` | 136 | ⚠️ **one-sided**: its WSOL vault's mint is nowhere in the 424-byte struct (4/4) |
| `meteora_damm_v2` | 168, 200 | ⭐ found by measurement; our map had no name for it |
| `orca_whirlpool` | 101, 181, 269, 397 | the last two are reward slots |
| `fluxbeam` | 99, 131, 163 | ⭐ **found by measurement 2026-09-23**; 324-byte token-swap shape |
| `unnamed_amm_9W959Dq` | 99, 131, 163 | same shape, still unidentified |

⛔ **Still NOT queryable, so never asked:** `moonshot`, `obric`, `openbook`,
`raydium_launchlab`, `solfi`. Their absence from a result is **not evidence**, and
every response says so in `venues_NOT_queryable`.

⭐ **The pair guard, which the measurement forced.** A memcmp hit only counts as a
pool of this mint if **the pool itself holds a vault of this mint**. Otherwise a
reward-mint slot would publish someone else's pool as ours. ⚠️ An unreadable vault
set is `pair_verified: None`, a third answer, never a pass.

---

## 3. ⛔⛔ Three corrections the run forced on itself, all before the headline

### (a) `pool_closed` was too loose (§3a)

A PDA can be derived for a venue the token **never touched**.
`BsskZM8NNi6ayj3h9KUwawMuuY8hU4iB1QYxEaSuJAfh` does not end in `pump`, so its
bonding curve was never created, and its non-existence was scored `pool_closed`.
⭐ **An address that was never created is an absent venue, not a closed pool.**
`pool_closed` now requires **evidence the pool once existed** (`known_pair`, the
address an outcome row actually priced). ⚠️ So `pool_closed` is rarer by
construction and `not_found` now absorbs two different things.

### (b) A bonding curve's quote side is NATIVE SOL, and we read $0 (§3b)

`getTokenAccountsByOwner` cannot see lamports. ⭐ **Measured on 26 live curves: 2
hold >= $10 above the rent-exempt floor and one holds 1.978990 SOL = $226.61.**
Those would have been published as `curve_died` with "$0 of quote side".

### (c) A venue that owns no token accounts also read $0 (§3b)

⛔ **All 3 sampled Meteora DBC pools and the one FluxBeam pool return ZERO
vaults**, and **12 of 120 recorded pairs in this sample are DBC**. Fixed with
`pooldiscovery.vaults_from_struct()`: every 32-byte window of the pool's own data
is a candidate pubkey and the chain says which are real SPL token accounts. ⭐ **No
layout is assumed and no offset is needed** - a vault address is inside the struct
by definition. Measured: DBC 2 vaults each ($3.47 / $2.98 / $0.58 of WSOL),
FluxBeam 3 ($14.66).

⛔ **And when neither route reads a vault, `quote_usd` is None with a reason.** Such
a pool can no longer produce `pool_emptied` or `curve_died`, because both of those
assert there is no money in it.

---

## 4. The case that proves the READER was broken, and does NOT prove the token was alive

`BsskZM8NNi6ayj3h9KUwawMuuY8hU4iB1QYxEaSuJAfh` ("business"):

| method | answer |
|---|---|
| the indexer | `gone` |
| derivation, original `pool_closed` rule | `pool_closed` |
| derivation, after §3a | `not_found` |
| ⭐ derivation, after §3b | **`pool_live`, $14.64 of WSOL in a FluxBeam pool** |
| ⛔⛔ **a live $100 Jupiter round trip** | **TOTAL_LOSS: $0.0061 back, 99.9939% cost** |

⛔⛔ **LEAD WITH THE LAST LINE.** Our recorded pair was the right pool all along and
the bug was the reader, not the record - **but the token is still not sellable.**
A pool with $14.64 in it returns **six tenths of a cent** on $100.

⭐ **That is the whole reason `pool_live` is not allowed to mean sellable.** The
state describes a pool; the exit is `chainfields.round_trip()` and only that.

⚠️ **And there are TWO different contracts symbol'd `business` in this sample**
(`BsskZM8NNi6a…` on FluxBeam and `4NjzeT37BXXa…` on Meteora DBC/DAMM v2), which is
standing rule 2 arriving on schedule: the ticker is display only.

---


---

## 5. The measurement: 120 `gone` contracts, re-measured under the final rule

Sample: every distinct contract our own outcome rows labelled `gone` in 72h,
newest first, N=120 - **the same population as the ladder run**, so the two are
comparable. 11 venues queried (every venue in Frank's list, plus three found by
measurement). Cost: **3,720 RPC calls, 0 errors, 0 rate-limited, 20.4 minutes**
for the first pass; the whole set was then **re-measured** under the corrected
reader and both passes are on disk.

| state | n | share (Wilson 95%) |
|---|---|---|
| `curve_died` | **81** | **67.5% [58.69, 75.22]** |
| `pool_emptied` | **32** | **26.7% [19.57, 35.21]** |
| `pool_live` | **7** | **5.8% [2.85, 11.55]** |
| `pool_closed` | **0** | the only state that means what `gone` claimed |
| `not_found` | **0** | |
| `unreadable` | **0** | |

⭐⭐ **Every one of the 120 has at least one pool on chain.** The ladder returned
`NO_POOL_FOUND` on 15 of these 120; derivation resolved **15 of 15**. The
pre-registered prediction in §7 asked for at least 8, and named `curve_died` as
the expected dominant state. **Both hold.**

⛔ **`pool_closed` = 0 of 120, and that is now a meaningful zero rather than a
tautology.** The earlier version of this question read `getAccountInfo` on the
pool address our own row recorded and found 0 closed - but **86 of those 120
recorded pairs are pump.fun bonding curves, which are never closed when a token
bonds**, so the answer was guaranteed. ⭐ **The non-tautological slice: 34 of the
120 recorded pairs are real AMM pool accounts (12 Meteora DBC, 11 DAMM v2, 10
PumpSwap, 1 FluxBeam) and all 34 still exist.** n=34.

### ⭐⭐ The wrong-pool defect, measured properly at last

| question | answer |
|---|---|
| was the recorded pair a real pool of this mint? | ⭐ **yes, 120 of 120** |
| ⛔ was it the pool holding the MOST quote side? | **no, 17 of 119 (14.3% [9.11, 21.69])** |

⛔ **This corrects two of my own numbers.** The ladder run reported the recorded
pair was "not a discovered pool" **27 of 120 (22.5%)** - that was the ladder
failing to surface the curve, not a bad record. And "3 of 3" was an anecdote from
three sellable contracts, not a rate. **The honest figure is 14.3%**, and the
mechanism is the one the anecdote showed: a real, existing, **empty** bonding
curve recorded while another pool holds the money.

⚠️ **I also nearly published this at 61 of 61 (100%).** The first version compared
a full-precision pool value against `quote_usd_max`, which is rounded to 6 decimal
places on the way out, so every row failed an equality test. Caught before it left
the terminal; the comparison now runs against the pools' own values.

---

## 6. ⛔⛔ THE ONLY MEASURE THAT ANSWERS "CAN HE SELL IT": a live $100 round trip

Every `pool_live` contract was put through `chainfields.round_trip()`. ⚠️ **Quotes,
not fills. Nothing was signed.**

| symbol | contract | derived reserves | verdict | $100 returns |
|---|---|---|---|---|
| APEZCAT | `8scSC6m9Y2YDH5hRxvmVPLHUctzyRceh6oYV27pRpump` | $1,242.29 | ⭐ **TRADEABLE** | **$91.94** (8.06%) |
| TRADER | `FrCB5Zhda9swKKQNh5uAiiC2pH2trFH1WC2Umddipump` | $226.46 | ⭐ **TRADEABLE** | **$92.52** (7.48%) |
| CATP | `atQMQhdARupehhVDRcBU11t5DjM1HcraUnHEJcUpump` | $11.48 | ⭐ **TRADEABLE** | **$92.24** (7.76%) |
| PERPY | `Dj2dYF8BtWVf7txmRkpBzFHYQ7iraL3CLjNJgaki6rvF` | $11.08 | ⭐ **TRADEABLE** | **$90.80** (9.20%) |
| Robinhood | `J5UM626sfU7NMLe1fSsU9YWA8eLutoSunPoqVjZkpump` | $22.67 | ⛔ **NO_SELL_ROUTE** | cannot be sold |
| business | `4NjzeT37BXXaS1sGQnZvbAwwKgspMgKT11Pu3ZUrvm7A` | $22.12 | ⛔ TOTAL_LOSS | $0.84 |
| business | `BsskZM8NNi6ayj3h9KUwawMuuY8hU4iB1QYxEaSuJAfh` | $14.64 | ⛔ TOTAL_LOSS | $0.0061 |

### ⛔⛔ CORRECTION TO THE FOUR, SAME DAY: two of them are SELF-FINANCED

A round trip **buys and then sells**. When the pool holds **less than the probe
size**, the SOL the sell leg pays out is largely the SOL the buy leg just put in.
⭐ **The control is unambiguous**: a mint symbol'd BOUNCER whose bonding curve
holds **$0.00** still returns **$92.22** on a $100 round trip. So TRADEABLE on a
thin curve is **not** evidence that $100 of exit was already sitting there, and
Frank sells a bag he already holds rather than round-tripping.

| token | reserves that pre-existed the probe | $100 round trip | what it means |
|---|---|---|---|
| APEZCAT | **$1,238.65** | $91.94 | ⭐ the exit was already there |
| TRADER | **$225.80** | $92.53 | ⭐ the exit was already there |
| CATP | $11.45 | $92.23 | ⚠️ round-trippable, **self-financed** |
| PERPY | $11.04 | $90.79 | ⚠️ round-trippable, **self-financed** |

⛔ **So the honest count is 2 of 120 with pre-existing $100 depth, and 4 of 120
round-trippable.** `analysis/pool_offsets/roundtrip_live.py` now carries
`self_financed` and its reason on every row, and prints both counts.

⭐⭐ **4 of 120 contracts our own pipeline wrote off as `gone` can be round-tripped
for $100 today, and 2 of those had the depth already in the pool.** ⛔ **And 3 of those 4 are visible ONLY because of today's two
quote-reader fixes:** TRADER and CATP hold their entire quote side as **native SOL
in a bonding curve** (the old reader said $0, state `curve_died`), and PERPY's only
pool is a **Meteora DBC** whose vaults the old reader could not see at all.

⛔⛔ **Robinhood is the counter-example that keeps `pool_live` honest**: $22.67 of
reserves on chain and **no sell route at all**. 3 of 7 `pool_live` contracts cannot
be exited. **Reserves are not an exit price, measured again.**

## 7. What none of this fixes

- ⛔ **Existence is not liquidity.** Every state here is about pools, never fills.
- ⚠️ **A backfill measures the pool TODAY.** A pool drained after we scored a row
  is indistinguishable from one drained before. Every row carries
  `backfilled: true` and no rate over them describes the moment of scoring.
- ⛔ **Five venues have no measured offset**, and two more are one-sided.
- ⚠️ **`journal.py` still writes the word `gone`,** and that is deliberate:
  renaming the field relabels outcomes across the whole record, which needs its
  own pre-commit rather than a patch. ⭐ **What did change: the row no longer
  pretends to know why.** Every `gone` row now carries `status_reason` saying two
  indexer lookups of the recorded pair returned nothing, that this is our lookup
  failing rather than evidence a pool closed, and where the measured state lives.
  `test_gonelabel.py` (12/12) calls `record_outcome` in the sandbox and reads the
  row back **off disk**, because this repo has lost five fields to computing a
  value and never persisting it.

- ⛔ **`pool_live` is not sellable.** Measured today: 3 of 7 `pool_live` contracts
  returned NO_SELL_ROUTE or TOTAL_LOSS on a live $100 round trip.
- ⚠️ **`raydium_launchlab`, `moonshot`, `obric`, `openbook` and `solfi` were never
  asked.** Their absence from any result is our coverage gap.

---

## 8. ⛔ The five venues with no measured offset: THREE fixture routes tried, all empty

An offset can only be measured on a pool we already know belongs to a mint, so
these five need one fixture each. Three independent routes, all run today:

| route | result |
|---|---|
| the indexer's pair list for **8 of the most liquid Solana mints** (240 pairs) | ⛔ **0 pairs** owned by any of the five. Every pair resolved to a venue we already measure |
| **Jupiter's launch feed**, 37 distinct launches over 3 polls | ⛔ unusable: **`firstPool.id` is the MINT, not a pool** (31 of 37 resolved to a Token program). One `raydium-launchlab` launch appeared, and ⛔ **its mint has 52 holders and NOT ONE program-owned vault**, so it has no pool yet at all |
| the indexer's own **dexId search** for launchlab / moonshot / solfi / obric / openbook | ⛔ launchlab, obric and openbook return **0 Solana pairs**; the moonshot and solfi text searches return pairs on other venues, which is a name match and not a venue match |

⭐ **And the structural reason, which the measurement now supports:**

- **`openbook`** is a central limit order book. Its accounts are **markets**, not
  AMM pools with vaults, so a mint-offset memcmp is the wrong instrument for it.
- **`obric` and `solfi`** are **PMM / market-maker** programs. We already measured
  that class: BisonFi carries **$446.8M/day across 17 program accounts** and
  **launches nothing**, and Jupiter already routes through them. Parsing one adds
  market-maker inventory, not token coverage.
- **`moonshot` and `raydium_launchlab`** are launchpads, so their pools are fresh
  curves that can never rank inside a liquid mint's 30-pair cap. **1 of 37**
  launches in a three-poll sample was launchlab.

⛔ **So the five stay unqueryable, and every response keeps naming them.** What
would produce a fixture: a LaunchLab or Moonshot token that has actually **traded**
(the ladder finds its pool from the mint, as it did for FluxBeam), or enumerating
the program's own accounts, which ⚠️ **hung past 120s on two large programs
earlier today** and is not a cheap route.

⚠️ **This is a FLOOR statement, not a completeness claim**: three routes failing
means we have no fixture, not that no pool exists.

# PRE-COMMIT: derive the pool from the mint, and replace `gone` with what we measured

**Written 2026-09-23 before any derivation code was run against the record.**
Standing rule 6. This supersedes the discovery half of
`PRECOMMIT_pool_discovery.md` and keeps its verdict bands.

Frank: *"I would probably rather fix pool discovery. That's been a problem for
us. We can't publish shit data."*

---

## 1. Why the previous method was not enough

`PRECOMMIT_pool_discovery.md` found pools by enumerating the mint's token
accounts and asking which program owned each holder. That works and it is
venue-agnostic, but it is a **LADDER**: it reaches the largest holders only, so
it missed **2 of 15** sellable tokens in its own validation, and the cause on one
of them was that the pool's vault is not among the top 100 holders by base
amount.

⭐ **Derivation has no such failure mode.** A pool's address is a deterministic
function of the mint (a PDA) or is directly queryable by the mint (a
`getProgramAccounts` memcmp against the pool's own mint field). Neither depends
on how much the pool holds.

⛔ **And the record-level bug is worse than the discovery one.** Of the three
`gone` contracts measured sellable, **two had a recorded pair that was not the
pool holding the money**. We priced the wrong account and then called the token
dead. That is ours, not the market's.

---

## 2. The derivation method, fixed before it runs

**Primary, for every mint, in this order. Each venue records which method
answered.**

1. **PDA derivation** where the seeds are a pure function of the mint:
   - pump.fun bonding curve: `["bonding-curve", mint]` under
     `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P`.
2. **`getProgramAccounts` with a memcmp on the pool's own mint field**, per
   venue: PumpSwap, Raydium v4 / CPMM / CLMM, Meteora DLMM / dynamic / DBC, Orca
   Whirlpool. Both the base and the quote position are queried, because our mint
   can be on either side.
3. **The token-account ladder** from `PRECOMMIT_pool_discovery.md`, kept as a
   **supplement** so a venue absent from the map can still surface.

⛔⛔ **NO STRUCT OFFSET IS ASSUMED. EVERY OFFSET IS MEASURED FIRST.** For each
venue, a known (pool, mint) pair is fetched and the mint's 32 raw bytes are
searched for inside the pool account. The offset that is found is the offset
used, it is written to `data/pools/offsets.json` with the pool it was measured
on, and a venue whose offset could not be measured is **NOT QUERIED AT ALL**
rather than queried at a guess. A guessed offset returns an empty result, and an
empty result reads as "no pool", which is the `authority_live=None` bug for the
seventh time.

⚠️ **A memcmp query returning nothing is only evidence when its offset was
verified.** Every row records `offset_verified` per venue.

## 3. ⛔ The `gone` replacement, with the thresholds fixed now

`gone` is wrong about mechanism in **7 of 8** cases: it says the pool is gone, and
the pool exists 87.5% [80.4, 92.3] of the time. It is replaced by four states
that name what was actually measured.

| state | rule |
|---|---|
| **`pool_closed`** | ⛔ **AMENDED 2026-09-23, see §3a.** The pool we have INDEPENDENT evidence once existed - the address an outcome row actually priced - **does not exist on chain**, and no other pool of this mint does either. **The only state that means what `gone` claimed.** |
| **`pool_emptied`** | the pool account exists and its **quote-side reserves are < $10**, read from its own vaults |
| **`curve_died`** | the only venue found is the **pump.fun bonding curve**, it still holds its base tokens, and the mint never appears at any AMM. **It never bonded.** |
| **`pool_live`** | a pool exists with **>= $10** of quote side. ⚠️ Not a claim that it is sellable - see §5 |
| **`not_found`** | ⛔ **no pool could be derived or discovered. This is OUR UNCERTAINTY and is never a claim about the token.** |
| **`unreadable`** | an RPC failed. ⛔ Its own bucket, never folded into any other |

⛔ **`$10` is the same dust boundary already pre-committed in
`PRECOMMIT_pool_discovery.md` §6 and is not re-tuned here.**

⚠️ **`curve_died` and `pool_emptied` are both "the pool exists and is empty".**
They are separated because the mechanism differs and Frank asked for the
mechanism: one never reached an AMM, the other did and was drained.

## 3a. ⛔⛔ AMENDMENT, 2026-09-23, SAME DAY, AFTER 28 BACKFILL ROWS

**The original `pool_closed` rule above was too loose and it produced a wrong
label on its 25th row.** It is corrected here rather than edited away, because a
pre-commit that is quietly rewritten is not a pre-commit.

**What it said:** *the derived pool account does not exist on chain
(`getAccountInfo` returns null for every derived address, and at least one
address was derived).*

**What went wrong.** `BsskZM8NNi6ayj3h9KUwawMuuY8hU4iB1QYxEaSuJAfh`, symbol
`business`, backfilled as `pool_closed`. Its only derived address was a pump.fun
bonding-curve PDA, which does not exist. ⛔ **But that mint does not end in
`pump`, so it never launched on pump.fun, so that PDA was never created in the
first place.** A PDA is a pure function of the mint: we can derive an address for
a venue the token never touched, and `getAccountInfo` returning null there says
**the token was never on that venue**, not that a pool closed.

⭐ **An address that was never created is an ABSENT VENUE, not a closed pool.**
This is the `authority_live=None` shape once more: not-checked, or in this case
never-existed, rendering as a positive finding.

**The corrected rule, and it is narrower on purpose:**

- `pool_closed` requires **evidence the pool once existed**. The only such
  evidence this repo holds is the pool address an outcome row **actually priced**
  (`known_pair`, passed in by the backfill from the row's own `pair` field).
- If that known pool is absent on chain and no other pool of the mint is live,
  the state is `pool_closed`.
- ⛔ **A speculatively derived PDA that does not exist yields `not_found`**,
  which §3 already defines as OUR UNCERTAINTY and never a claim about the token.
- ⚠️ Therefore **`pool_closed` is now rarer by construction**, and a low
  `pool_closed` count is partly a statement about what evidence we kept, not only
  about the market. That is the honest trade and it is stated here before the
  re-run.
- ⚠️ And when no `known_pair` is available at all, `pool_closed` is
  **unreachable** for that row. It falls to `not_found`. ⛔ **So `not_found`
  absorbs two different things** - we could not find a pool, and we could not
  prove one ever existed - and neither may be read as the token being alive or
  dead.

⭐ **The 28 rows measured under the old rule are NOT deleted** (standing rule 8).
They are kept at `data/pools/state_v1_superseded.jsonl` and the re-run writes a
fresh `data/pools/state.jsonl`. Any figure quoted from the superseded file must
say so.

## 3b. ⛔⛔ SECOND AMENDMENT, 2026-09-23: TWO QUOTE-SIDE READS WERE WRONG

Both were found by measurement **before** the corrected run, and both are the
same shape as the defect §3a fixed: **a number we never read, published as zero.**

**(1) A pump.fun bonding curve's quote side is NATIVE SOL, and we read $0.**
`_vaults` asks `getTokenAccountsByOwner`, which cannot see lamports. ⭐ Measured on
**26 live curves** from this sample: **2 hold >= $10 above the rent-exempt floor,
and one holds 1.978990 SOL = $226.61.** Under the original rule those would have
been labelled `curve_died` with "$0 of quote side", which is a false statement
about a curve with real money in it.
**Corrected:** for `pumpfun_curve` the quote side is `lamports - rent_exempt(len)`
valued at the run's SOL price, labelled `native SOL above the rent-exempt floor`.
⛔ If lamports, the rent floor or the SOL price is missing, the answer is
**unknown, not zero** (standing rule 5).

**(2) A venue that owns no token accounts read as $0 of quote side.**
⛔ **Measured: all 3 sampled Meteora DBC pools and the one FluxBeam pool return
ZERO vaults from `getTokenAccountsByOwner`**, because those venues keep their
vaults under a separate authority. Our reader turned that into `$0.00` with
nothing unvalued - a confident zero. **12 of 120 recorded pairs in this sample are
DBC**, so this was not an edge case.
**Corrected:** `pooldiscovery.vaults_from_struct()` treats every 32-byte window of
the pool's own data as a candidate pubkey and asks the chain which of them are
real SPL token accounts. ⭐ **No layout is assumed and no offset is needed**: a
vault address is inside the struct by definition. Measured result on those four
pools: 2 vaults each for DBC (base + WSOL) and 3 for FluxBeam, with the WSOL leg
worth **$3.47 / $2.98 / $0.58 / $14.66**.
⛔ **And if neither route reads a vault, `quote_usd` is None with a reason, never
0.0**, and such a pool can no longer produce `pool_emptied` or `curve_died` - both
of those assert there is no money in it. The state becomes `unreadable`.

⛔⛔ **And the struct scan keeps ONE AUTHORITY GROUP.** A pool struct can name an
account that is not the pool's own - a protocol fee vault, a router's account - and
summing one of those would **overstate** this pool's quote side, which is the one
direction we must never err in. So the scan keeps only the vaults sharing the
authority of the vault holding **our** mint, records every vault it dropped and
why, and if no vault of our mint is in the struct there is **no anchor** and
nothing is summed at all. ⭐ Tested with a fabricated 500-SOL foreign fee vault: it
is dropped, not counted, so the guard is worth **$50,000 of overstatement** on that
one fixture.

**Venue set extended, and this is disclosed because it was discovery-driven.**
After measuring that 12 of 120 recorded pairs were Meteora DBC and 1 was FluxBeam,
and that **neither venue had a measured offset so neither was ever queried**, both
were measured and added: `meteora_dbc` at **[136]**, `fluxbeam` at **[99, 131,
163]**. ⚠️ **The $10 dust boundary was NOT touched** - extending coverage is not
the same as tuning a decision boundary after seeing which rows fail.

⚠️ **A new measured limit, carried on every response as `venues_one_sided`.**
`meteora_dbc` stores ONE mint slot and holds a WSOL vault whose mint is **nowhere
in its 424-byte struct** (4 of 4 samples), and `raydium_v4` yields one slot
because its vaults sit under a shared authority. ⛔ **So for those two venues a
pool where our mint is on the OTHER side is invisible to us**, and their absence
from a result is a floor, not a fact.

⭐ **The case that proves the whole exercise:** `BsskZM8NNi6ayj3h9KUwawMuuY8hU4iB1QYxEaSuJAfh`
was `gone` to the indexer, `pool_closed` under §3's original rule and `not_found`
after §3a. It is **`pool_live` with $14.64 of WSOL in a FluxBeam pool** - and
**our recorded pair was the right pool all along.** The bug was the reader, not
the record.

## 4. The backfill, and its limit

- Every outcome row currently labelled `gone` is **re-derived** and gets a new
  field **`pool_state`**, plus `pool_state_measured_at` and the derived pool
  addresses.
- ⛔⛔ **`status` IS NOT OVERWRITTEN. Nothing is deleted (standing rule 8).**
  `gone` stays on the row as the historical label; `pool_state` is the measured
  one. Anything reading these rows must prefer `pool_state` when present.
- ⚠️ **A backfill measures the pool TODAY, not at the time the row was written.**
  A pool drained after we scored it will backfill as `pool_emptied` and we cannot
  tell that from one drained before. **Every backfilled row carries
  `backfilled: true` and its measurement time**, and no rate computed across
  backfilled rows may be described as a rate at the time of scoring.

## 5. ⛔ What none of these states claim

**None of them says the token is sellable.** Measured in the previous run: a pool
holding **$41.07** of WSOL returns **NO_SELL_ROUTE** from Jupiter. So
`pool_live` means a pool exists with reserves, nothing more. **The exit is
`chainfields.round_trip()` and only that.**

## 6. What would make this wrong

- ⛔ **A venue we do not query.** Derivation only finds pools at the eight
  programs listed. A pool elsewhere reads as `not_found`, which is why
  `not_found` is defined as our uncertainty.
- ⛔ **A wrong offset that still returns rows** would produce false pools. Guarded
  by measuring the offset against a known pool and by requiring the returned
  account to actually contain the mint.
- ⚠️ **Token-2022 mints** sit under a different token program and their vaults are
  fetched separately; a venue that only supports one program will read empty.

## 7. Pre-registered prediction

⭐ **I expect derivation to find a pool for more of the sample than the ladder
did: the ladder returned `NO_POOL_FOUND` on 15 of 120, and I expect derivation to
resolve at least 8 of those 15.**

⭐ **And I expect the dominant state to be `curve_died`**, because the measured
venue split was `pumpfun_curve` 82 against `pumpswap` 25.

⛔ **If derivation resolves fewer than 4 of the 15, the derivation adds little
over the ladder and this file says so.**

# PRE-COMMIT: find the REAL pool from the MINT, on chain, and price the quote side

**Written 2026-09-23 before a single contract in the sample was queried.**
Standing rule 6. The instrument was validated first, on a mint deliberately
OUTSIDE the sample (the real EMBER), and that validation is described in section
3 so the method is not mistaken for a result.

---

## 1. ⛔ Lead with the correction: my own on-chain probe answered the wrong question

Frank, 2026-09-23: *"I think the 1.7% testing result is inaccurate. We need to use
the contract address to find the real pool so we can see it after bonding."*

He is right, and the defect is worse than the one he is pointing at.

⛔ **`PRECOMMIT_gone_onchain.md` reported POOL_EXISTS 54, POOL_ABSENT 0 and I
presented it as a finding about `gone`. It was a tautology.** That probe called
`getAccountInfo` on the pool address **our own outcome row recorded**, and
**all 54 of those were `pumpfun_curve` accounts**. A bonding-curve account is not
closed when a token bonds. So "the account still exists" was guaranteed before the
first RPC, and the result contained no information about whether the token has a
market.

⛔ **The real pool after bonding is a different account we never recorded.**
`docs/BACKLOG.md` A52 already measured this: **243 rows on 135 distinct contracts
were scored against a pump.fun curve AFTER our own graduation ledger recorded the
migration.** So the population labelled `gone` is dominated by tokens that left
the curve, and we were reading the abandoned curve and calling the token dead.

⛔ **And the earlier 1.7% all-pairs result is dead for the reason Frank gave:**
118 of its 120 rows returned NO_PAIRS on **both** arms, so both arms asked the
same indexer. An indexer returning nothing has a normal explanation - a pool
empties or is delisted when a token bonds or dies on the curve - so **silence
proves nothing.**

⭐ **The question this file answers instead:** starting from the CONTRACT ADDRESS,
does this mint have a pool ON CHAIN holding real quote-side reserves that the
indexer did not list? That number is the true correction rate.

---

## 2. The sample, fixed before it is drawn

- Every distinct **contract address** with `status == "gone"` on an outcome row in
  the last **72 hours**, ordered by the row's own timestamp, newest first.
- **`N_SAMPLE = 120`**, to be comparable with the all-pairs run that Frank
  rejected. ⛔ No other selection, and nothing is dropped for being inconvenient.
- The row's recorded `pair` is carried along **for comparison only**. ⛔ It is
  never used to find the pool. That is the bug being corrected.

---

## 3. The instrument, validated BEFORE the rule was written, on a mint outside the sample

⚠️ This section is method validation, not a result. It was run against the real
EMBER (`5dvXTZ5qwgafnHtwu3Ls3QrWx1U4LQsFeCuJgkk4QEC6`), which is not a `gone` row.

| probe | outcome |
|---|---|
| `getTokenLargestAccounts(mint)` | 20 accounts, 0.54s |
| resolve those 20 owners, then the owners' programs | found **1 Meteora DLMM pool** (`LBUZKhRx…`) |
| `getProgramAccounts` on the SPL Token program, memcmp mint @ offset 0, `dataSlice` owner+amount | **60,691 token accounts in 6.5s** |
| resolving all 60,691 owners in 100-chunks | ⛔ **HTTP 429 immediately.** 607 calls is not affordable |

⭐ **Two things follow, and both go in the rule.**

1. **Enumeration by mint is exact and cheap**, because the SPL token-account
   layout is fixed and public (mint @0, owner @32, amount @64) so no program
   layout has to be guessed.
2. ⛔ **Resolving every holder is NOT affordable, so discovery is a LADDER and its
   answer is a FLOOR.** EMBER has 30 pools and the top-20 holders surfaced only
   **one**, because user wallets outrank individual pools.

---

## 4. The discovery ladder, and every mint records which rung answered it

**Rung 1, always.** `getTokenLargestAccounts(mint)` → up to 20 token accounts.
Resolve each account's `owner`, then each distinct owner's owning **program**. Any
owner owned by a **known AMM or launchpad program** (the `AMM_OWNERS` map, same
one `analysis/gone_onchain/probe.py` uses) is a **discovered pool**.

**Rung 2, only when rung 1 finds no pool.** Full `getProgramAccounts` enumeration
of the mint's token accounts with `dataSlice {offset: 32, length: 40}`, sorted by
amount, and the **top 100** owners resolved. Both the SPL Token program and
Token-2022 are enumerated.

**Rung 3, for every discovered pool.** `getTokenAccountsByOwner(pool, TOKEN
program)` → **every vault that pool holds**, which is what gives the QUOTE side.
Token-2022 vaults are fetched in the same way.

⛔ **The row records `rung`, the pool addresses found, and the program that owns
each.** A method that cannot say how it got its answer is not auditable.

## 5. Pricing the quote side

- **WSOL / native SOL** (`So1111…112`), **USDC** (`EPjFWdd5…`) and **USDT**
  (`Es9vMFrz…`) vaults are valued. SOL is converted at **one** price, read once
  at the start of the run, and **the price and its read time are recorded on the
  output**.
- ⛔ **A vault in any other quote asset is COUNTED and reported with a NULL USD
  value, never valued at 0.** Standing rule 5. The count of such vaults is on
  every row, so "we could not value it" can never read as "it is worth nothing".
- A pool's own **lamports** are recorded separately, because a pump.fun curve
  holds SOL natively rather than in a vault. ⚠️ Lamports include rent and are
  **not** treated as tradeable reserves.

## 6. The verdicts, per contract

| verdict | meaning |
|---|---|
| **POOL_QUOTE_100** | a discovered pool holds **>= $100** of valued quote-side reserves. ⛔ This is proof the indexer was wrong |
| **POOL_QUOTE_10** | >= $10 and < $100 |
| **POOL_QUOTE_DUST** | a pool exists, valued quote side < $10 |
| **POOL_QUOTE_UNVALUED** | a pool exists with vaults we could not value. ⛔ Its own bucket, never folded into DUST |
| **NO_POOL_FOUND** | no AMM-owned account among the holders the ladder reached. ⚠️ **NOT proof that no pool exists** |
| **UNREADABLE** | an RPC failed or was rate limited. ⛔ Its own bucket, never folded into any other |

⛔ **The asymmetry is the most important line in this file.** Finding a pool with
reserves is **proof** the `gone` label was wrong about that contract. Finding no
pool is **not** proof there is none, because the ladder is a floor. So the headline
is a **LOWER BOUND on the error rate**, and it must be published as one.

## 7. What counts as the headline number

**`POOL_QUOTE_100 / (every verdict except UNREADABLE)`**, with its n and a Wilson
interval, stated as **"at least this share of `gone` contracts have a real market
the indexer did not show us"**.

- The $10 band and a combined `POOL_QUOTE_100 + POOL_QUOTE_10` figure are reported
  beside it, so the answer is not hostage to one threshold.
- `POOL_QUOTE_UNVALUED` is reported as its own share.
- ⛔ **If `UNREADABLE` exceeds one third of the sample, no rate is published at
  all** and the finding is about our RPC budget rather than about the market.

## 8. Pre-registered prediction, so the result cannot be rationalised afterwards

⭐ **I expect between 15% and 45% of the sample to be POOL_QUOTE_100.**

The reasoning, stated now: `gone` is written when two lookups of the recorded
**pair address** fail, that pair is a bonding curve in the overwhelming majority
of these rows, and a curve stops being a listed pair the moment the token bonds.
So a token that bonded successfully and still trades on PumpSwap is exactly the
case most likely to be mislabelled `gone`, and those tokens have real reserves.

⛔ **What would falsify it, and what each outcome means:**

- **Under 5%** - `gone` is roughly honest about liquidity even though it is wrong
  about mechanism. The label still has to change, but no outcome needs relabelling
  for value. **My prediction was wrong and this file says so.**
- **Over 45%** - worse than I expect, and the outcome record is broadly corrupted
  for this population.
- ⚠️ Either way the answer is about **72 hours of rows on one chain**, is not a
  base rate for all time, and is reported with its window attached.

## 9. What this becomes, beyond the experiment

⛔ **This is not a one-off.** `intel.liquidity(mint)` must fall back to on-chain
pool discovery whenever the indexer returns nothing, because **"we could not find
it" and "it does not exist" are different answers** and collapsing them is the
`authority_live=None` bug class for the sixth time in this repo.

The permanent shape, pre-committed here so the experiment cannot quietly become
the product without it:

- The ladder lives in its own module with its own tests.
- `liquidity()` calls it only on an indexer miss, and the response says **which
  source answered** and that discovery is a **floor**.
- ⛔ A discovered pool's reserves are **shape and existence**, never an exit price.
  The exit stays `chainfields.round_trip()`, which routes across every pool.

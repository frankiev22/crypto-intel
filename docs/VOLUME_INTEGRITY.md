# Volume is the easiest number to fake, and now there is a reason to

**2026-09-17. Methods, measured signals, and pre-committed thresholds.**

> *"volume is easily fakeable, so how can we protect against that? I've seen so
> many volume bots on DEX screener."* — Frank

---

## ⭐ 1. Why this got worse, and why it is now structural

**pump.fun changed how creators are paid, and the change creates a direct
financial incentive to wash trade your own token.**

| | old | now (2026) |
|---|---|---|
| graduation bonus | **0.5 SOL** | ⚠️ **still 0.5 SOL** — Frank's question answered, it did not go away |
| ongoing creator cut | effectively none | **0.30% of every trade on the curve**, out of a 1.25% total |
| after graduation | none | **up to 0.95% of every trade** in lower market-cap tiers, tapering |

**pump.fun distributed $2M to creators in the first 24 hours of the new model.**

⛔ **The incentive has inverted.** Under the old model a creator was paid once,
for reaching $69k. **Under the new one a creator is paid a percentage of every
trade, forever — including trades they make with themselves.** Wash trading was
previously done to attract buyers; it is now *directly revenue-generating* even
if no outside buyer ever appears.

⭐ **This is why volume integrity is now a first-class field and not a caveat.**
Any volume-derived signal in this repo is measuring a number the token's creator
is paid to inflate.

## 2. The five methods, and what they actually measured

Measured on 60 parsed transactions per token, keyed on the **mint** and using
`jsonParsed` transaction metadata. ⚠️ **n = 4 tokens. This is a method
demonstration, not a validated detector.**

```
sym       parsed  signers  uniq/tx  top share  repeat%  same-slot  DUP AMT%
BONK           8        7     0.88       25%      25%          0       17%   liquid control
ROCK          51       28     0.55       18%      59%          1        0%   TRADEABLE
WOFI          60       51     0.85        7%      22%          5       80%   COSTLY, 43 holders
POGGERS       60       29     0.48       12%      78%          5       90%   TOTAL_LOSS
```

### ⭐ M1. Trade-size clustering — the strongest signal found

**`dup_amount_share`**: the share of observed token-balance deltas whose exact
size has been seen before.

**0% and 17% on the healthy pair; 80% and 90% on the two bad ones.**

Humans trade round dollar amounts, not identical token quantities to four
decimal places. **A bot loops a fixed size.** This separated cleanly and it is
the cheapest of the five to compute.

### ⭐ M2. Same-block clustering

**`multi_tx_slots`**: slots containing more than one transaction on this mint.

**0 and 1 on the healthy pair; 5 and 5 on the bad ones.** Two trades in the same
~400ms slot is either a bundle or one actor running parallel wallets. It is the
same primitive that makes launch bundling detectable.

### M3. Repeat-wallet share

**`repeat_wallet_txn_share`**: fraction of transactions from wallets seen more
than once. POGGERS 78%, ROCK 59%, WOFI 22%, BONK 25%.
⚠️ **Did not separate.** ROCK is genuinely tradeable and scores high; WOFI is
junk and scores low. **Do not use alone.**

### M4. Unique-buyer-to-trade ratio

**`distinct_signers / parsed`**. BONK 0.88, WOFI 0.85, ROCK 0.55, POGGERS 0.48.
⚠️ **Inverted from expectation** — the worst token scored near the best.
**Reject as a standalone signal.** A wash operation using many fresh wallets
produces a *high* unique ratio, which is exactly what a naive reading rewards.

### M5. Wallet-age distribution — ⛔ specified, not yet measured

For each trading wallet, the age of its first transaction. A cohort of wallets
all funded within minutes of each other is a farm.
**Cost:** one `getSignaturesForAddress` per wallet, so ~50 extra RPC calls per
token. Affordable at decision points, not on the scan path. **Not measured yet
and therefore not claimed.**

## 3. ⛔ Pre-committed thresholds — written before any validation run

Per standing rule 6, these are fixed **now**, before being tested on anything
beyond the four tokens above, so the test cannot be tuned to its result.

```
VOLUME_SUSPECT if  dup_amount_share  >= 0.50        # M1
               or  multi_tx_slots    >= 4  per 60 txns   # M2

VOLUME_CLEAN   if  dup_amount_share  <  0.25
               and multi_tx_slots    <= 1

otherwise      VOLUME_UNKNOWN
```

⚠️ **`VOLUME_UNKNOWN` is a real state and must render as "unknown"**, never as
clean and never as 0 — the same rule that governs every other field here.

**Validation required before any of this is quoted:** n ≥ 30 tokens per arm,
labelled independently by `chainfields.round_trip()` verdict, Wilson intervals
on the separation, reported both ways.

## 3b. ⛔ A flaw in M1 as computed, and a corrected variant — PRE-COMMITTED 2026-09-19 before any validation run

**Found while building the validation (`volintegrity.py`), before it ran.** One
swap moves the same token quantity out of the pool and into the trader, and when
both token accounts appear in `pre/postTokenBalances` the 09-17 computation
records **two equal deltas**, e.g. BONK, one swap: `+326,173.12` and
`−326,173.12`. It counts every delta in a repeated-size group, so **a single
ordinary swap can register as a "repeated trade size"**. The n=4 separation in §2
may partly reflect which routes happened to show both legs. **Unresolved — the
09-17 script's per-token raw output was not saved.**

**What happens now, in this order, so neither result can be tuned:**

1. **§3 is validated exactly as committed** — the 09-17 computation, unchanged
   except version-1 transactions and "no trades = unknown" (`volintegrity.py`).
2. **Alongside it, on the SAME fetched transactions, a corrected M1′:**
   `dup_amount_share_tx` — within one transaction, equal absolute deltas of the
   mint collapse to one transfer size; the share is then taken across
   transactions, counted the 09-17 way. **Same thresholds, fixed now:**

```
VOLUME_SUSPECT_V2 if  dup_amount_share_tx >= 0.50  or  multi_tx_slots >= 4
VOLUME_CLEAN_V2   if  dup_amount_share_tx <  0.25  and multi_tx_slots <= 1
otherwise         VOLUME_UNKNOWN
```

3. Both are reported, both ways (all sampled / verdicts only), with Wilson
   intervals, labelled by the universe gate's `round_trip` verdict:
   TRADEABLE members vs tokens refused at the gate, seeded random, n ≥ 30 per arm.

⛔ **Neither is quotable as a detector unless it separates the arms on that
run.** A null result is the finding, and it gets written here.

## 3c. ⛔ RESULT, 2026-09-19: both rules FAIL validation. Not a detector; do not quote

`volintegrity.validate(30)`, seeded 20260919, labelled by the universe gate's
round trip. 30 TRADEABLE members against 30 tokens refused at the gate; 3,600
transactions, all read at version 1. Evidence:
`data/findings/volintegrity_validation_2026-09-19.json`.

| rule | TRADEABLE flagged SUSPECT | NOT TRADEABLE flagged SUSPECT |
|---|---|---|
| §3 (09-17, as committed) | **29/30 = 96.7% [83.3, 99.4]** | 27/30 = 90.0% [74.4, 96.5] |
| §3 on verdicts only | 29/29 = 100% [88.3, 100] | 27/28 = 96.4% [82.3, 99.4] |
| §3b M1′ + M2 | **19/30 = 63.3% [45.5, 78.1]** | 18/30 = 60.0% [42.3, 75.4] |
| §3b on verdicts only | 19/22 = 86.4% [66.7, 95.3] | 18/26 = 69.2% [50.0, 83.5] |

**Neither separates, and on verdicts only the direction is inverted:** the
tokens you can actually sell are flagged more often. Why:

- **M1 as committed counts both legs of every swap** (§3b). The median TRADEABLE
  token scores 0.845, so almost everything reads SUSPECT.
- **⛔ M2 measures trading intensity, not fraud.** Tokens flagged by slots had
  their 60 sampled transactions spread over a median **2.0h**; tokens with ≤ 1
  multi-tx slot, over **90h**. A busy token puts two trades in one 400ms slot
  as a matter of course.
- ⚠️ **The label is the wrong one for a wash detector.** Round-trip verdicts
  separate *sellable* from *not*. A wash-traded token can be sellable; that is
  the point of washing it. The §3 validation design could only ever confirm
  "dead vs alive", which the round trip already tells us.

An observation, **not a finding**, because it was seen in this sample: M1′ on its
own differs by arm, with a median of **0.128** for TRADEABLE and **0.496** for NOT
TRADEABLE. It is tested only on a fresh sample with a better label (§3d).

## 3d. PRE-COMMITTED 2026-09-19, before it runs: M1′ alone, against the wallet farm

**The label:** the wallet farm the universe seed found (`docs/UNIVERSE.md` §3a).
Those are members from the graduation ledger that share a ticker with another
tracked contract. That label was identified from holders, tickers and backing,
**independently of any volume measure**. The positive arm is those members; the
negative arm is TRADEABLE `token`-class members outside the farm signature,
seeded random (seed 20260920). n = min(30, farm size) per arm.

```
M1'_SUSPECT if dup_amount_share_tx >= 0.50
M1'_CLEAN   if dup_amount_share_tx <  0.25
otherwise   UNKNOWN          (and None -> UNKNOWN, never clean)
```

**Separates** only if the farm's SUSPECT rate's Wilson lower bound exceeds the
negative arm's upper bound, reported both ways. Anything less is a null result
and gets written here.

## 3e. ⛔ RESULT, 2026-09-19: M1′ against the wallet farm — NULL RESULT

`volintegrity.validate_farm(30)`, seed 20260920, exactly as §3d fixed it before it
ran. 30 farm members against 30 TRADEABLE `token` members outside the
farm signature, 60 transactions each, all read at version 1. 0 token(s)
gave no reading (UNKNOWN, never clean). Evidence: `data/findings/volintegrity_farm_2026-09-19.json`.

| arm | SUSPECT, all | SUSPECT, verdicts only | verdicts | median M1′ |
|---|---|---|---|---|
| FARM | **0/30 = 0.0% [0.0, 11.3]** | 0/29 = 0.0% [0.0, 11.7] | 29 clean, 1 unknown | 0.0 (n=30) |
| NOT FARM | 4/30 = 13.3% [5.3, 29.7] | 4/26 = 15.4% [6.2, 33.5] | 4 suspect, 22 clean, 4 unknown | 0.0707 (n=30) |

**Separates, all tokens: False. Separates, verdicts only: False.**

⛔ **M1′ does not detect this farm.** The farm's trades are, if anything, MORE varied in size than the control's (median M1′ 0.0 vs 0.0707).
An inference, not a measurement: that is consistent with how the farm looks in
§3a of `docs/UNIVERSE.md` (~2,000 holders, top ten at 5-10%). What it fakes is
**breadth and a market cap**, not **repeated trade sizes**, so a size-clustering
test is looking in the wrong place. The §3c observation
(M1′ median 0.128 vs 0.496 by round-trip arm) does not carry over to this label.

**What stands:** the farm is identified by the fields that found it — shared
ticker, graduation-sourced, `cap_backing_pct` far below the claimed cap
(`docs/UNIVERSE.md` §3a) — and **no volume measure in this file adds to that.**
B5 stays not a detector and not wired. Nothing here is quoted as a signal.

## 4. ⚠️ Two limits I hit, stated so nobody repeats them

1. **Keying on the stored `pair` gives stale pools.** An earlier run showed
   0.17 txns/hour for a token with a $1.65M real market cap, because the pool in
   our rows is the pool *as it was at observation*. **Key on the mint, or on the
   venue `chainfields.round_trip()` reports in `exit_venues`** — that is the pool
   Jupiter routes through *today*.
2. **The mint address is a weak handle for very large tokens.** BONK yielded
   only 8 parsed transactions, because most BONK swaps never touch the mint
   account. **For established tokens, key on the live pool instead.** The
   control in the table above is therefore weaker than it looks.

## 5. What this replaces

`vol_h1`, `vol_h24`, `vol_to_liq` and `vol_burst` are all Dexscreener
self-reports, and `vol_to_liq` divides one untrusted number by another. **Both
inputs are now known bad.** ⛔ **Any weight or gate keyed on them is suspect and
belongs on the re-run list in `docs/UNKILL.md`.**

**Replacement order:** M1 and M2 are cheap and computable today. Add
`volume_integrity` as a decision-point field alongside `exit_verdict` and
`holders`, and leave the reported volume fields in place, renamed to make clear
they are self-reported — nothing is ever deleted.

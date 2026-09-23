# PRECOMMIT: does all-pairs summing change recorded outcome verdicts

Written **2026-09-23 ~11:40Z, before any contract was re-queried.** Frank asked
for the verdict delta between the old single-pool read and all-pairs summing, and
called it the most important number in the report. So the rule that decides
"changed" is fixed here first.

## Why a verdict can change at all

`record_outcome` reads **one pair**, the `exit_pair` recorded at observation. Two
consequences already in the handoff:

- `journal.py:974` writes **`gone`** when two INDEXER lookups on that one pair
  fail, collapsing four different states into one word.
- **0 of 5,816** distinct pools in 24h of outcome rows are actually closed on
  chain, so `gone` is almost certainly not measuring pool closure.

A token that trades in thirty pools can have the recorded pair go quiet while the
token itself is liquid. All-pairs summing is the only way to tell.

## Sample, and it is a SAMPLE, stated before running

4,874 distinct contracts appear in the last 24h of outcome rows. Rule 18 forbids
batching the token endpoint (3 mints in one call returned 30 pairs TOTAL), so
this is one call per mint, and 4,874 paced calls is over 80 minutes. Two arms:

- **ARM A, every contract with a recorded `mult` >= 2x** (n=178 expected). This
  is where a verdict becomes a win claim, so it is the consequential arm.
- **ARM B, a seeded random sample of contracts whose recorded `status` is
  `gone`** (n=120 target, seed 20260923). This measures the `gone` error rate.

Both arms exceed the n=30 floor. Arm B carries a Wilson interval; arm A is a
census of its own population and does not need one.

## The verdict function, fixed now

From `allpairs.token(mint)`:

| new verdict | condition |
|---|---|
| `LOOKUP_FAILED` | `ok` is False. ⛔ Counted in NEITHER direction. Unknown is unknown. |
| `NO_PAIRS` | `ok` and `pair_count == 0` |
| `DUST` | `ok` and `pair_count >= 1` and `total_liq_usd < 1000` |
| `TRADING` | `ok` and `pair_count >= 1` and `total_liq_usd >= 1000` |

**A verdict CHANGED when, and only when:**

1. recorded `status == "gone"` and the new verdict is `TRADING` or `DUST`
   (the token still has pools; "gone" was a one-pool artifact), or
2. recorded `status` in (`dead`, `rugged`) and the new verdict is `TRADING`
   **and** the all-pairs total is at least **10x** the `liq` on the row (the
   single pool materially understated the token), or
3. the row's PHANTOM call flips under the pre-committed phantom rule
   (mcap > $1,000,000 with total liquidity < $1,000 across all pairs),
   ⛔ **except that a sample at `pair_count == 30` may never be called a
   phantom**, because 30 is Dexscreener's hard cap and the total is a floor.

**Not a change:** a different liquidity number alone. Rule 18 is explicit that a
correct sum of an overstating field is still an overstating field, good for
shape, venue spread and phantom detection, never for an exit price.

## What this cannot answer

- ⛔ **It does not revise any exit price.** `chainfields.round_trip()` already
  routes across every pool, so exit verdicts were never affected by the
  single-pool bug. The 2026-09-22 all-pairs re-run found exactly that: 12 of 15
  SHAPE labels changed, **0 exit verdicts changed**.
- ⚠️ Every total at `pair_count == 30` is a **floor** and is reported as one.
- ⚠️ This is a re-read at ~11:40Z of rows recorded across 24 hours, so a token
  can legitimately have died or revived in between. That direction of error is
  named in the result, not argued away.

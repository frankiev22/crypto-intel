# RULE_V2 — pre-committed 2026-09-10, before the first v2 entry

Written before any v2 entry exists. v1 stays pinned and untouched; the two
ledgers run in parallel over the same observation stream, same market, same
hours. Nothing below may be changed once the first entry is written; a change
means v3 and a new ledger.

## The rule

v2 is **v1 with the score band deleted and nothing else altered.**

    venue_type == "amm"
    exit_depth_usd >= $1,000              (quote side only, never liquidity.usd)
    can_mint is False AND can_freeze is False   (known AND revoked; unknown fails closed)
    NOT (sells_h1 == 0 and buys_h1 >= 10)       (a price never tested is not a price)

Deleted from v1: `70 <= score <= 99`, and the `score is None` rejection.

Nothing is loosened. Every fraud check in v1 is present in v2 at the same
constant. The depth floor, the authority requirement, the sell-side test, pair
identity, D1, and the sticky quarantine are all unchanged.

## PINNED_GATE_V2

    MIN_EXIT_DEPTH   1000.0
    TARGET_MULT      2.0
    MAX_HOLD_H       24.0
    NOTIONAL_USD     100.0
    MIN_N            30          (distinct tokens, not rows)
    SCORE_LO         None        (deliberately absent)
    SCORE_HI         None        (deliberately absent)

Drift check refuses every entry if any of these moves, same as v1.

## Epoch and storage

    epoch    2026-09-10
    ledger   data/paper/ledger_v2.jsonl      (its own hash chain, its own seq)

Rows from the two ledgers are **never merged and never compared row-wise.**
Only distribution to distribution, at matched n, with n and interval stated.

## How the comparison must be read — the part that is easy to get wrong

v1's entry set is a SUBSET of v2's: v2 is v1 minus a filter, so every v1 entry
also qualifies for v2. Comparing v1 to v2 is therefore comparing a set to its
own superset, and v2's distribution will be dragged toward v1's by the overlap.
That comparison understates the effect and cannot answer the question.

**The question is whether the tokens the score was REJECTING are worse than the
ones it was accepting.** So the comparison that matters is:

    A = entries qualifying under BOTH v1 and v2      (the score accepted these)
    B = entries qualifying under v2 but NOT v1       (the score rejected these)

If B's outcome distribution is no worse than A's, the score was destroying
information. If B is materially worse, the score was doing real work and the
230+ known false negatives were survivorship in the milestone ledger.

Every v2 entry records `also_qualifies_v1` at entry time so A and B are
separable forever without re-deriving anything.

## Pre-committed decision rule

Read at n >= 30 distinct tokens in BOTH A and B, not before, and stated with
Wilson intervals:

- **B's >=2x rate materially below A's** (A's lower bound above B's upper bound)
  -> the score was doing real work. Keep it. Report that v2 failed.
- **Intervals overlap** -> no evidence the score helped. It goes, on the
  grounds that a filter must justify its own existence, not be presumed useful.
- **B at or above A** -> the score was inverted, consistent with score 100
  being the worst band at 1.5% and the model's 0.9x lift.

⚠️ Expected null result. Base rate for >=2x is single-digit percent, so at
n=30 per arm the intervals will be wide and overlap is the likely outcome.
Overlap is not a licence to keep the score by default — the rule above says
what happens, and it was written before the data.

## What this is not

Not an appreciation claim. Removing a filter that was demonstrably suppressing
evidence does not make the surviving tokens go up. v2 is a cleaner measurement,
not a better signal.

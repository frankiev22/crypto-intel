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

---

# AMENDMENT 1 — 2026-09-11, arm B splits into B_high and B_low

**Made with 90 entries and ZERO closes on the v2 ledger.** No outcome has been
observed, so no result could have motivated this. That is the only condition
under which an analysis plan may be amended, and it is stated here rather than
edited into the text above, which stands as originally written.

## Why

Arm B was defined as "qualifies under v2 but not v1". I treated that as one
population. It is two, and they sit at opposite ends of the outcome
distribution. v1 rejects a token either for scoring **below** its 70-99 band or
for scoring exactly **100**, which is above it.

Measured post-epoch, distinct tokens, gate-applied >=3x:

| band | n | wins | rate | 95% CI | lift |
|---|---|---|---|---|---|
| 0-44 | 3,188 | 3 | 0.09% | [0.03, 0.28] | 0.40x |
| 45-69 | 2,385 | 4 | 0.17% | [0.07, 0.43] | 0.71x |
| 70-99 | 73 | 1 | 1.37% | [0.24, 7.36] | 5.82x |
| **100** | **307** | **6** | **1.95%** | **[0.90, 4.20]** | **8.31x** |
| all | 5,953 | 14 | 0.24% | [0.14, 0.39] | base |

Arm B's 73 entries are **53 scoring 100 and 20 scoring below 70**. Pooling them
would have averaged the best-performing bucket with the worst and reported a
number describing neither.

## The correction this carries

The project has been working from "score 100 is our worst band at 1.5%, and the
model's lift was 0.9x". **Post-epoch that is not what the data says.** 100 is
the best-performing band by rate and by lift, and the score as a whole is not
inert: 0-69 sits below the base rate and 70+ sits well above it.

The old figure is not necessarily wrong — it is pre-epoch, and the 74,281
excluded rows are excluded for cause. But it must not be quoted as current, and
v1's exclusion of score 100 was chosen on the strength of it.

**What is established:** 100 beats 0-69. Its lower bound (0.90%) clears the
45-69 upper bound (0.43%).
**What is NOT established:** that 100 beats 70-99. Those intervals overlap
heavily, on n=73 with a single win.

## v1 is NOT being changed

v1 keeps SCORE_HI=99 and stays pinned. It is the control, and a control that
gets corrected mid-run is not a control. `RULE_V1` encodes `score70-99` in its
own name; changing it produces a different rule, not a fixed one.

The exclusion costs v1 nothing that is being lost, because **v2 already enters
every score-100 token** — 53 of them so far, in B_high. The comparison that
answers the question is B_high vs A, and it is already running.

## Reading, unchanged in discipline

At n >= 30 **closed** distinct tokens per arm, Wilson intervals, stated with n:

- **B_high vs A** — does the band's upper exclusion cost anything? This is the
  question P1 raised and it is now directly measurable.
- **B_low vs A** — was the lower bound doing real work? The lift table predicts
  yes; the pre-committed rule says the intervals decide, not the prediction.

Entries are not closes. All three arms are at zero closes today.

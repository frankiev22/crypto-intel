# Surfaced grade — pre-committed 2026-09-15, before measuring its effect

## Why

PTN (`PTNzAfFAB4LvoUQEUUGrFMyUoRLExMYjH6CcfyQfsVP`) surfaced at 20:12Z on 9/14 as
**"scored 100"** with mint authority and freeze authority both LIVE. The deployer
could print supply into a buyer's bid and stop them selling. `paper.qualifies()`
has refused live or unknown authority since 9/07. The score path never read
authorities at all, because they were measured to have near-zero variance as a
feature (227 of 228 revoked). That is correct for a feature and wrong for what
surfaces. Frank acts on what surfaces. A 100 beside a live mint authority is the
most dangerous single output this system can produce.

## The rule

`score` is **not changed**. It is the scorer's output. v1's pinned gate reads it
(SCORE_LO 70 / SCORE_HI 99), and v2's B_high/B_low split reads it. Rewriting it
for some rows mid-run would store a policy value in a field both ledgers read,
which is the substitution bug this project has already had.

What surfaces is a separate field, `grade`:

| authorities at observation | grade | label |
|---|---|---|
| mint OR freeze authority **live** | **0** | `TRAP - authority live` |
| either one **unknown** (never checked, or the check failed) | **min(score, 69)** | `authorities unverified` |
| both revoked | score | none |

69 is `PASS_SCORE - 1`, so an unverified contract can never "pass the launch
filter". It is derived from the existing constant, not tuned.

Every surface reads `grade`, never `score`:
- the Discord alert list in `collect.scan_stage`
- the alert embed title
- the scanner's printed output
- the skill file's `scanner-hit` rule (85+)

`check.py` already answers trap / clean / can't tell and is unchanged.

## What it cannot change

**No ledger entry.** v1 and v2 both refuse live and unknown authority before they
read the score, so every row whose grade differs from its score was already
refused. This is verified by replaying `paper.qualifies` and `paperv2.qualifies`
over post-epoch observations twice, once as recorded and once with `score`
replaced by `grade`. The decisions must be identical row for row. If they are
not, this rule is wrong and does not ship.

## Measured after this file was written

This file was committed in 57e4608 before the replay below ran. Post-epoch
observations, 2026-09-07 → 2026-09-15 05:18Z: **10,469**.

**The claim holds.** Both entry rules were replayed over every observation with
`score` replaced by `grade`. v1 qualifies 137 rows and v2 qualifies 709, and
**0 decisions change** in either ledger.

| score band | rows / tokens | authority live | unknown | revoked | still in band after grade |
|---|---|---|---|---|---|
| ≥ 70 | 684 / 663 | 2 / 2 | 56 / 56 | 626 / 607 | 626 / 607 |
| ≥ 85 | 582 / 562 | 2 / 2 | 50 / 50 | 530 / 512 | 530 / 512 |

That means 58 of the 684 rows at 70+ (58 tokens) no longer surface as a pass.
Two had a live authority and 56 were unverified. Why the 56 were unverified:

| reason | rows |
|---|---|
| no reason recorded (rows from before `authorities_skipped` existed, 2026-09-10) | 49 |
| lookup failed (URLError) | 3 |
| exit depth below the floor | 2 |
| no sell side | 2 |

**Score 85+ with a live authority, post-epoch: two tokens.** Both scored 100 with
mint AND freeze authority live, and both are now grade 0:
- QUBT (`QUBTAD8C9bMU9LvmMNgKPhrmBGbHvxpu6vfWQtThxxw`) at 09-09 21:18Z
- PTN (`PTNzAfFAB4LvoUQEUUGrFMyUoRLExMYjH6CcfyQfsVP`) at 09-14 20:07Z

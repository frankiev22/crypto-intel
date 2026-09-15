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

To be filled in from post-epoch observations:
- how many scored ≥70, split by authority state
- how many alerts the rule would have suppressed
- how many 85+ scanner hits carried a live authority

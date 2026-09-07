# More than half of every win is contaminated — and the mechanism is not what we thought

2026-09-07, P0. **The contamination is real and the scale is right. The
diagnosis was wrong, and the fix that follows from it is different.**

## ⚠️ Correction to the diagnosis

The finding was read as a **shared reference pool** — many tokens priced off one
pool, i.e. a pair-identity failure. That is not what the data shows.

If it were one shared pool, the reported liquidity would repeat *across* symbols.
It does not. Every value maps to exactly one symbol:

    $1,261,984.63  x5   CHAD only
    $1,250,076.76  x4   XDC only
    $1,274,978.79  x4   PONS only
    $1,203,561.98  x3   OGCALL only

The repeats are the *same token scored at several horizons*. 63 distinct entry
pairs, 53 distinct symbols, 63 distinct liquidity values.

**What it actually is: the template attack, already documented in
`TEMPLATE_ATTACK.md`.** Of the 141 band rows carrying a measured exit depth,
every single one shows the same ratio to five decimal places:

| symbol | reported liq | measured exit depth | depth/liq | overstatement |
|---|---:|---:|---:|---:|
| CHAD | $1,261,985 | $10,045.28 | 0.00796 | 125.6x |
| GME | $1,294,731 | $10,305.28 | 0.00796 | 125.6x |
| JERSEY | $1,257,511 | $10,008.89 | 0.00796 | 125.6x |
| ZODL | $1,263,969 | $10,061.04 | 0.00796 | 125.6x |
| cTERX | $1,265,830 | $10,076.79 | 0.00796 | 125.6x |
| S500 | $1,271,164 | $10,116.19 | 0.00796 | 125.7x |

And at entry: **liq/fdv median 1.0020** (the entire supply *is* the pool), **56
of 63 had zero sells against ≥10 buys**, and **56 of 63 were already flagged
`template_suspect`** by `plausibility.assess()` at the time.

CHAD, ZODL and SUNCOIN are literally the pools in the `TEMPLATE_ATTACK.md`
table. We identified this class on 2026-09-05, declined to filter on it because
it was unvalidated — and it has been supplying the win record ever since.

**The scale stands: 85 of 165 realizable 3x+ wins (51.5%) are in this band.**

## Why the depth floor alone does not catch it

These pools hold **~$10,045 of real quote side**. That clears a $100 exit floor
honestly — you genuinely could exit $100. So depth cannot disqualify them.

**Silence can.** A pool with buys and no sells has never had its price tested by
anyone trying to leave. The price is set by a curve with no counterparty.

So the gate gained a `sell_side` check: fail when `sells_h24 < 1` and
`buys_h24 >= 10`. Only applied where sell data was actually recorded — an absent
count is not evidence of silence. Verified: the template case fails, a normal
pool with 12 sells passes, a genuinely quiet pool with 3 buys passes, and a row
with no data recorded passes.

## The gate, which is the real deliverable

Four headline results have now evaporated: the 718x, the liquidity gradient, the
low-score inversion, and now half the win record. The checks mostly *existed*;
they were a checklist somebody had to remember, and remembering caught it about
half the time.

`journal.verify_win()` is now a **gate**, applied inside `record_outcome()`
before any row is written, with each check recorded **by name** on the row in
`win_checks_failed`:

    pair_identity     exit pair == entry pair, and no cross_pair_fallback
    depth_measured    the quote side was actually seen
    depth_floor       and it clears the exit floor
    sell_side         somebody has sold; the price has been tested
    source_agreement  the two sources agree, where checked
    plausibility      within the multiple ceiling
    elapsed_recorded  actual_elapsed_h exists
    alive             the token is still there

Adding a check here applies it everywhere at once. `journal.verified_outcomes()`
is the denominator any win claim must use.

## Pair identity was still unguarded, and is now fixed

Separately from the above — and it was a real hole. `sources.dexscreener_pair()`
did `return pairs[0]` with **no check that the returned `pairAddress` was the
one requested**. The existing `cross_pair_fallback` guard only ever covered the
*fallback* branch; all 141 band rows came through the **primary** branch with no
reasons recorded at all.

Fixed: the response list is now **searched for the requested address** (a
multi-pair response containing ours is fine — we just have to pick ours), and a
genuine mismatch returns `None` and is logged to `sources.LAST_PAIR_MISMATCH`.
`exit_pair` is now recorded on every outcome row, so identity is auditable from
the data rather than trusted from the code. Live-tested on 8 pairs: 8/8 matched,
which does not clear the path — it only says the endpoint behaves when the pair
is healthy.

## What survives: zero

**All-time verified wins: 0 of 165.**

- **0 of 76,020 outcome rows carry an `exit_pair`.** The field did not exist
  before today, the pools are delisted, and it cannot be reconstructed — not
  from the journal, not from the API. **Historical pair identity is permanently
  unverifiable.**
- 34 of 165 wins pass every other check. **131 fail on `depth_measured`.**
- Of the 34, **16 are in the template band** and would now also fail `sell_side`.

Per instruction, unverifiable rows are **excluded, not flagged**:
`journal.outcomes()` sets `pair_identity_verifiable = False` on every legacy row
and `verified_outcomes()` drops them. Nothing is deleted; the rows stay.

## Did widening `pending()` cause the rise? Not established

| | in band | rate | 95% CI | n |
|---|---:|---:|---|---:|
| before 09-06 16:30Z | 80 of 159 | 50.3% | [42.6%, 58.0%] | 159 |
| after | 5 of 6 | 83.3% | [43.6%, 97.0%] | **6** |

**The intervals overlap and n=6 is far below `MIN_N=30`. Refuse to conclude.**

A mechanism does exist — a wider window scores older rows, and older rows are
likelier to be delisted or migrated. But the defect is the template population
and pair identity in `dexscreener_pair`, both orthogonal to the queue window.
**Re-test once n≥30 rows have accumulated after the change.** The aged-out
losses the widening fixed were real and measured (4,203 at 24h); reverting on
n=6 would trade a measured fix for an unmeasured suspicion.

## Noted for the record

The reported jump from 3 wins to 16 was attributed to the follow-through fix
working. That attribution was wrong — most of the jump was template
contamination. It has been corrected with Frank directly, and is recorded here.

## Also fixed

**`NameError: verbose` in the news check.** It killed the freshness check on
every pass from 2026-09-06 17:11Z. Cause: I inserted the call after the
source-health block, which lives in `main()` — a function with no `verbose`
parameter — not in `scan_stage()` as I assumed. Now passes `True` literally.
The irony is exact: a silent failure in the check built to catch silent
failures.

**The 168h horizon should be retired.** It is not newly dead — it has always
been this bad:

| window | rows | resolved | rate |
|---|---:|---:|---:|
| last 24h | 2,174 | 108 | 5.0% |
| last 3d | 4,683 | 242 | 5.2% |
| all time | 9,625 | 368 | **3.8%** |

Resolution by horizon over 3 days: **1h 99.9%, 6h 99.9%, 24h 36.8%, 168h 5.2%.**
Dexscreener stops indexing pairs between 6h and 24h, and by 168h almost nothing
resolves. **0 of 110 pairs have a ≥3x row only at 168h** — it contributes
nothing exclusive — while costing 12.1% of the outcome budget.

**24h is the longest trustworthy horizon, and it is already degraded at 36.8%.**

# PAPER_V3 — pre-committed 2026-09-17, before the first v3 entry exists

**Written before any v3 entry, any v3 code, and any v3 result. Nothing below may
be changed once the first entry is written. A change means v4 and a new ledger.**

⛔ **This file is committed on its own, before the module that implements it.**

---

## ⛔ Naming: this is v3, not v2, and the reason matters

**`v2` is already taken.** `paperv2.py` / `ledger_v2.jsonl` is RULE_V2 — v1 with
the score band deleted — an A/B on the *filter*. It is not a pricing change.

⛔ **v1 and v2 are BOTH priced on the poisoned field** (`entry_price_usd` from
the Dexscreener mid, gated on `liq` / `exit_depth_usd`). **Both are quarantined
by this file. v3 is the first ledger priced on what a trade would actually
return.**

## 1. What was wrong, stated precisely

v1 records `notional_usd: 100.0` on every entry and then **never applies it**.
The multiple is `exit_price_usd / entry_price_usd` — a **mid-to-mid price ratio
with zero price impact**. Size is recorded and ignored.

⭐ **So a "win" is a price nobody could have obtained at any size.** That is why
0 of the all-time wins survive an exit-integrity check: **the exits were
fictional, not merely optimistic.**

⚠️ **The measured scale of the error, from `docs/LIQUIDITY.md` §12:** across 18
random contracts, stored liquidity claimed **$7,467,996,005** against **$1.68**
actually recoverable at a $100 probe. And from §10, a token can cost 3.46% at $10
and have **no sell route at all** at $500.

## 2. ⛔ Quarantine

- `data/paper/ledger.jsonl` (v1) — **frozen. Append nothing.**
- `data/paper/ledger_v2.jsonl` (RULE_V2) — **frozen. Append nothing.**
- **Neither is deleted** (standing rule 8) and **neither is merged into v3.**
- ⛔ **Stop quoting their numbers.** Specifically retired: **−$3,099 / −$40.78
  per round trip**, and its re-derivation **−$2,495 by multiple / −$4,168
  realizable over 86 closes**. Both are computed on fictional fills. **The
  honest status of v1 and v2 is "no usable P&L", not a loss figure.**

## 3. The rule — frozen

**Entry condition** (all must hold, evaluated at the observation that triggers):

```
venue_type == "amm"
exit_verdict == "TRADEABLE"          from chainfields.round_trip(mint, 100)
can_mint is False AND can_freeze is False     unknown fails closed
NOT (sells_h1 == 0 and buys_h1 >= 10)         a price never tested is not a price
holders >= 100                                 chainfields.holder_count, deduped
holders_truncated is False                     a bound is not a count
```

⚠️ **`holders >= 100` is an unvalidated candidate** (`docs/TRUSTED_FIELDS.md`
§1), and it is pre-committed here **as part of the rule** precisely so it gets
tested rather than tuned. If it is wrong, v3 fails and that is a result.

**Exit condition** — whichever comes first:

```
TARGET_MULT reached      realizable multiple >= 2.0   (not mid-price)
MAX_HOLD_H exceeded      24.0 hours
EXIT_VERDICT degrades    round_trip returns TOTAL_LOSS / NO_SELL_ROUTE /
                         NO_BUY_ROUTE  -> close immediately at whatever it returns
```

⭐ **The third is new and is the whole point.** v1 could not detect that an exit
had stopped existing. v3 closes on it and **records the loss.**

## 4. ⭐ Pricing — every fill is a real quote

**Entry fill** = `chainfields.round_trip(mint, NOTIONAL_USD)`, using the **buy
leg**: the token quantity $100 actually purchases, including impact.

**Exit fill** = a **sell quote for exactly that token quantity**, in USD.

```
realizable_multiple = exit_usd_received / NOTIONAL_USD
```

⛔ **No mid price appears anywhere in the P&L.** A fill that cannot be quoted is
not a fill: if no route exists at exit, the position closes at **$0 recovered**
and is recorded as a total loss, **not skipped.**

**Recorded on every fill, entry and exit:**

| field | why |
|---|---|
| `usd_in` / `usd_out` | the actual money |
| `token_qty` | what $100 bought, at impact |
| `price_impact_pct` | ⭐ **the number that was invisible and killed the edge** |
| `route_venues` | which AMMs the quote traversed |
| `quote_ts` | when, to the second |
| `verdict` | TRADEABLE / COSTLY / TOTAL_LOSS / NO_*_ROUTE |

## 5. ⭐ Size-aware by default

Frank's live clips are **$100**. That is the simulated size and the only one the
P&L uses.

**At entry and at exit, additionally record a quote at $250 and $500** —
recorded, never traded. This gives the depth cliff **as measured at the moment of
the trade**, instead of a remembered one.

```
SIZES_RECORDED = (100, 250, 500)
SIZE_TRADED    = 100
```

⚠️ Cost: 2 quotes per size per side = **12 quotes per completed position.** At
~1.1 req/s that is ~11 seconds, and against the 25M monthly allowance it is
nothing (`docs/LIQUIDITY.md` §9).

## 6. PINNED_GATE_V3 — drift refuses every entry

```
NOTIONAL_USD        100.0
TARGET_MULT         2.0
MAX_HOLD_H          24.0
MIN_HOLDERS         100
ENTRY_VERDICT       "TRADEABLE"
SIZES_RECORDED      (100, 250, 500)
MIN_N               30        distinct contracts, not rows
epoch               2026-09-17
ledger              data/paper/ledger_v3.jsonl   own hash chain, own seq
```

## 7. ⭐ The falsifiable claim

**H1: entries selected by this rule, priced at realizable fills, produce a
positive median realizable multiple over n ≥ 30 distinct contracts.**

**v3 is reported as a failure if any of these hold:**

1. **Median realizable multiple ≤ 1.0** at n ≥ 30. The rule does not pay.
2. **The Wilson interval on the win rate includes the break-even rate** implied
   by TARGET_MULT and the observed loss distribution.
3. ⭐ **Fewer than 30 contracts pass the entry gate in 60 days.** If
   `TRADEABLE` + `holders >= 100` is that rare, the rule is unusable regardless
   of whether it would have paid.
4. **Median entry `price_impact_pct` at $100 exceeds 10%.** Then the edge is
   eaten by the fill and the strategy is a fee generator.

⛔ **No post-hoc exclusions. Every close is reported** — late closes in and out,
per standing rule 7. **A position whose exit route vanished is a loss, not a
void.** The only `void` permitted is a *recording* failure (quote API down at
exit), which must be logged with its reason and reported separately.

## 8. ⭐ Why this is the asset worth building

**Almost everyone in this space lies about their track record**, and the lie is
cheap because a screenshot of a mid-price multiple costs nothing to fabricate.

**A timestamped, hash-chained ledger where every fill is a real quote at a stated
size, including every loss, cannot be faked retroactively.** That is rare, and it
is the one thing in this repo with a clear route to being worth money.

⛔ **It only counts if it runs forward, cleanly, from a fixed epoch.** Backfilling
is impossible by construction — `round_trip()` measures *now* and cannot
reconstruct a past exit. **Every day the collector is down is a day of record
that cannot be bought back at any price.**

## 9. ⛔ Hard dependency: collection must be alive

**Nothing has collected since 2026-09-15 05:07:59 UTC.** v3 cannot accumulate a
single row until that is fixed, and this is the gating item, not a footnote.

**Minimum to restart** (`docs/TRACKER_SCOPING.md` §5a):

1. Windows Task Scheduler calling `collect.py` directly — the Claude desktop task
   is dead because the sandbox lost its drive mount on the 9/15 reboot, and
   GitHub Actions is out of free minutes.
2. ⛔ **`CRYPTO_ORIGIN=scheduled` must be set**, or every beat logs as `manual`
   and is never counted as unattended.
3. **Verify by observing an unattended run** (standing rule 10), not by reading
   config. The desktop task fired hourly for two days while collecting nothing.
4. **Liveness check that means something:** newest `ts` in `data/observations/`,
   or `last_unattended_at` in `data/liveness.json`.

⚠️ **This is a Task Scheduler entry, not a migration, and needs no spend.**

---

## 10. ⭐ SCHEDULED, 2026-09-18 — and what had to be true first

⛔ **Until today nothing called this module.** 71 passing tests, a frozen rule, a
live hand-run entry, and `collect.py` did not reference `paperv3` anywhere. The
ledger recorded nothing automatically for the entire time it existed. **Passing
tests are not evidence that a module is in the system** — the same pattern as
`chainfields` (imported only by paperv3) and `devwallet` (imported by nothing).

⚠️ **And wiring it in alone would have produced a gate that could never pass.**
`holders` was on **zero of the last 400 observation rows**, and RULE_V3 refuses
an unknown float by design. v3 would have entered nothing, for ever, and read
exactly like a quiet market. Three things were required together:

1. **`holders` on the row.** Fetched at the decision point in `scanner.py` for
   rows that already cleared every free condition — measured **92 of 1,003 rows
   over three days**, roughly 7 a pass. Helius DAS, not Jupiter.
2. **`holders` in `journal.record()`'s whitelist**, or it is computed and does
   not exist. That whitelist has eaten five fields.
3. **v3 entry inside the enrichment loop**, beside v1 and v2 — same row, same
   pass, three filters. ⛔ Moving it to a later stage would turn a forward log
   into a retrospective one, and every retrospective finding in this project has
   died of leakage. It is also standing rule 14: conditions opened
   simultaneously, never in sequence.

**Cost per pass, stated:** ~7 holder counts; one round trip (2 Jupiter calls)
for each row clearing `holders>=100`; and **an entry costs three round trips,
not one** — the $100 gate quote plus shadow quotes at $250 and $500, six Jupiter
calls, against a 55/min bucket and a 540s scan budget. Ceilings are
`CRYPTO_HOLDER_BUDGET` (25) and `CRYPTO_V3_QUOTE_BUDGET` (15), and both record
what they deferred rather than skipping silently.

### ⛔ The liveness thresholds, pre-committed here rather than invented

`paperv3.sweep` is a **schedule** event: it runs every pass, so it carries a real
**12h** threshold matching `paper.sweep`, which shares the stage.

`paperv3.open` and `paperv3.close` are **market** events. RULE_V3 is strictly
stricter than v1 and its entry rate **has never been observed**, because nothing
ever ran it. Any staleness bar set today would be invented, and an alarm that
fires when nothing is wrong is the failure this repo documented and shipped
again on the morning of 2026-09-18.

⭐ **So they are declared `unmetered`: counted and printed, never alarmed.** This
is not a way to silence a component — the verdict appears in every
`python liveness.py` line with the reason attached.

**The threshold gets set from data at whichever comes first:**

- **30 v3 entries**, or
- **14 days of unattended collection** from the first scheduled pass that runs
  this code.

⛔ **Written before the data, so it cannot be moved to fit a result.** If the
observed rate makes a useful threshold impossible — for example if entries are
so rare that any bar is either always-firing or never-firing — that is a finding
about RULE_V3, and it gets recorded as one rather than being tuned away.

### Verified, not assumed

`test_v3wiring.py` drives the real `scanner.scan()` loop with the network stubbed
and asserts a **ledger row** comes out: the entry lands, the refused row records
why, the per-pass refusal tally reaches the coverage row, and the sweep closes
the position at **2.5x** against a live sell quote for the exact holding. **32
checks on the output, not on whether the code ran.**

# Paper trader v3 — fills that could actually have happened

**2026-09-17. Design. The frozen rules live in `PRECOMMIT_paper_v3.md`, which was
committed before this file and before any code.**

> *"then we can actually get the paper trader working properly"* — Frank

---

## 1. ⭐ Why the old log was worthless, in one line of code

```python
# paper.py — v1
"notional_usd": NOTIONAL_USD,        # recorded on every entry
...
mult = price / entry["entry_price_usd"]      # and never used
```

**`notional_usd` is written to every row and never applied.** The multiple is a
**mid-to-mid price ratio with zero price impact**. Size is recorded and ignored.

⭐ **So a "win" is a price nobody could have obtained at any size.** That is the
mechanism behind "0 of the all-time wins are verifiable" — the exits were
**fictional, not merely optimistic.** It was never a measurement that came out
badly; it was not a measurement.

**The scale of the gap, measured** (`LIQUIDITY.md` §12): across 18 random
contracts, stored liquidity claimed **$7,467,996,005** against **$1.68**
actually recoverable at a $100 probe.

## 2. ⛔ Quarantine — enforced in code, not in prose

| ledger | rows | state |
|---|---:|---|
| `data/paper/ledger.jsonl` (v1) | 409 | **frozen** |
| `data/paper/ledger_v2.jsonl` (RULE_V2) | 633 | **frozen** |

`paper._refuse_if_quarantined()` and the same in `paperv2` **raise on append**.
Reads and chain verification still work — the modules are still the correct
implementation of their rules and are still how those ledgers are audited.

⭐ **The guard keys on the ledger PATH, not the module.** The quarantine is a
property of the poisoned file on disk. My first version keyed on the module and
broke every test that redirects `LEDGER` to a temp path — which is exactly what
those tests should do. **Path-based: real ledgers refuse, temp ledgers work,
26/26 and 61/61 tests pass.**

⚠️ **RULE_V2 is frozen too, and that is the less obvious one.** v2 changed the
*filter*, not the pricing, so its A/B sits on the same fictional exits and cannot
be read either.

**Nothing is deleted** (standing rule 8), nothing is merged into v3.

### ⛔ Numbers retired by this

- **−$3,099 / −$40.78 per round trip** (quoted to Frank, walked back)
- **−$2,495 by multiple / −$4,168 realizable over 86 closes** (my re-derivation)

**Both are computed on fictional fills.** The honest status of v1 and v2 is
**"no usable P&L"** — not a loss figure. A wrong loss is still a fabrication.

## 3. How a v3 fill works

```
ENTRY   round_trip(mint, 100)  ->  buy leg gives token_qty for $100, at impact
        record: usd_in=100, token_qty, price_impact_pct, route_venues, quote_ts

EXIT    sell quote for exactly token_qty  ->  usd_out
        realizable_multiple = usd_out / 100
```

⛔ **No mid price appears anywhere in the P&L.** And a fill that cannot be quoted
is not a fill: **if no route exists at exit, the position closes at $0 recovered
and is recorded as a total loss — never skipped, never voided.**

⭐ **The third exit condition is the one v1 could not express:** close
immediately when `round_trip` returns `TOTAL_LOSS`, `NO_SELL_ROUTE` or
`NO_BUY_ROUTE`. **v1 had no way to notice that an exit had stopped existing.**

## 4. ⭐ Size-aware, because the cliff is the risk

$100 is traded. **$250 and $500 are quoted and recorded at both ends, never
traded.** That captures the depth cliff **as it was at the moment of the trade**,
instead of quoting a remembered one.

The reason, measured (`LIQUIDITY.md` §10):

```
sym              $10         $100         $500
ROCK           8.28%        8.51%        9.51%
WOFI           3.46%       11.63%  NO_SELL_ROUTE
```

**At $10 WOFI looks like the better token. At $500 it cannot be sold.** A ledger
that records only one size cannot tell those apart, and the difference is the
entire risk.

**Cost:** 12 quotes per completed position (2 legs × 3 sizes × 2 ends) ≈ 11
seconds at the measured ~1.1 req/s. Against the 25M monthly allowance this is
noise — total usage so far is **0.00038%**.

## 5. What v3 produces

Per closed position: `usd_in`, `usd_out`, `realizable_multiple`,
`price_impact_pct` at entry and exit, the $250/$500 shadow quotes at both ends,
`route_venues`, `holders` at entry, `exit_reason`, and hash-chain `prev`/`seq`.

**Reported at n ≥ 30 distinct contracts**, with Wilson intervals, late closes
both ways, and **every loss included** — per `PRECOMMIT_paper_v3.md` §7, which
also names the four conditions under which v3 is declared a failure.

⚠️ **One of those failure conditions is worth surfacing:** if fewer than 30
contracts pass `TRADEABLE` + `holders >= 100` in 60 days, **the rule is unusable
regardless of whether it would have paid.** Given that `holders >= 100` kept only
12 of 15 exitable contracts in the sample that produced it, **this is a live
risk, not a formality.**

## 6. ⭐ Why this is the asset

**Almost everyone in this space lies about their track record**, and the lie is
cheap: a screenshot of a mid-price multiple costs nothing to fabricate — **which
is exactly what v1 was accidentally producing.**

A **timestamped, hash-chained ledger where every fill is a real quote at a stated
size, including every loss and every position whose exit route vanished**, cannot
be faked retroactively. **That is rare, and it is the one thing in this repo with
a clear route to being worth money.**

⛔ **It only counts if it runs forward, cleanly, from a fixed epoch.**
Backfilling is impossible **by construction** — `round_trip()` measures *now* and
cannot reconstruct a past exit. There is no version of this that can be made up
later, which is precisely why it is credible and precisely why the clock matters.

## 7. ⛔ The gating dependency: collection is dead

**Nothing has collected since 2026-09-15 05:07:59 UTC.** v3 cannot accumulate a
single row until that is fixed. **Every day down is a day of record that cannot
be bought back at any price.**

**Minimum to restart — a Task Scheduler entry, not a migration, and no spend:**

1. **Windows Task Scheduler → `collect.py` directly.** The Claude desktop task
   died when the sandbox lost its drive mount on the 9/15 reboot; GitHub Actions
   is out of free minutes (~$31/mo to resume, or $0 if the repo goes public).
2. ⛔ **`CRYPTO_ORIGIN=scheduled` must be set**, or every beat logs as `manual`
   and is never counted as unattended.
3. **Verify by observing an unattended run**, not by reading config (standing
   rule 10) — **the desktop task fired hourly for two days while collecting
   nothing.**
4. **Liveness that means something:** newest `ts` in `data/observations/`, or
   `last_unattended_at` in `data/liveness.json`.

## 8. Build order

1. ✅ `PRECOMMIT_paper_v3.md` — committed first, before any code.
2. ✅ Quarantine v1 and v2 in code; tests still pass.
3. ⬜ `paperv3.py` — entry/exit on real quotes, own hash chain,
   `data/paper/ledger_v3.jsonl`, `PINNED_GATE_V3` drift check.
4. ⬜ `test_paperv3.py` — the $0-recovered close, the no-route exit, the drift
   refusal, and **that no mid price can reach the P&L**.
5. ⬜ Restart collection (§7). **Until this lands, v3 records nothing** and the
   epoch in the pre-commit is aspirational.

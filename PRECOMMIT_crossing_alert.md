# PRE-COMMIT: the crossing alert lane

**Written 2026-09-23 before any crossing was evaluated against it.** Standing
rule 6, and Frank's own note the same day: *"you pre-committed the verdict rule
to a file before querying, and that is why the 1.7% result is trustworthy. Do
that on every experiment from now on. It is the direct fix for the
score-gated-evidence bug class."*

---

## 1. The problem this exists to fix

Measured over the 24h to 2026-09-23 (`data/findings/DAILY_2026-09-23.md`):

| | |
|---|---|
| crossings of `mcap_1m` or `mcap_5m` | **61**, on **34 distinct contracts** |
| crossing pings fired | ⛔ **ZERO** |
| crossings with **under $1,000** of exit depth measured AT the crossing | **45 of 60 (75.0%)**, median depth **$0** |
| crossings that **cleared** $1,000 and were still never announced | ⛔ **15** |

There was no crossing alert lane at all. `outcome-win` fires on a multiple;
nothing fires on a market-cap crossing. So the 45 were correctly silent **by
accident**, and the 15 were incorrectly silent for the same reason.

⭐ **The point of the lane is the silence as much as the alert.** A crossing
detector that fires on all 61 is worse than nothing: rule 4 says never fire on an
unverified crossing, because Frank will act on it.

---

## 2. The rule, fixed now

A crossing is evaluated **once per (contract, tier), ever** - that is already
guaranteed by `milestones.claim()`, which is an `O_EXCL` file create, not a
convention.

**Trigger:** a NEW claim of `mcap_1m` or `mcap_5m`.
⛔ `mcap_100k` and `mcap_200k` never alert. They are recorded and stay silent.

**Then exactly one of three outcomes, decided on `exit_depth_at_crossing`, the
quote-side depth measured in the SAME call that produced the crossing:**

| depth at crossing | action | why |
|---|---|---|
| **>= $1,000** | ⭐ **ALERT** | there is a market on the other side, at a size that matters at Frank's $100 clip |
| **< $1,000** | **SILENT_THIN** | recorded, counted, never pinged. 75% of crossings land here |
| **unknown** (`None`, or `depth_unmeasured_at_crossing` true) | ⛔ **SILENT_UNMEASURED** | rule 5: not checked must never read as passed. This is the `authority_live=None` shape and it stays silent |

⛔ **$1,000 is the number, and it is the one already pre-committed elsewhere** -
the phantom rule in standing rule 18 uses exactly this floor for
"mcap > $1,000,000 on total liquidity < $1,000 is a ghost". It is not a new dial
and it is not tuned to today's data.

⚠️ **The depth is Dexscreener's quote side, NOT a sell quote.** A crossing that
clears this bar has not been round-tripped. The alert must say so in words, the
same way `outcome-win` had to stop saying "realizable" (2026-09-19).

---

## 3. Keying, dedupe and budget, all pre-committed

- **Key: the contract address, with no fallback to the ticker.** Standing rule 2.
  Six BASKET contracts collapsed into one findings class on 2026-09-20 and
  everything after the first went silent; `test_tickerkey.py` now fails at the
  AST level on a ticker key, and this lane is inside its scope.
- **Dedupe: the `O_EXCL` claim.** A second pass that sees the same contract at
  the same tier does not reach the alert at all, because `claim()` returns False.
- **Lane: `crossing`, its own budget of 3 pings/hour.** Lanes are independent, so
  a crossing storm cannot exhaust the lane a confirmed outcome arrives in, and a
  flood of scanner hits cannot silence a crossing. 15 qualifying crossings in 24h
  is **0.6/hour**, so 3 is 5x headroom and still bounds a burst.
- **Significance: `depth_usd / 1000.0`.** A crossing on $3,000 of depth scores
  3.0, which is deliberately the same number a 3x outcome scores, so
  `SIGNIFICANCE_ALWAYS = 3.0` treats them alike and the two lanes rank on a
  comparable scale. A $1,000 crossing scores 1.0 and can be rationed.

---

## 4. What would make this rule WRONG, stated before it runs

- ⛔ If most $1,000+ crossings turn out not to be sellable on a live round trip,
  the bar is measuring the wrong thing and must move to a quote, not be raised.
  The honest expectation is that **some of them are not**: the base rate for a
  $1m token a month later is **9.0% [7.1, 11.4]** still round-trippable
  (`analysis/gorilla_archive/control_roundtrip.py`), and 85% of $1M/$5M
  crossings failed realizability at the crossing on the broader screen.
- ⛔ If SILENT_UNMEASURED is a large share, the lane is mostly reporting our own
  measurement gaps rather than the market, and the fix is upstream in the depth
  read, not here.
- ⭐ **Both are checkable from the row**, because every decision is recorded with
  its action and its depth, including the silent ones. **A lane that only records
  what it announced cannot be audited.**

## 5. What this lane does NOT claim

It does not predict that a crossing will run further. Marino applies to anything
forward-looking. **A crossing that has already happened, with the depth that
existed at the moment it happened, is description.** The alert says what
happened and what was measured, and stops.

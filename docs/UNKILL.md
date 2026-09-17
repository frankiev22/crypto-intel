# Every killed strategy, what killed it, and whether the killer survives

**2026-09-17.**

> *"Unkill all of the strategies that you previously killed. We had incorrect
> information... I promise you there will be patterns and we will be able to
> figure it out. We just need the information to be correct."* — Frank

⭐ **He is more right than I first credited, and the reason is worse than "some
numbers were wrong".**

---

## ⛔ The finding that reframes all of this: the LABELS are poisoned, not just the features

Until 2026-09-11, `journal._exit_liquidity_ok()` contained:

```python
judged = exit_depth if exit_depth is not None else liq
```

`exit_depth_usd` is missing or zero on **76%** of rows, so on most rows the
`realizable` flag — **the win/loss label itself** — fell back to the field that
overstates exitable size by a median 781x.

**Counted:**

| | rows | realizable | rate |
|---|---:|---:|---:|
| before 2026-09-11 | 107,947 | **793** | 0.73% |
| on/after | 10,874 | 49 | 0.45% |

⭐ **793 of 842 realizable labels — 94.2% — were assigned by the buggy path.**

⚠️ **Honest caveat on the rate shift:** the realizable rate was already falling
before the fix (2.39% in late August to 0.53% by 09-08), so the 0.73%→0.45% drop
is **confounded with time and cannot be attributed to the fix alone.** The 94.2%
figure does not depend on that — it is mechanical, from which code wrote which
row.

**Why this changes everything:** when labels are corrupt, **a negative result is
no more trustworthy than a positive one.** "No signal survived" is not evidence
of absence; it is evidence that nothing correlated with a broken label. Every
supervised conclusion in this repo — including the discouraging ones — is
suspect in **both** directions.

⛔ **That is the honest basis for un-killing. Not optimism — the labels were
wrong, so the verdicts built on them do not stand either way.**

---

## The list

| # | strategy | what killed it | killer survives correction? |
|---|---|---|---|
| 1 | scoring model / graduation prediction | **Marino** | ⛔ **YES — untouched** |
| 2 | front-running copied wallets (B24) | structural: second prediction problem | ⛔ **YES, mostly** |
| 3 | liquidity trajectory as a signal | **leakage** | ⛔ **YES as built** — ⭐ but redesignable |
| 4 | magnitude as a fraud gate | `age_hours` is pair age | ⚠️ **SPLIT** |
| 5 | buy/sell ratio (weight 0) | failing tokens "won" ~2x more often | ⭐ **NO — re-run** |
| 6 | the 2.10% base rate and every lift from it | computed on `liq` | ⭐ **NO — re-run** |
| 7 | "no signal survived" conclusions | poisoned labels | ⭐ **NO — re-run** |
| 8 | band dwell / nomination impossible | our own sampler | ✅ **ALREADY WITHDRAWN** |

### 1. ⛔ Marino survives. Do not pretend otherwise.

**Source: published, external, n=655,770. Our liquidity field played no part in
producing it.** Perfect knowledge of graduation probability still loses money
because price already reflects the probability at the moment the signal is
readable.

**It constrains curve-level entry and it still does.** Anything that ranks live
tokens by expected return is dead for a reason that corrected data does not
touch. ⭐ **What it does NOT constrain:** anything measured *before a price
exists* (`PRELAUNCH_SIGNAL.md` §1), and anything purely descriptive.

### 2. ⛔ B24 front-running copiers — mostly survives

The objection was structural: predicting *which* copied trade will run is the
same prediction problem one layer removed. **That argument does not depend on
our liquidity data.** The reopening conditions in `RULES.md` B24 stand as
written. ⚠️ One caveat: the *supporting* numbers used the poisoned field, so
re-derive them before citing.

### 3. ⛔ Liquidity trajectory — survives as built, ⭐ but the redesign is legitimate

Killed by **leakage**: the feature was measured at the 1h check while the
outcome was measured from entry. Nine of eleven "out-of-sample wins" were
**already at their final multiple by 1h**. The feature was a restatement of the
outcome.

⛔ **Better liquidity data does not fix this.** Measuring a feature after the
outcome is a design error.

⭐ **But `QUESTIONS.md` already names the fix and it is a genuine un-kill:**
*"Does a second observation at a fixed short lag make trajectory usable as an
ENTRY feature?"* Two observations both **strictly before** the decision point,
outcome measured strictly after, is a different and valid experiment. **Reopen
it — with the lag pre-committed before looking.**

### 4. ⚠️ Magnitude — the confound survives, the distribution does not

Two separate killers, and only one holds:

- ⛔ **`age_hours` is pair age, not token age.** A new pool for an established
  token sits in the tail legitimately. **Independent of liquidity data. Survives.**
- ⭐ **The distribution itself was computed on reported liquidity** — and its
  maximum, **$7,406,577,362, is the "Fartcoin" row we have since proven is an
  impersonator holding a different mint entirely.** The p99.9–p99.95 tail that
  produced the "580x cliff" is substantially composed of exactly this artifact.
  **The cliff must be re-derived on realizable numbers.**

### 5. ⭐ Buy/sell ratio — re-run it, this is a live candidate

Currently weighted **0** because tokens that *failed* the gate won nearly twice
as often as those that passed. ⛔ **But "won" means `mult` on rows whose
`realizable` label came from the buggy path.** A pool that cannot be exited can
print any multiple at all, and those prints were counted as wins.

**This is the clearest case for re-running in the whole list.** The result is
not just unsupported, it is exactly the shape a corrupt label produces.

### 6–7. ⭐ Base rates, lifts, and the negative results

⛔ **Never quote 2.10% again** — 397/18,920 on reported liquidity. Our clean
figure is 0.22%, agreeing with Kamat's 0.198%.

**Every lift computed against 2.10%, and every "no signal survived" conclusion,
needs re-running against realizable labels.** ⭐ **Including the socials
question** — `PRELAUNCH_SIGNAL.md` cites published 9x–17x lift for linked
socials, and our own field was never read until 2026-09-17.

### 8. ✅ Band dwell — the kill is already withdrawn

`ts` is per-batch, so all ten "multi-sighting" contracts sat inside a single
pass. It measured our scan loop. Retracted in `0754716`; **whether nomination
works is an open question again, not a settled negative.**

---

## ⛔ How to un-kill honestly

**Re-opening is not re-believing.** Every revived strategy re-enters at the
bottom of the evidence ladder, under the same rules that killed the last five:

1. **Rebuild the labels first.** Nothing can be re-tested until
   `exit_realizable_usd` replaces the substituted field. Re-testing on the old
   labels reproduces the original error with more confidence.
   ⚠️ **Forward-only** — `chainfields.round_trip()` measures *now* and cannot
   reconstruct a historical exit. **The corrected label set starts accumulating
   the day a collector runs, and nothing has collected since 2026-09-15.**
2. **Pre-commit every threshold to a file before looking.** ⛔ `holders >= 100`
   is currently in breach of this and is labelled a candidate, not a result.
3. **n ≥ 30 closed distinct contracts per arm**, Wilson intervals, report both
   ways.
4. **Matched controls, never winner-side rates alone.**
5. **The feature must be measurable strictly before the decision point.** This
   is what killed trajectory and it will kill the next one too.

⚠️ **The honest expected outcome: some of these stay dead.** Marino is not
going anywhere and neither is the leakage rule. **What changes is that the
negative results are no longer evidence** — and with 94.2% of labels assigned by
a known-buggy path, *"we found nothing"* was never a finding in the first place.

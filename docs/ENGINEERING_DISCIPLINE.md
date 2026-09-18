# Verify the output, never the execution

**Standing engineering rule, 2026-09-18. This is the rule the rest of `docs/`
assumes. Read it before adding any component.**

> *"We need to do better testing we have wasted so much time."* — Frank

---

## 1. ⛔ The single pattern behind every failure this week

| what broke | what we checked | what we should have checked |
|---|---|---|
| socials dropped by the whitelist | the field was computed | **that it was present in a written row** |
| score band "fixed" | the changelog | **the source** |
| pools truncated | that the pass completed | **what fraction of input it processed** |
| liquidity off by 781x | that a number came back | **that it matched ground truth** |
| collector dead 4 days | that the task fired | **that rows appeared** |

⛔ **Every one: we verified that something RAN, not that it produced a correct
result.** Four of the five were silent — the component reported success while
producing less than it claimed.

⚠️ **This is not a list of five bugs to fix. It is one bug, five times.** Fixing
them individually is what we have been doing, and it is why we keep paying.

---

## 2. The four rules

### Rule A — every component asserts its own output

Not *"did it execute"* — **"did it produce what it claimed."**

- A **write** asserts the fields landed. `journal.record()` is a whitelist; a
  field not added there does not exist, and it has silently eaten five.
- A **scan** asserts its coverage ratio, every pass, even when it is 100%.
- A **quote** asserts it got a real price. ⭐ Jupiter returns `priceImpactPct: '1'`
  — a sentinel meaning *"no reference price"* — for longtail tokens. Read as a
  number it says 100% impact on a pool that round-trips at 0.76%. **A value that
  arrived is not a value that is true.**
- A **fill** asserts it could have been taken. Paper v1 recorded `notional_usd`
  on every row and never applied it; the multiple was a mid-to-mid ratio at zero
  size. The code ran perfectly for 409 rows and measured nothing.

### Rule B — count ROWS, not beats

> *"A heartbeat with zero rows behind it is a failure, and right now it reads as
> health."*

**Fixed in `liveness.beat()` 2026-09-18.** `n` is the row count. A beat now keeps
two clocks — `last_ts` (it fired) and `last_rows_ts` (it fired **with rows**) —
and `status()` judges on the second. A component that fires on time and produces
nothing is reported **`empty`**, which is a different verdict from `stale`.

⭐ **They need different fixes, and conflating them is how the desktop task read
as healthy for two days while collecting nothing.**

### Rule C — ⛔ loud failure beats silent degradation, always

**A component that cannot tell us it is broken is worse than one that is
obviously broken.** A broken thing that screams costs an hour. A degraded thing
that reports success costs four days and poisons every number computed from it.

Concretely: no `except: pass` that swallows a shortfall; no default that renders
absence as zero (standing rule 5); no metric that only appears on failure,
because a field that is missing when healthy cannot be used to prove health.

### Rule D — every headline number carries provenance and n

So it cannot be quoted out of context later. ⚠️ **I have done that to Frank
twice** — the `2.10%` graduation rate computed on the poisoned liquidity field,
and the `−$3,099` paper P&L computed on fictional fills. Both were repeated for
days after the ground under them had gone.

Every number gets: **the n, the interval, the source file, and the date**. A
number without them is a rumour.

---

## 3. What this means when you add a component

**Before it ships, answer these four in writing:**

1. **What does it claim to produce?** State it as a count or a ratio, not a verb.
2. **How would I know if it produced less?** If the answer is "I wouldn't", it is
   not finished.
3. **What does it record when it degrades?** Not when it crashes — when it half
   works. That is the case that has cost us every time.
4. **What is the alarm, and who sees it?** An unread alarm is not an alarm.

⛔ **"It ran without error" answers none of these.**

---

## 4. Enforced in the suite, not just written here

A rule nobody checks is a comment. These are machine-checked:

| rule | check | file |
|---|---|---|
| coverage is recorded every pass | `pools_seen` / `pools_processed` present and non-None on every coverage row, even at 100% | `test_discipline.py` |
| truncation is never silent | both scanner break sites route through `_truncate()`, which carries the remainder forward | `test_discipline.py` |
| nothing is discarded | a truncated pass writes a carry file; a completed pass clears it | `test_discipline.py` |
| beats count rows | `liveness.beat(n=0)` does not refresh the rows clock; `status()` reports `empty` | `test_discipline.py` |
| no score gates an entry | AST walk of every entry gate | `test_scoreband.py` |
| no mid price reaches a P&L | AST walk of `paperv3.close_entry` | `test_paperv3.py` |
| a symbol cannot render as another token | bidi/homoglyph neutralisation, checked on the built artifact | `test_symbols.py` |
| unknown never renders as a value | `usd()` contract | `test_gate.py`, `dashboard.py` |

⚠️ **The AST checks exist because the score band was "fixed" once and only the
wording changed.** A comment promising a property is not enforcement; a test that
reads the source is.

---

## 5. ⚠️ What this rule does NOT license

- **It is not a mandate to assert everything.** An assertion on a value nobody
  uses is noise that trains people to ignore assertions.
- **It does not make a component correct.** Coverage recording proves we know
  what we missed; it does not mean we missed nothing.
- ⛔ **It does not replace measuring against ground truth.** The 781x liquidity
  error would have passed every self-assertion in this document — the number was
  internally consistent and completely wrong. **Self-assertion catches silent
  degradation. Only an external check catches being wrong.**

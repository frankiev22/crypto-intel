# Scanner truncation: a real bias, and my own overstatement of it

**2026-09-18.**

---

## ⛔ Lead with the correction: I said 24%. It is 3.0%.

I reported *"24% of pools dropped, systematically"* and that every conclusion
drawn from scanner data sits on a biased sample. **I generalised from a single
pass I happened to watch.** That is the same error I have repeatedly flagged in
other people's work, and it should not have left my mouth as a general claim.

**Measured across all 399 recorded scan passes** (`data/coverage/*.jsonl`, which
has been logging `pools_returned` and `scanned` all along):

| | |
|---|---|
| pools returned by source | **31,863** |
| pools actually enriched | **30,895** |
| **overall coverage** | **97.0%** |
| **dropped, never looked at** | **968 (3.0%)** |
| passes truncated at all | 221 of 399 (55%) |
| per-pass coverage | min 19% · p25 96% · **median 99%** · max 100% |

**The pass I watched (70/94 = 74%) is the sixth-worst in the entire history.**
The median pass loses one pool in a hundred.

⚠️ **The bias is real. The magnitude I gave was wrong by 8x, and in the
direction that made it sound alarming.**

## 1. The mechanism, confirmed from source

`sources.new_pools()` pages GeckoTerminal `new_pools` from page 1 to 5 and
appends each page in order, deduping. **Page 1 is newest.** So `pools` arrives
ordered **newest → oldest**.

`scanner.py:201` iterates `for i, p in enumerate(pools)` with **no shuffle and no
sort** — the only sort is `rows.sort(...)` at `scanner.py:425`, *after*
enrichment. The budget checks at `scanner.py:214` and `scanner.py:220` `break`
out of that loop.

⭐ **So the drop is always the tail, and the tail is always the oldest pools in
the batch — roughly pages 4–5, i.e. pools from ~60–100 seconds earlier in the
stream.** The bias direction is **toward over-sampling the very newest pools.**

## 2. When it bites

Daily coverage, worst to best:

```
2026-09-11  92.6%      2026-09-10  93.8%      2026-08-30  94.6%
2026-09-06  96.0%      2026-09-02  96.4%      ...
2026-09-04  99.7%      2026-09-03  99.5%      2026-09-05  99.3%
```

Worst individual passes: **19%** (2026-09-02T10:05, 18/93), 20%, 33%, 48%, 69%,
74%. ⚠️ The 87% and 83% days at the end are **my own manual runs** with tight
`--max-seconds`, not the automated collector.

⛔ **Separately, and worse than truncation: 103 `aborted_pass` records with
`pools_returned: 0, scanned: 0` and `suspected_cause: "killed - no clean exit"`.**
Those passes collected *nothing at all*. That is a bigger hole than the 3% and it
is not a bias, it is absence.

## 3. ⭐ Which findings are actually exposed

**At 97% coverage with a known direction, most are not materially exposed.** Being
specific rather than alarming:

| finding | n | exposure |
|---|---|---|
| 781x liquidity overstatement | large corpus | ⬜ **negligible** — 3% missing cannot move a median of that size |
| graduation base rate 0.22% (30/13,709) | large | ⬜ **negligible**, and it agrees with Kamat's external 0.198% |
| $1M verification pass rate 25.4% (n=696) | medium | ⚠️ **minor** — interval already quoted, 3% sits inside it |
| ⛔ **D1/D2 detector precision** (23 flags, "0 false positives") | **tiny** | ⛔ **most exposed.** At n=23 a biased 3% is a whole flag. And D1/D2 are *already* suspect for being computed on the poisoned `liq` field |
| anything computed from a single pass or a handful of passes | tiny | ⛔ **most exposed** — the worst passes lost 80% |
| holder-count / Jupiter work in this session | n/a | ⬜ **unaffected** — keyed on contract address, not drawn from a scan pass |

⭐ **The honest summary: this bias does not overturn the big corpus findings. It
is a real problem for small-n results, and the smallest-n result we have is the
one I have twice described as beating the state of the art.**

## 4. ⚠️ The fix is not obviously "shuffle", and here is the trade-off

The instinct is to shuffle `pools` before enrichment so truncation is unbiased.
**That would fix the statistics and damage the purpose.**

The scanner exists to **catch launches early**. Newest-first is not an accident;
it is the operational intent. Shuffling means that when a pass is truncated, it
sometimes drops the freshest launches — the exact rows the system exists to
capture — in exchange for a cleaner sample of rows we care less about.

| option | statistics | operations |
|---|---|---|
| keep newest-first (today) | biased toward newest, 3% | ✅ best launch capture |
| shuffle | unbiased | ⛔ sometimes drops the newest launches |
| **record what was dropped** | **bias becomes measurable and correctable** | ✅ unchanged |

⭐ **Recommendation: do not shuffle. Record.** Coverage already logs the counts;
what is missing is **which pools were skipped**, so any later analysis can say
"this pass saw 74% and here is exactly what it missed" instead of silently
treating a truncated pass as complete.

⛔ **This is a recommendation, not a decision.** If the call is to shuffle
anyway, it is one line and I will make it — but it should be made knowing it
costs launch capture.

## 5. `track.py:209` — reviewed, measured, and NOT the disaster I first wrote

- **`scanner.py:220`** — `if time.time() - started > budget: break`. Same
  mechanism as :214, same tail-drop. **Both are the same finding.**

⛔ **Two corrections to my own first pass at this, before the numbers.**

**Correction 1: the 168h horizon is RETIRED, deliberately.** I measured 48% of
7-day outcome checks ageing out unscored and was about to report it as the
worst bias in the repo. `track.py:20-35` retired 168h on purpose — it resolves
at 2.7-5.1% because the pools are gone by then — and says so explicitly:
*"Anything still pending at 168h ages out of pending()'s window deliberately,
which is the explicit drop rather than the silent one."* **That is a documented
decision, not a leak, and I nearly reported it as one by measuring the code
without reading the header above it.**

**Correction 2: "the queue is structurally over-subscribed" was wrong.** I
derived it from `HORIZON_SLICE = 120` against a 18h window and it looked like
arithmetic. It is not what the data shows — most days lose **0.0%**.

### What the live horizons actually lose

Aged-out rate at each horizon, split at the 2026-09-06 slice fix (`fa972b1`,
80 -> 120 per pass) and again where the collector started dying:

| period | 1h | 6h | 24h |
|---|---:|---:|---:|
| before the slice fix, through 09-05 (n=21,492) | 4.5% | 13.9% | **19.1%** |
| ⭐ after the fix, collector healthy, 09-06..09-10 (n=10,033) | **1.6%** | **4.3%** | ⭐ **5.8%** |
| ⛔ after the fix, collector dying/dead, 09-11 on (n=3,326) | 11.2% | 33.2% | ⛔ **76.4%** |

⛔ **CORRECTION 2026-09-18, after measuring the scheduler.** The "collector
healthy" row below is **not** a measurement of the collector. Those days ran
38–204 passes each, of which only **6–8 were scheduled** — the rest were mine, by
hand. **Only 91 of 691 passes in the whole record were unattended (13%).**
Measured separately: the hourly cron actually fires every **3.24h** (median,
n=99, and 0 of 99 gaps were under 1.5h), so unattended capacity is ~7 passes/day
against ~2,300 new pairs — roughly **37% of what the queue needs.** ⚠️ **So 5.8%
is what the system achieves WITH a human running it, not on its own.**

⭐ **The slice fix worked. 24h went 19.1% -> 5.8%.** The 20.8% figure recorded in
`track.py`'s own comment was real, it was fixed, and the fix held for as long as
the collector ran.

⛔ **Every remaining loss is the collector being down.** 76.4% of 24h outcomes
since 09-11 were never scored, because nothing was running in the window when
they came due. Windows with **no** collector passes average **44.3%** aged out
against **23.7%** for windows with at least one (correlation -0.335, n=25 days).

⭐ **So this is not a new bias. It is the outage, showing up in a second place.**
The collector restoration was already the top item; this says the cost of every
hour it is down is not just a missing observation, it is a missing **label**,
and labels cannot be backfilled — `pending()` will not offer the row again once
its window closes.

### Which findings this exposes

| finding | exposure |
|---|---|
| ⛔ anything using **24h outcomes from 09-11 onward** | ⛔ **most exposed** — 76.4% of that window's labels do not exist |
| 1h / 6h / 24h rates over the **healthy** period | ⬜ **low** — 1.6-5.8%, and matched on `passed` (5.86% vs 6.14%), median score, median fdv and venue mix |
| anything at the **168h** horizon | ⚠️ retired by decision; the rows that exist skew 94% venue-unknown against 40% in the due population, so **do not compute anything new on it** |
| graduation base rate, 781x overstatement | ⬜ negligible — computed from observations, not from this queue |

### What shipped, and what did not

✅ **`track.LAST_COVERAGE`** now records, per horizon per pass: rows due, rows
sliced, rows not reached, **rows that will age out before the next pass**, the
slice limit and the window. A pass that is about to lose labels prints it.
⭐ **This does not fix anything. It makes the loss countable**, which is what was
missing — it stayed invisible for weeks and only surfaced when the queue was
measured directly.

⬜ **Not done, and not recommended without a decision:** raising the slice again
(the healthy-period numbers do not justify it), widening `PENDING_WINDOW_H`
(buys coverage by letting a "24h" check land at 42h+ — standing rule 13 in a
different hat), and writing an explicit `unscored_expired` outcome row (it would
change what the outcomes corpus means, and every existing analysis reads it).

## 6. This is the third instance of one root cause

1. **Sampling slower than the phenomenon** — first checkpoint at 1h against a
   ~1min median time-to-bond (standing rule 13).
2. **Comparing samples from different windows** — the sequential Helius A/B that
   made a filtered stream look busier than its own baseline (standing rule 14).
3. **Truncating a sample non-randomly** — this, in two places: the scanner's
   3% tail-drop and, far worse, `track.py`'s 21% of outcome checks that expire
   unscored.

**All three are the instrumentation shaping the finding.** Rules 13 and 14 each
came from one of these. This one earns the third.

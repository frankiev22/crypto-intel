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

## 5. The other two unreviewed early exits

- **`scanner.py:220`** — `if time.time() - started > budget: break`. Same
  mechanism as :214, same tail-drop, same fix. **Both are the same finding.**
- **`track.py:209`** — `if S.over_budget(headroom=2)`. ⚠️ **Not reviewed yet.**
  `track.py` scores outcomes rather than discovering pools, so a truncation there
  drops *outcome records*, not observations — a different and potentially worse
  exposure, because outcomes are the labels. **Flagged, not yet measured.**

## 6. This is the third instance of one root cause

1. **Sampling slower than the phenomenon** — first checkpoint at 1h against a
   ~1min median time-to-bond (standing rule 13).
2. **Comparing samples from different windows** — the sequential Helius A/B that
   made a filtered stream look busier than its own baseline (standing rule 14).
3. **Truncating a sample non-randomly** — this.

**All three are the instrumentation shaping the finding.** Rules 13 and 14 each
came from one of these. This one earns the third.

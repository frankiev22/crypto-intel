# The template attack, measured in aggregate

2026-09-05. Detectable from stored fields alone — no API call, no live pool
fetch — so every historical row classifies for free and every future one
classifies at write time. Implemented in `plausibility.py`.

## The headline number

**66 tokens — 0.36% of the 18,458 we have ever observed — produce 39.6% of
every realizable >=2x outcome row on the books, and 44.9% of everything at
>=5x.**

| | count | template | share |
|---|---:|---:|---:|
| realizable outcome rows >= 2x | 164 | 65 | **39.6%** |
| distinct pairs behind them | 111 | 34 | 30.6% |
| rows at >= 5x | 89 | 40 | **44.9%** |
| milestone crossings, all kinds | 1,546 | 105 | 7% |
| ...`realizable_2x` | 111 | 34 | **31%** |
| ...`realizable_3x` | 88 | 34 | **39%** |
| ...`mcap_1m` | 225 | 1 | 0% |
| ...`mcap_5m` | 127 | 1 | 1% |

The multiple-based milestones are a third to two fifths fake. The market-cap
ones are essentially clean, because a template reprices without its FDV ever
crossing a real threshold.

## It never cost us an entry

**No template observation has ever passed the filter.** All 67 were rejected,
maximum score 50, and the reason given 51 times was `vol/liq 0.00 - liquidity
parked, nothing trading`. The scanner was right about every single one.

The damage was never to entries. It was to the record we grade ourselves
against: a class we correctly refused to buy supplied ~40% of the "wins" we
then measured our own filter by.

## The detector

`liq / fdv` decomposes as *(share of supply sitting in the pool) + (quote/fdv)*,
verified against a pool whose sides were pulled live:

    worthless   liq $1,285,629   fdv $1,298,827   liq/fdv = 0.9898
                base  981,744,468 x $0.001299 = $1,275,286   (0.9817 of supply)
                quote 98.73 SOL              =    ~$10,236   (0.0079 of fdv)

So a ratio near 1 means *all supply is in the pool* — the one-sided signature.
Against the 53 tokens verified by fetching reserves:

| rule | flagged | true | precision | recall |
|---|---:|---:|---:|---:|
| `liq/fdv >= 0.95` | 536 | 53 | 10% | 100% |
| zero sells with >= 10 buys | 75 | 53 | 71% | 100% |
| **both together** | **61** | **53** | **87%** | **100%** |
| `liq > $1M` | 63 | 2 | 3% | 4% |

**The magnitude gate does not find this class.** Templates report $160k-$360k
*at entry* and only reach ~$1.26M by the outcome check, so a write-time gate
never sees the big number. Magnitude and template are two different
populations, and the fingerprint is the interaction of ratio and silence, not
either term alone.

## What `liq > fdv` does and does not mean

`liq > fdv` is **not** impossible — it needs `quote_usd > (supply - base) x
price`, which for a fresh launch with nearly all supply pooled is about zero,
so any cash side clears it. 708 of 2,723 tokens (26.0%) sit there legitimately.

`liq > 2 x fdv` **is** impossible: the cash side alone would have to be worth
more than every token in existence. Six tokens in the record do it, worst at
2,729x against a $1 fdv, and **three of them passed the filter.** The template
pools are not in this population at all — they sit at 0.99, just under one.

## Magnitude, tuned from the distribution

Reported liquidity, tokens under an hour old, n=20,292:

    p50 $0   p95 $21,136   p99 $207,140   p99.5 $344,813
    p99.9 $199,803,718     p99.95 $956,443,208    max $7,406,577,362

A **580x cliff** between p99.5 and p99.9. Among pools anyone has actually sold
into (>= 3 sells, n=13,424) the p99.9 is $607,779 and the all-time maximum is
$9,089,748. So the hard ceiling is **$10M under one hour** — above anything ever
traded, below the anomaly cluster. 43 tokens breach it. All 63 tokens reporting
over $1M are under an hour old, and three of the top ten are right-to-left
override impersonations, which is a different attack again and is handled in
`tickers.py`.

## What the flag revises

**The score discriminates after all. This reverses what I reported on 09-04.**

| | n | wins | >= 2x | 95% CI |
|---|---:|---:|---:|---|
| passed (>= 70), all rows | 974 | 22 | 2.26% | [1.50%, 3.40%] |
| rejected (< 70), all rows | 1,469 | 34 | 2.31% | [1.66%, 3.22%] |
| passed, template excluded | 974 | 22 | **2.26%** | [1.50%, 3.40%] |
| rejected, template excluded | 1,412 | 6 | **0.42%** | [0.19%, 0.92%] |

The intervals separate. Yesterday I said the two were indistinguishable, using
a cruder `liq/price ~ 1e9` flag that missed part of the population sitting in
the rejected band. **The template class was masking a real 5.4x edge.** Score
100 remains the worst of the passing bands at 1.3% against 6.7% for 85-99.

**The liquidity gradient loses its top bucket.** Clean 1h window, entry
liq > $5,000:

| bucket | n (all) | >= 2x | n (clean) | >= 2x |
|---|---:|---:|---:|---:|
| negative | 517 | 0.2% | 513 | 0.2% |
| 0 to +20% | 59 | 5.1% | 59 | 5.1% |
| +20 to 50% | 19 | 15.8% | 19 | 15.8% |
| +50 to 100% | 11 | 27.3% | 11 | 27.3% |
| **+100%+** | 36 | **41.7%** | 21 | **14.3%** |

Monotonic before, non-monotonic after, peaking at +50-100%.

**The false-negative ledger is 21% fake.** 96 of 458 entries are template, and
they concentrate exactly where you would expect: 30 of 52 `realizable_2x` and
29 of 48 `realizable_3x`, against 1 of 62 `mcap_1m` and 1 of 50 `mcap_5m`.
**145 distinct genuine tokens remain that we wrongly rejected.**

## Implementation

- `plausibility.assess()` returns `liq_to_fdv_ratio`, `template_suspect`,
  `liquidity_plausible` and an `integrity_flags` list.
- `journal.record()` writes them on every new observation.
- `journal.observations()` fills them in **on read** for history. Every input
  has been on every row since day one, so the archive is never rewritten —
  nothing deleted, nothing restated, the flags are derived.
- `scanner.score()` returns 0 for a row that is not physically possible
  (`liq > 2 x fdv`, or over $10M under an hour). The row is still journalled in
  full; it simply cannot clear the pass line on a number that is wrong.

## Still open

- The GeckoTerminal fallback has no exit-depth measure, so a GT-only row can
  still clear the exit floor on a one-sided pool.
- Multiple-accuracy validation at write time.
- Whether the 1h horizon is retired or the runner cadence is paid for.

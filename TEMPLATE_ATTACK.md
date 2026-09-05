# The template attack, measured in aggregate

2026-09-05, **corrected the same day**. Implemented in `plausibility.py` as
**descriptive columns only**. Nothing filters on any of it.

## ⚠️ Retraction, before anything else

The first version of this document claimed a detector with **87% precision and
100% recall against 53 "live-verified" tokens**. Both halves of that are wrong
and I am withdrawing them:

- The 53 were not verified. They were selected by *another heuristic*
  (`liq/price ~ 1e9` plus zero sells). Measuring one heuristic against another
  is agreement, not validation. **Only three pools had ever been confirmed by
  pulling their base/quote reserves: SUNCOIN, TIKZZZ and `worthless`.**
- The detector is circular in the way that matters. It uses Dexscreener's
  `liquidity.usd` and `fdv` to judge when Dexscreener's `liquidity.usd` is
  misleading. The original finding came from *reserves*, which is independent
  evidence; the proxy has none of the underlying data.

A score-zeroing gate shipped in `scanner.score()` on the strength of that and
**was withdrawn hours later**. It keyed on `age_hours`, which is `pairCreatedAt`
— **pair age, not token age**. A new pool for an established token is
indistinguishable from a new token, so the gate would have zeroed legitimate
large tokens. Demonstrated: a $45M-liquidity token with 7,800 transactions an
hour and real sell-side, in a 20-minute-old pool, scores **80** with the gate
gone and **0** with it in place.

**When a proper labelled set was finally attempted it could not be built.** Of
43 tokens sampled across four strata, **only 9 could still be resolved — 21%.**
Dexscreener stops indexing pools whose reserves collapse, which is exactly the
population that needs labelling, and GeckoTerminal's pools endpoint returns
`reserve_in_usd` with no base/quote split, so it cannot substitute.
**Retrospective validation of this detector is not currently possible.**

What the 9 resolvable rows showed, as measurements rather than proxies:

| token | reported | exit depth | ratio | sells/24h |
|---|---:|---:|---:|---:|
| SUNCOIN | $1,260,745 | $10,030 | 125.7x | 0 |
| ZODL | $1,263,969 | $10,061 | 125.6x | 0 |
| CHAD | $1,261,985 | $10,045 | 125.6x | 0 |
| HASH | $486 | $4 | 125.7x | 0 |
| STUFFY | $484 | $4 | 125.8x | 0 |
| Solana | $2,286 | $244 | 9.4x | 1,397 |
| minilyst | $2,299 | $274 | 8.4x | 2 |
| CYBERLEEK | $0 | $0 | 2.0x | 51 |

Five pools at 125.6–125.8x with zero sells is a tight, real cluster, and three
controls with sell-side activity sit at 2–9x. **That is suggestive, and it is
nine rows.** It is not a validated detector.

**The fix is forward, not retrospective.** `scanner.score()` now stores
`liq_base`, `liq_quote`, `price_native` and a computed `exit_depth_usd` on every
observation, from the pair object already in hand — a real measurement made
cheap by caching, captured while Dexscreener still indexes the pair. On the
first pass that recorded it, four fresh pools measured **exactly 2.00x**. Once
enough rows carry it, a detector can be validated against reserves with
precision, recall and counts reported *before* anything is allowed to filter.

**Standing rule adopted from this: medians and distributions, never bare means.**
Every field here is heavy-tailed. The zero-sell entry cohort has a mean
liquidity of $169,061,510 against a **median of $256,219**; across all entries
the mean is $22,296,205 against a **median of $24,630**; best-realizable-multiple
has a mean of 0.307 and a **median of 0.000**. Hit rates are counts and stand.
Every "mean" column in the tables below is a tail artifact and should be ignored.

---

## The headline number

**Unvalidated — this counts tokens matching the ratio+silence *pattern*, not
confirmed fakes.** It is reported because the pattern is worth stratifying on,
not because it has been proven.

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
The table below **was** presented as precision and recall. **It is neither.**
The "true" column is another heuristic's output, so this measures agreement
between two proxies and nothing more. Retained only to show what was claimed:

| rule | flagged | agrees with the other heuristic | ~~precision~~ | ~~recall~~ |
|---|---:|---:|---:|---:|
| `liq/fdv >= 0.95` | 536 | 53 | — | — |
| zero sells with >= 10 buys | 75 | 53 | — | — |
| both together | 61 | 53 | — | — |
| `liq > $1M` | 63 | 2 | — | — |

The one line that survives is the last: whatever the ratio+silence pattern is
picking up, **magnitude is not picking up the same thing.** Templates report
$160k-$360k
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

## Magnitude — WITHDRAWN as a gate, kept as description

Reported liquidity, tokens under an hour old, n=20,292:

    p50 $0   p95 $21,136   p99 $207,140   p99.5 $344,813
    p99.9 $199,803,718     p99.95 $956,443,208    max $7,406,577,362

There is a real 580x cliff between p99.5 and p99.9, and it is worth knowing
about. **It is not a fraud signal**, because `age_hours` is pair age: a new
pool for an established token sits in the tail legitimately.

The 43 tokens breaching $10M do have internal structure — 14 share a 24h volume
of exactly $1,041, 9 share $1,050, and 20 share 3 buys / 0 sells — which is
suggestive of *something* templated. But structure is not proof, only 1 of 12
sampled could be resolved to check its reserves, and the one that did (`CC`)
showed $111.9M reported against $78,186 of depth **while carrying 16 sells and
$234,215 of daily volume**. That is not the silent class. Two different things
are in this cohort and neither is established.

Three of the top ten are right-to-left override impersonations, which is a
separate matter handled in `tickers.py`.

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
- `scanner.score()` **does not gate on any of this.** The block that returned 0
  for an "implausible" row was withdrawn the day it shipped. Nothing scores on
  these fields, nothing filters on them, nothing is excluded from the journal
  because of them.
- `scanner.score()` **does** now record `liq_base`, `liq_quote`, `price_native`
  and `exit_depth_usd` on every observation — the reserves themselves, not a
  summary of them, captured while the pair is still indexed.

## The rule that governs the next attempt

No detector filters, scores, or backfills until it reports **precision and
recall with counts against a labelled set built from reserves** — both classes,
fakes and genuinely tradeable tokens. A detector with an unmeasured
false-positive rate is worse than none, because it silently discards real data
and nobody finds out.

## Still open

- The GeckoTerminal fallback has no exit-depth measure, so a GT-only row can
  still clear the exit floor on a one-sided pool.
- Multiple-accuracy validation at write time.
- Whether the 1h horizon is retired or the runner cadence is paid for.
